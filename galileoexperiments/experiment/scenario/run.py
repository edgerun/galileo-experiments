# TODO implement one function that does only the plumbing for the workers and does not start any experiment
# TODO implement one function that prepares the experiment but does not invoke the previous function
# TODO implement one function that calls the previous function, s.t. an experiment with different profiles is started
# TODO use the functions in galileo-faas to implement invoke but also show how to start an experiment

# deploy pods on nodes
# set load balancer to pods
# create clients
import logging
import time
from typing import List, Dict, Tuple, Callable

from galileo.shell.shell import RoutingTableHelper, Galileo, ClientGroup

from galileoexperiments.api.model import ScenarioWorkloadConfiguration, Pod, ScenarioExperimentConfiguration, \
    ExperimentRunConfiguration, AppWorkloadConfiguration
from galileoexperiments.api.profiling import GalileoClientGroupConfig
from galileoexperiments.experiment.run import run_scenario_experiment
from galileoexperiments.utils.arrivalprofile import clear_list, read_and_save_profile
from galileoexperiments.utils.constants import function_label, zone_label
from galileoexperiments.utils.helpers import set_weights_rr, EtcdClient
from galileoexperiments.utils.k8s import spawn_pods, get_pods, remove_pods

logger = logging.getLogger(__name__)


def spawn_pods_for_config(workload_config: ScenarioWorkloadConfiguration) -> List[Pod]:
    pod_names = []
    for host, values in workload_config.services.items():
        for image, no_pods in values.items():
            name = workload_config.app_names[image]

            labels = {
                function_label: name,
                zone_label: workload_config.zone_mapping[host]
            }
            profiling_app = workload_config.profiling_apps[image]
            names = spawn_pods(image, name, host, labels, no_pods, profiling_app.pod_factory)
            pod_names.extend(names)

    return get_pods(pod_names)


def _map_pods_to_dict(pods: List[Pod]) -> Dict[Tuple[str, str], List[Pod]]:
    pods_map = {}
    for pod in pods:
        zone = pod.labels[zone_label]
        fn = pod.labels[function_label]
        if pods_map.get((fn, zone)) is None:
            pods_map[(fn, zone)] = [pod]
        else:
            pods_map[(fn, zone)].append(pod)

    return pods_map


def set_loadbalancer_weights(pods: Dict[Tuple[str, str], List[Pod]]):
    keys = []
    for t, pods in pods.items():
        fn = t[0]
        zone = t[1]
        key = set_weights_rr(pods, zone, fn)
        keys.append(key)
    return keys


def set_rtbl(fns: List[str], load_balancers: Dict[str, str], rtbl: RoutingTableHelper) -> List[str]:
    """
    :param fns: function names available
    :param load_balancers: load balancer ip addresses by zone
    """
    services = []
    for fn in fns:
        for zone, lb_ip in load_balancers.items():
            service = f'{fn}-{zone}'
            url = f'{lb_ip}:8080'
            logger.info(f"Set routing table '{service} - {url}'")
            rtbl.set(service, [url], [1])
            services.append(service)
    return services


def prepare_client_groups_for_services(workload_config: ScenarioWorkloadConfiguration) -> List[
    Tuple[str, str, ClientGroup, Callable]]:
    client_groups = []
    for zone, values in workload_config.profiles.items():
        for image, profiles in values.items():

            n_clients = len(profiles)
            client_group_config = GalileoClientGroupConfig(
                n_clients=n_clients,
                zone=zone,
                fn_name=workload_config.app_names[image],
                params=workload_config.app_params[image]
            )
            profiling_app = workload_config.profiling_apps[image]
            rds = workload_config.rds
            galileo = workload_config.galileo
            client_group = profiling_app.spawn_group(n_clients, rds, galileo, client_group_config)
            time.sleep(1)
            for index, client in enumerate(client_group.clients):
                profile_path = profiles[index]
                clear_list(client.client_id, rds)
                read_and_save_profile(profile_path, client, rds)

            def requests():
                client_group.request(ia=('prerecorded', 'ran')).wait()
                client_group.close()

            client_groups.append((image, zone, client_group, requests))
    return client_groups


def run_scenario_workload(workload_config: ScenarioWorkloadConfiguration):
    rtbl: RoutingTableHelper = workload_config.rtbl
    pods = None
    rtbl_services = []
    etcd_service_keys = []
    creator = workload_config.creator
    master_node = workload_config.master_node
    try:
        client_groups = prepare_client_groups_for_services(workload_config)
        pods = spawn_pods_for_config(workload_config)
        etcd_service_keys = set_loadbalancer_weights(_map_pods_to_dict(pods))
        rtbl_services = set_rtbl(list(workload_config.app_names.values()), workload_config.lb_ips, rtbl)

        exp_run_config = ExperimentRunConfiguration(
            creator=creator,
            master_node=master_node,
            galileo_context=workload_config.context,
            metadata=workload_config.params,
        )
        app_configs = []

        for (image, zone, client_group, requests) in client_groups:
            app_workload_config = AppWorkloadConfiguration(
                app_container_image=image,
                requests=requests,
                pod_factory=workload_config.profiling_apps[image].pod_factory
            )
            app_configs.append(app_workload_config)

        scenario_experiment_config = ScenarioExperimentConfiguration(
            apps=app_configs,
            exp_run_config=exp_run_config
        )
        run_scenario_experiment(scenario_experiment_config)
    except Exception as e:
        logger.error(e)
    finally:
        if pods is not None:
            logger.info(f'Remove {len(pods)} pods')
            remove_pods([x.name for x in pods])
        for service in rtbl_services:
            logger.info(f'Remove rtbl entry for: {service}')
            rtbl.remove(service)
        client = EtcdClient.from_env()
        for key in etcd_service_keys:
            client.remove(key)
