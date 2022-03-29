import json
import logging
import os
from typing import List

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


def set_weights_rr(pods: List[Pod], zone: str, fn: str):
    client = EtcdClient.from_env()
    weights = {
        "ips": [f'{pod.ip}:8080' for pod in pods],
        "weights": [1] * len(pods)
    }
    key = f'golb/function/{zone}/{fn}'
    value = json.dumps(weights)
    logger.info(f'Set following in etcd {key} - {value}')
    client.write(key=key, value=value)


def set_weight(pod: Pod, weight: int):
    client = EtcdClient.from_env()
    zone = pod.labels[zone_label]
    fn = pod.labels[function_label]
    ip = pod.ip
    key = f'golb/function/{zone}/{fn}'
    value = json.dumps({"ips": [f'{ip}:8080'], "weights": [weight]})
    client.write(key=key, value=value)
