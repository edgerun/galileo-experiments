import logging
import time
from typing import List, Dict, Callable

import kubernetes
from galileoexperiments.api.model import Pod
from galileoexperiments.utils.constants import zone_label
from kubernetes import client, config
from kubernetes.client import V1Deployment, V1ObjectMeta, V1DeploymentSpec, V1LabelSelector, V1PodTemplateSpec, \
    V1PodSpec, V1Toleration, V1Container, V1EnvFromSource, V1ConfigMapEnvSource
from kubernetes.client import V1EnvVar

logger = logging.getLogger(__name__)


def start_telemd_kubernetes_adapter(master_node: str) -> V1Deployment:
    # Configs can be set in Configuration class directly or using helper utility
    config.load_kube_config()

    v1 = client.AppsV1Api()
    image = 'edgerun/telemd-kubernetes-adapter:0.1.20'
    return v1.create_namespaced_deployment(pretty=True, namespace='default',
                                           body=V1Deployment(
                                               api_version='apps/v1',
                                               kind='Deployment',
                                               metadata=V1ObjectMeta(name='telemd-kubernetes-adapter'),
                                               spec=V1DeploymentSpec(
                                                   replicas=1,
                                                   selector=V1LabelSelector(match_labels={
                                                       'app': 'telemd-kubernetes-adapter'
                                                   }),
                                                   template=V1PodTemplateSpec(
                                                       metadata=V1ObjectMeta(
                                                           labels={'app': 'telemd-kubernetes-adapter'}),
                                                       spec=V1PodSpec(
                                                           tolerations=[
                                                               V1Toleration(
                                                                   key='node-role.kubernetes.io/master',
                                                                   operator='Exists',
                                                                   effect='NoSchedule'
                                                               )
                                                           ],
                                                           node_selector={
                                                               'kubernetes.io/hostname': master_node
                                                           },
                                                           containers=[
                                                               V1Container(
                                                                   name='telemd-kubernetes-adapter',
                                                                   image=image,
                                                                   env_from=[
                                                                       V1EnvFromSource(
                                                                           config_map_ref=
                                                                           V1ConfigMapEnvSource(
                                                                               name='telemd-kubernetes-adapter-config'
                                                                           )
                                                                       )
                                                                   ]
                                                               )
                                                           ]
                                                       )
                                                   ),
                                               ),
                                           ))


def stop_telemd_kubernetes_adapter():
    # Configs can be set in Configuration class directly or using helper utility
    config.load_kube_config()

    v1 = client.AppsV1Api()
    v1.delete_namespaced_deployment(name='telemd-kubernetes-adapter', namespace='default')


def get_pods(pod_names: List[str], v1: client.CoreV1Api = None) -> List[Pod]:
    if v1 is None:
        config.load_kube_config()
        v1 = client.CoreV1Api()
    pod_list = v1.list_namespaced_pod("default")
    pods = []
    for pod in pod_list.items:
        if pod.metadata.name in pod_names:
            ip = pod.status.pod_ip
            if ip is None:
                logger.info(f'Pod IP for {pod.metadata.name} is not yet available. Sleep for 5 seconds...')
                time.sleep(5)
                return get_pods(pod_names, v1)
            labels = pod.metadata.labels
            pod_id = pod.metadata.uid
            name = pod.metadata.name
            pods.append(Pod(pod_id, ip, labels, name))

    return pods


def spawn_pods(image: str, name: str, node: str, labels: Dict[str, str], n: int,
               pod_factory: Callable[[str, str, Dict], client.V1Container], env_vars: Dict[str,str]= None) -> List[str]:
    """
    Function spawns n pods on the given node. The pod factory creates the containers to allow
    different kinds of containers.
    :param image: the container imag
    :param name: the pod name prefix
    :param node: the node
    :param labels: labels to attach
    :param n: the number of pods to spawn on the given node
    :param pod_factory: factory function to create V1Containers
    :param env_vars: a dict containing env variables that will be available in each Pod
    :return: a list containing the names of pods created
    """
    # Configs can be set in Configuration class directly or using helper utility
    config.load_kube_config()
    resource_requests = {}
    v1 = client.CoreV1Api()
    pods = []
    for idx in range(n):
        selector = {'kubernetes.io/hostname': node}
        pod_name = f'{name}-{node}-{idx}'
        container = pod_factory(pod_name, image, resource_requests)

        if env_vars is not None:
            for k, v in env_vars.items():
                container.env.append(V1EnvVar(k, v))

        pod = client.V1Pod(
            api_version="v1",
            kind="Pod",
            metadata=client.V1ObjectMeta(name=pod_name, labels=labels),
            spec=client.V1PodSpec(
                node_selector=selector,
                containers=[
                    container
                ],
                volumes=[
                    {
                        'name': 'podinfo',
                        'downwardAPI': {
                            'items': [
                                {'path': 'labels', 'fieldRef': {'fieldPath': 'metadata.labels'}}
                            ]
                        }
                    }
                ]
            ),
        )
        logger.info(f"Create pod '{pod_name}'")
        v1.create_namespaced_pod('default', pod, async_req=False)
        pods.append(pod_name)
    return pods


def remove_pods(names: List[str]):
    config.load_kube_config()
    v1 = client.CoreV1Api()
    for name in names:
        try:
            v1.delete_namespaced_pod(name, 'default', async_req=False)
        except kubernetes.client.exceptions.ApiException:
            logger.debug(f'Pod {name} was not available to teardown anymore')


def fetch_pods(label: str, value: str):
    config.load_kube_config()
    v1 = client.CoreV1Api()
    pods_list = v1.list_namespaced_pod('default')
    pods = []
    for pod in pods_list.items:
        if pod.metadata.labels is None:
            # labels object does not have to be set and can be None: ignore
            continue

        fn_value = pod.metadata.labels.get(label)
        if fn_value == value:
            pods.append(pod)
    return pods


def get_load_balancer_pods() -> Dict[str, Pod]:
    pods = fetch_pods('type', 'api-gateway')
    lb = {}
    for pod in pods:
        # pod name, i.e.: go-load-balancer-deployment-zone-b-xwg9c
        pod_name = pod.metadata.name
        zone = f"zone-{pod_name.split('-')[5]}"
        ip = pod.status.pod_ip
        # not used
        pod_id = ''
        labels = {
            'type': 'api-gateway',
            zone_label: zone
        }
        lb[zone] = Pod(pod_id, ip, labels, pod_name)
    return lb
