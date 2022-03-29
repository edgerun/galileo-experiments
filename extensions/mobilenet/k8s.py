from typing import Dict

from kubernetes import client
from kubernetes.client import V1ResourceRequirements, V1EnvVar, V1EnvVarSource, V1ObjectFieldSelector


def mobilenet_pod_factory(pod_name: str, image: str, resource_requests: Dict) -> client.V1Container:
    return client.V1Container(
        image=image,
        name=pod_name,
        ports=[
            client.V1ContainerPort(
                name="function-port", container_port=8080
            )
        ],
        resources=V1ResourceRequirements(
            requests=resource_requests
        ),
        env=[
            V1EnvVar('NODE_NAME', value_from=V1EnvVarSource(
                field_ref=(V1ObjectFieldSelector(field_path='spec.nodeName')))),
            V1EnvVar('MODEL_STORAGE', 'local'),
            V1EnvVar('MODEL_FILE', '/home/app/function/data/mobilenet.tflite'),
            V1EnvVar('LABELS_FILE', '/home/app/function/data/labels.txt'),
            V1EnvVar('IMAGE_STORAGE', 'request')
        ]
    )