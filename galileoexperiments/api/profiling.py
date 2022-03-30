import abc
from typing import Dict

import redis
from galileo.shell.shell import Galileo, ClientGroup
from kubernetes import client


class ProfilingApplication(abc.ABC):

    def spawn_group(self, rds: redis.Redis, galileo: Galileo,
                    config: 'ProfilingWorkloadConfiguration') -> ClientGroup: ...

    def pod_factory(self, pod_name: str, image: str, resource_requests: Dict) -> client.V1Container: ...
