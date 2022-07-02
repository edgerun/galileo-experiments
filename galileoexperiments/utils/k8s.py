import logging
from dataclasses import dataclass
from typing import List, Dict, Callable

from kubernetes import client, config
from kubernetes.client import V1Deployment, V1ObjectMeta, V1DeploymentSpec, V1LabelSelector, V1PodTemplateSpec, \
    V1PodSpec, V1Toleration, V1Container, V1EnvFromSource, V1ConfigMapEnvSource
from kubernetes.client import V1ResourceRequirements, V1EnvVar, V1EnvVarSource, V1ObjectFieldSelector

from galileoexperiments.api.model import Pod

logger = logging.getLogger(__name__)


def start_telemd_kubernetes_adapter(master_node: str) -> V1Deployment:
    # Configs can be set in Configuration class directly or using helper utility
    config.load_kube_config()

    v1 = client.AppsV1Api()
    image = 'edgerun/telemd-kubernetes-adapter:0.1.18'
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


def get_pods(pod_names: List[str]) -> List[Pod]:
    config.load_kube_config()
    v1 = client.CoreV1Api()
    pod_list = v1.list_namespaced_pod("default")
    pods = []
    for pod in pod_list.items:
        if pod.metadata.name in pod_names:
            ip = pod.status.pod_ip
            labels = pod.metadata.labels
            pod_id = pod.metadata.uid
            name = pod.metadata.name
            pods.append(Pod(pod_id, ip, labels, name))

    return pods


def spawn_pods(image: str, name: str, node: str, labels: Dict[str, str], n: int, pod_factory: Callable[[str, str, Dict], client.V1Container]) -> List[str]:
    """
    Function spawns n pods on the given node. The pod factory creates the containers to allow
    different kinds of containers.
    :param image: the container imag
    :param name: the pod name prefix
    :param node: the node
    :param labels: labels to attach
    :param n: the number of pods to spawn on the given node
    :param pod_factory: factory function to create V1Containers
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
        pod = client.V1Pod(
            api_version="v1",
            kind="Pod",
            metadata=client.V1ObjectMeta(name=pod_name, labels=labels),
            spec=client.V1PodSpec(
                node_selector=selector,
                containers=[
                    pod_factory(pod_name, image, resource_requests)
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
        v1.delete_namespaced_pod(name, 'default', async_req=False)
