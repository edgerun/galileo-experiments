import json
import logging
import os
from typing import List, Dict, Tuple

import etcd3

from galileoexperiments.api.model import Pod
from galileoexperiments.utils.constants import function_label, zone_label

logger = logging.getLogger(__name__)


class EtcdClient:
    _etcd_client: etcd3

    def __init__(self, etcd_host: str, etcd_port: int):
        self.etcd_host = etcd_host
        self.etcd_port = etcd_port
        self._etcd_client = etcd3.client(host=etcd_host, port=etcd_port)

    @staticmethod
    def from_env() -> 'EtcdClient':
        etcd_host = os.environ.get('etcd_host', 'localhost')
        etcd_port = int(os.environ.get('etcd_port', 2379))
        logger.info(f"Connect to etcd instance {etcd_host}:{etcd_port}")
        return EtcdClient(etcd_host, etcd_port)

    def write(self, key: str, value: str):
        self._etcd_client.put(key, value)

    def remove(self, key: str):
        self._etcd_client.delete(key)


def set_weights_rr(pods: List[Pod], cluster: str, fn: str):
    client = EtcdClient.from_env()
    weights = {
        "ips": [f'{pod.ip}:8080' for pod in pods],
        "weights": [1] * len(pods)
    }
    key = f'golb/function/{cluster}/{fn}'
    value = json.dumps(weights)
    logger.info(f'Set following in etcd {key} - {value}')
    client.write(key=key, value=value)
    return key


def set_weight(pod: Pod, weight: int):
    client = EtcdClient.from_env()
    zone = pod.labels[zone_label]
    fn = pod.labels[function_label]
    ip = pod.ip
    key = f'golb/function/{zone}/{fn}'
    value = json.dumps({"ips": [f'{ip}:8080'], "weights": [weight]})
    client.write(key=key, value=value)


def update_weights(pods_per_cluster: Dict[Tuple[str, str], List[Pod]], lbs: Dict[str, Pod]) -> List[str]:
    """
    Sets load balancer weights according to the given arguments.
    Sets for each cluster the internal Pods, as well as adds other clusters that also host the function.
    Thus, in the end if the system consists of three clusters, and only in one a Pod is running: the other two zones
    will re-direct requests to that cluster.
    :param pods_per_cluster: a dict, that contains a List of Pods for each Tuple[function, cluster]
    :param lbs: a dict, keyed by cluster and containing the  associated load balancer pod
    :return: list of etcd keys that were written
    """
    keys = []
    for pair in pods_per_cluster.keys():
        fn = pair[0]
        cluster = pair[1]
        # fetch pods in cluster
        pods = pods_per_cluster[pair].copy()

        # look for other clusters that node the function
        for lb_cluster, lb_pod in lbs.items():
            if lb_cluster == cluster:
                continue
            else:
                pods_of_cluster = pods_per_cluster.get((fn, lb_cluster))
                if pods_of_cluster is not None and len(pods_of_cluster) > 0:
                    pods.append(lb_pod)

        # update weights
        keys.append(set_weights_rr(pods, cluster, fn))

    # set also weights for clusters that do not host any instance and re-route them to the others
    for fn,_ in pods_per_cluster.keys():
        for cluster in lbs.keys():
            pods_of_cluster = pods_per_cluster.get((fn, cluster))
            if pods_of_cluster is not None:
                # we can skip this case, because weights have already been set before
                continue

            # look for clusters that host the function
            other_lbs = []
            for other_cluster in lbs.keys():
                if cluster == other_cluster:
                    pass
                pods_of_other_cluster = pods_per_cluster.get((fn, other_cluster))
                if pods_of_other_cluster is not None:
                    # we have found a cluster that hosts the function, we add its load balancer to the list
                    other_lbs.append(lbs[other_cluster])

            # set the weights for the cluster that has no Pods and re-direct all requests equally to all other clusters
            # that host a function
            keys.append(set_weights_rr(other_lbs, cluster, fn))

    return keys
