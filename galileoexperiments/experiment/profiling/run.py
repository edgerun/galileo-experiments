import logging
import time

from galileo.shell.shell import RoutingTableHelper, Galileo

from galileoexperiments.api.model import ProfilingWorkloadConfiguration, \
    ExperimentRunConfiguration, AppWorkloadConfiguration, ProfilingExperimentConfiguration
from galileoexperiments.api.profiling import GalileoClientGroupConfig
from galileoexperiments.experiment.run import run_profiling_experiment
from galileoexperiments.experiment.scenario.run import set_loadbalancer_weights
from galileoexperiments.utils.arrivalprofile import clear_list, read_and_save_profile
from galileoexperiments.utils.constants import function_label, zone_label
from galileoexperiments.utils.helpers import set_weights_rr, EtcdClient
from galileoexperiments.utils.k8s import spawn_pods, get_pods, remove_pods, get_load_balancer_pods

logger = logging.getLogger(__name__)


def _run(config: ProfilingExperimentConfiguration):
    if config.exp_run_config.exp_name is None:
        config.exp_run_config.exp_name = f'{config.app_name}-{int(time.time())}'
    logger.info("Set up experiment")

    rtbl: RoutingTableHelper = config.rtbl
    service = f'{config.app_name}-{config.zone}'

    try:
        url = f'{config.lb_ip}:8080'
        logger.info(f"Set routing table '{service} - {url}'")
        rtbl.set(service, [url], [1])
        return run_profiling_experiment(config)
    finally:
        if rtbl is not None:
            logger.info(f"Remove routing table '{service}'")
            rtbl.remove(service)


def run_profiling_workload(workload_config: ProfilingWorkloadConfiguration):
    rds = workload_config.rds
    galileo: Galileo = workload_config.galileo
    client_group = None

    zone = workload_config.zone
    creator = workload_config.creator
    master_node = workload_config.master_node
    host = workload_config.host
    image = workload_config.image
    profiling_app = workload_config.profiling_app
    if workload_config.lb_ip is None:
        lb_pods = get_load_balancer_pods()
        lb_ips = {}
        for cluster, pod in lb_pods.items():
            lb_ips[cluster] = pod.ip
        workload_config.lb_ip = lb_ips[workload_config.zone]
    else:
        # we use the given load balancer ip
        pass

    if workload_config.params.get('exp') is None or workload_config.params['exp'].get('requests') is None:
        workload_config.params['exp'] = {
            'requests': {}
        }

    use_profiles = workload_config.profiles is not None
    if use_profiles:
        profiles = workload_config.profiles
        workload_config.params['exp']['requests']['profiles'] = profiles
        n_clients = len(profiles)
        workload_config.params['exp']['requests']['n_clients'] = n_clients
        workload_config.params['exp']['requests']['no_pods'] = workload_config.no_pods

        client_group_config = GalileoClientGroupConfig(
            n_clients=n_clients,
            zone=workload_config.zone,
            fn_name=workload_config.app_name,
            params=workload_config.params
        )

        client_group = profiling_app.spawn_group(n_clients, rds, galileo, client_group_config)
        time.sleep(1)
        for index, client in enumerate(client_group.clients):
            profile_path = profiles[index]
            clear_list(client.client_id, rds)
            read_and_save_profile(profile_path, client, rds)


        def requests():
            client_group.request(ia=('prerecorded', 'ran')).wait()
            client_group.close()

        try:
            exp_run_config = ExperimentRunConfiguration(
                creator=creator,
                master_node=master_node,
                galileo_context=workload_config.context,
                metadata=workload_config.params,
            )
            app_workload_config = AppWorkloadConfiguration(
                app_container_image=image,
                pod_factory=profiling_app.pod_factory,
                requests=requests,
            )
            config = ProfilingExperimentConfiguration(
                app_name=workload_config.app_name,
                zone=zone,
                host=host,
                no_pods=workload_config.no_pods,
                n_clients=n_clients,
                app_workload_config=app_workload_config,
                exp_run_config=exp_run_config,
                lb_ip=workload_config.lb_ip
            )

            logger.info(f'run: {workload_config.params}')
            _run_profiling_experiment(config)

        except Exception as e:
            logger.error(e)

    else:
        workload_config.params['exp']['requests']['n'] = workload_config.n
        workload_config.params['exp']['requests']['ia'] = workload_config.ia
        workload_config.params['exp']['requests']['n_clients'] = workload_config.n_clients
        workload_config.params['exp']['requests']['no_pods'] = workload_config.no_pods

        client_group_config = GalileoClientGroupConfig(
            n_clients=workload_config.n_clients,
            zone=workload_config.zone,
            fn_name=workload_config.app_name,
            params=workload_config.params
        )

        client_group = profiling_app.spawn_group(workload_config.n_clients, rds, galileo, client_group_config)

        def requests():
            # FIXME for some reason workers send only n-1 and not n requests
            client_group.request(n=workload_config.n+1, ia=workload_config.ia).wait()
            client_group.close()

        try:
            exp_run_config = ExperimentRunConfiguration(
                creator=creator,
                master_node=master_node,
                galileo_context=workload_config.context,
                metadata=workload_config.params,
            )
            app_workload_config = AppWorkloadConfiguration(
                app_container_image=image,
                pod_factory=profiling_app.pod_factory,
                requests=requests
            )
            config = ProfilingExperimentConfiguration(
                app_name=workload_config.app_name,
                zone=zone,
                host=host,
                no_pods=workload_config.no_pods,
                n_clients=workload_config.n_clients,
                app_workload_config=app_workload_config,
                exp_run_config=exp_run_config,
                lb_ip=workload_config.lb_ip
            )

            logger.info(f'run: {workload_config.params}')
            _run_profiling_experiment(config)
        except Exception as e:
            logger.error(e)


def _run_profiling_experiment(config: ProfilingExperimentConfiguration):
    pod_names = None
    params = config.exp_run_config.metadata
    image = config.app_workload_config.app_container_image
    name = config.app_name
    pod_prefix = f'{name}-deployment'
    host = config.host
    no_pods = config.no_pods
    n_clients = config.n_clients
    etcd_service_keys = []
    params['exp']['host'] = host
    params['exp']['zone'] = config.zone
    params['exp']['app_name'] = config.app_name
    params['exp']['app_container_image'] = config.app_workload_config.app_container_image

    try:
        labels = {
            function_label: config.app_name,
            zone_label: config.zone
        }

        lb_pods = get_load_balancer_pods()
        env_vars = {
            'API_GATEWAY': lb_pods[config.zone].ip
        }

        pod_names = spawn_pods(image, pod_prefix, host, labels, no_pods, config.app_workload_config.pod_factory,
                               env_vars)
        pods = get_pods(pod_names)

        logger.info("Set weights for Pod(s)")
        pods_per_fn_and_cluster = {
            (name, config.zone): pods
        }
        lb_pods = get_load_balancer_pods()

        etcd_service_keys = set_loadbalancer_weights(pods_per_fn_and_cluster, lb_pods)

        time.sleep(1)
        if config.exp_run_config.exp_name is None:
            experiment_name = f'{name}-clients-{n_clients}-{int(time.time())}'
            config.exp_run_config.exp_name = experiment_name
        return _run(config)
    except Exception as e:
        logger.error(e)
    finally:
        if pod_names is not None:
            logger.info(f'Remove {len(pod_names)} pods')
            remove_pods(pod_names)
        if len(etcd_service_keys) > 0:
            client = EtcdClient.from_env()
            for etcd_service_key in etcd_service_keys:
                client.remove(etcd_service_key)