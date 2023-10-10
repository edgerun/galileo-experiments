import logging
import time
from typing import List, Dict, Tuple, Callable

from galileo.shell.shell import RoutingTableHelper, ClientGroup

from galileoexperiments.api.model import ScenarioWorkloadConfiguration, Pod, ScenarioExperimentConfiguration, \
    ExperimentRunConfiguration, AppWorkloadConfiguration
from galileoexperiments.api.profiling import GalileoClientGroupConfig
from galileoexperiments.experiment.run import run_scenario_experiment
from galileoexperiments.utils.arrivalprofile import clear_list, read_and_save_profile
from galileoexperiments.utils.constants import function_label, zone_label
from galileoexperiments.utils.helpers import EtcdClient, update_weights
from galileoexperiments.utils.k8s import spawn_pods, get_pods, remove_pods, get_load_balancer_pods

logger = logging.getLogger(__name__)


def spawn_pods_for_config(workload_config: ScenarioWorkloadConfiguration, lb_pods: Dict[str, str]) -> List[Pod]:
    pod_names = []
    for host, values in workload_config.services.items():
        for image, no_pods in values.items():
            name = workload_config.app_names[image]

            zone = workload_config.zone_mapping[host]
            labels = {
                function_label: name,
                zone_label: zone
            }

            env_vars = {
                'API_GATEWAY': lb_pods[zone]
            }

            profiling_app = workload_config.profiling_apps[image]
            pod_name_prefix = f'{name}-deployment'
            names = spawn_pods(image, pod_name_prefix, host, labels, no_pods, profiling_app.pod_factory,
                               env_vars=env_vars)
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


def set_loadbalancer_weights(pods: Dict[Tuple[str, str], List[Pod]], lbs: Dict[str, Pod]):
    return update_weights(pods, lbs)


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


def prepare_client_groups_for_services(workload_config: ScenarioWorkloadConfiguration) -> Tuple[List[
                                                                                                    Tuple[
                                                                                                        str, str, ClientGroup]], Callable]:
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

            client_groups.append((image, zone, client_group))

    def requests():
        all_cmds = []
        for idx, group in enumerate(client_groups):
            cmd = group[2].request(ia=('prerecorded', 'ran'))
            all_cmds.append(cmd)

        for cmd in all_cmds:
            cmd.wait()

    return client_groups, requests


def set_params(workload_config: ScenarioWorkloadConfiguration):
    workload_config.params['app_params'] = workload_config.app_params
    workload_config.params['profiles'] = workload_config.profiles
    workload_config.params['lb_ips'] = workload_config.lb_ips
    workload_config.params['zone_mapping'] = workload_config.zone_mapping
    workload_config.params['services'] = workload_config.services
    workload_config.params['app_names'] = workload_config.app_names


def run_scenario_workload(workload_config: ScenarioWorkloadConfiguration):
    rtbl: RoutingTableHelper = workload_config.rtbl
    pods = None
    rtbl_services = []
    etcd_service_keys = []
    creator = workload_config.creator
    master_node = workload_config.master_node
    client_groups = []

    lb_pods = get_load_balancer_pods()
    lb_ips = {}
    for zone, pod in lb_pods.items():
        lb_ips[zone] = pod.ip

    workload_config.lb_ips = lb_ips
    try:
        client_groups, requests = prepare_client_groups_for_services(workload_config)
        pods = spawn_pods_for_config(workload_config, lb_ips)

        pods_per_fn_and_cluster = _map_pods_to_dict(pods)

        etcd_service_keys = set_loadbalancer_weights(pods_per_fn_and_cluster, lb_pods)
        rtbl_services = set_rtbl(list(workload_config.app_names.values()), workload_config.lb_ips, rtbl)

        set_params(workload_config)

        exp_run_config = ExperimentRunConfiguration(
            creator=creator,
            master_node=master_node,
            galileo_context=workload_config.context,
            metadata=workload_config.params,
        )
        app_configs = []

        for (image, zone, client_group) in client_groups:
            app_workload_config = AppWorkloadConfiguration(
                app_container_image=image,
                requests=lambda x: None,
                pod_factory=workload_config.profiling_apps[image].pod_factory
            )
            app_configs.append(app_workload_config)

        scenario_experiment_config = ScenarioExperimentConfiguration(
            apps=app_configs,
            exp_run_config=exp_run_config
        )
        run_scenario_experiment(scenario_experiment_config, requests)
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
        for c_group in client_groups:
            c_group[2].close()
