from dataclasses import dataclass
from typing import Dict, Callable, Optional, List, Tuple, Union

import redis
from galileo.shell.shell import RoutingTableHelper, Galileo, Telemd, Experiment
from kubernetes import client

from galileoexperiments.api.profiling import ProfilingApplication


@dataclass
class Pod:
    pod_id: str
    ip: str
    labels: Dict[str, str]
    name: str


@dataclass
class ExperimentRunConfiguration:
    creator: str
    # the kubernetes master node
    master_node: str
    galileo_context: Dict[str, object]
    # arbitrary Dict that will be saved with the Experiment
    metadata: Optional[Dict] = None
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

    @property
    def rds(self) -> redis.Redis:
        return self.galileo_context['rds']


@dataclass
class ProfilingWorkloadConfiguration:
    """
    This class encapsulates the workload of one profiling experiment.
    Either you pass a list of profiles, or configure the remaining parameters.
    """
    creator: str
    # the application name
    app_name: str
    # the host that will be profiled
    host: str
    # the zone in which the host is
    zone: str
    # the kubernetes master hostname
    master_node: str
    # the container image
    image: str
    # number of pods
    no_pods: int
    # stores params for service and metadata about experiment
    params: Dict
    # specifies how to create a ClientGroup and V1Containers
    profiling_app: ProfilingApplication
    # context contains all dependencies, instantiated using `galileo.shell.shell.init`
    context: Dict
    # list of profiles - one per client
    profiles: List[str] = None
    # number of requests
    n: int = None
    # interarrival config
    ia: Union[float, Tuple] = None
    # number of clients
    n_clients: int = None
    # optional load balancer ip, if None, will be read dynamically based on given zone
    lb_ip: str = None

    @property
    def galileo(self) -> Galileo:
        return self.context['g']

    @property
    def telemd(self) -> Telemd:
        return self.context['telemd']

    @property
    def exp(self) -> Experiment:
        return self.context['exp']

    @property
    def rtbl(self) -> RoutingTableHelper:
        return self.context['rtbl']

    @property
    def rds(self) -> redis.Redis:
        return self.context['rds']


@dataclass
class ScenarioWorkloadConfiguration:
    """
    This class encapsulates the workload of one profiling experiment.
    Either you pass a list of profiles, or configure the remaining parameters.
    """
    creator: str

    # image: the application names
    app_names: Dict[str, str]

    # the kubernetes master hostname
    master_node: str

    # {node: { image: number of instances}
    services: Dict[str, Dict[str, int]]

    # {node: zone}
    zone_mapping: Dict[str, str]

    # stores general experiment parameters
    params: Dict

    # stores specific app params (by image)
    app_params: Dict[str, Dict]

    # per image an app that specifies how to create a ClientGroup and V1Containers
    profiling_apps: Dict[str, ProfilingApplication]

    # context contains all dependencies, instantiated using `galileo.shell.shell.init`
    context: Dict

    # per zone: {image: list of profiles - one per client}
    profiles: Dict[str, Dict[str, List[str]]]

    @property
    def galileo(self) -> Galileo:
        return self.context['g']

    @property
    def telemd(self) -> Telemd:
        return self.context['telemd']

    @property
    def exp(self) -> Experiment:
        return self.context['exp']

    @property
    def rtbl(self) -> RoutingTableHelper:
        return self.context['rtbl']

    @property
    def rds(self) -> redis.Redis:
        return self.context['rds']


@dataclass
class AppWorkloadConfiguration:
    app_container_image: str
    requests: Callable[[], None]
    pod_factory: Callable[[str, str], client.V1Container]


@dataclass
class ProfilingExperimentConfiguration:
    app_name: str
    # used to determine the zone in which the clients will spawn
    zone: str
    # hosts that should emit telemetry data and is being profiled
    host: str
    # load balancer ip that forwards requests
    lb_ip: str
    # how many pods should be started on the host
    no_pods: int
    # how many clients should be started
    n_clients: int
    app_workload_config: AppWorkloadConfiguration
    exp_run_config: ExperimentRunConfiguration

    @property
    def rtbl(self) -> RoutingTableHelper:
        return self.exp_run_config.rtbl


@dataclass
class ScenarioExperimentConfiguration:
    # apps per (function, zone)
    apps: List[AppWorkloadConfiguration]
    exp_run_config: ExperimentRunConfiguration
