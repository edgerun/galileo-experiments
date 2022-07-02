import abc
from dataclasses import dataclass
from typing import Dict

import redis
from galileo.shell.shell import Galileo, ClientGroup
from kubernetes import client

@dataclass
class GalileoClientGroupConfig:
    n_clients: int
    zone: str
    fn_name: str
    # misc. paremeters for service
    params: Dict

class ProfilingApplication(abc.ABC):

    def spawn_group(self, clients: int, rds: redis.Redis, galileo: Galileo,
                    config: GalileoClientGroupConfig) -> ClientGroup: ...

    def pod_factory(self, pod_name: str, image: str, resource_requests: Dict) -> client.V1Container: ...
