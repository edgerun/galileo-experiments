from dataclasses import dataclass
from typing import Dict, Callable, Optional, List

import redis
from galileo.shell.shell import RoutingTableHelper, Galileo, Telemd, Experiment
from kubernetes import client


@dataclass
class Pod:
    pod_id: str
    ip: str
    labels: Dict[str, str]

@dataclass
class ExperimentRunConfiguration:
    creator: str
    requests: Callable[[], None]
    # the kubernetes master node
    master_node: str
    galileo_context: Dict[str, object]
    rds: redis.Redis
    # arbitrary Dict that will be saved with the Experiment
    metadata: Optional[Dict] = None
    # hosts that should emit telemetry data
    hosts: List[str] = None
    exp_name: str = None

    @property
    def galileo(self) -> Galileo:
        return self.galileo_context['g']

    @property
    def telemd(self) -> Telemd:
        return self.galileo_context['telemd']

    @property
    def exp(self) -> Experiment:
        return self.galileo_context['exp']

    @property
    def rtbl(self) -> RoutingTableHelper:
        return self.galileo_context['rtbl']

@dataclass
class ProfileExperimentConfiguration:
    app_name: str
    zone: str
    host: str
    no_pods: int
    n_clients: int
    app_container_image: str
    exp_run_config: ExperimentRunConfiguration
    pod_factory: Callable[[str, str], client.V1Container]

    @property
    def rtbl(self) -> RoutingTableHelper:
        return self.exp_run_config.rtbl

@dataclass
class ProfileWorkloadConfiguration:
    """
    This class encapsulates the workload of the experiment.
    Either you pass a list of profiles, or configure the remaining parameters.
    """
    creator: str
    # the host that will be profiled
    host: str
    # the zone in which the host is
    zone: str
    # the kubernetes master hostname
    master_node: str
    # the container image
    image: str
    # number of pods
    no_pods: List[int]
    # list of profiles - one per client
    profiles: List[str] = None
    # number of requests
    n: List[int] = None
    # interarrival config
    ia: List = None
    # number of clients
    n_clients: List[int] = None

