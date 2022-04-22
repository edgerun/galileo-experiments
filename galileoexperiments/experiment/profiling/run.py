import logging
import time

from galileo.shell.shell import RoutingTableHelper, Galileo

from galileoexperiments.api.model import ProfilingExperimentConfiguration, ProfilingWorkloadConfiguration, \
    ExperimentRunConfiguration
from galileoexperiments.experiment.run import run_experiment
from galileoexperiments.utils.arrivalprofile import clear_list, read_and_save_profile
from galileoexperiments.utils.constants import function_label, zone_label
from galileoexperiments.utils.helpers import set_weights_rr
from galileoexperiments.utils.k8s import spawn_pods, get_pods, remove_pods

logger = logging.getLogger(__name__)


def _run(config: ProfilingExperimentConfiguration):
    if config.exp_run_config.exp_name is None:
        config.exp_run_config.exp_name = f'{config.app_name}-{int(time.time())}'
    logger.info("Set up experiment")

    rtbl: RoutingTableHelper = config.rtbl
    service = f'{config.app_name}-{config.zone}'

    try:
        url = f'{config.host}:8080'
        logger.info(f"Set routing table '{service} - {url}'")
        rtbl.set(service, [url], [1])
        return run_experiment(config.exp_run_config)
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

    if workload_config.params.get('exp') is None or workload_config.params['exp'].get('requests') is None:
        workload_config.params['exp'] = {
            'requests': {}
        }

    use_profiles = workload_config.profiles is not None
    if use_profiles:
        profiles = workload_config.profiles
        workload_config.params['exp']['requests']['profiles'] = profiles
        workload_config.params['exp']['requests']['n_clients'] = len(profiles)
        workload_config.params['exp']['requests']['no_pods'] = workload_config.no_pods

        client_group = profiling_app.spawn_group(rds, galileo, workload_config)
        time.sleep(1)
        for index, client in enumerate(client_group.clients):
            profile_path = profiles[index]
            clear_list(client.client_id, rds)
            read_and_save_profile(profile_path, client, rds)

        n_clients = len(profiles)

        def requests():
            client_group.request(ia=('prerecorded', 'ran')).wait()
            client_group.close()

        try:
            exp_run_config = ExperimentRunConfiguration(
                creator=creator,
                requests=requests,
                master_node=master_node,
                galileo_context=workload_config.context,
                metadata=workload_config.params,
                hosts=[host]
            )

            config = ProfilingExperimentConfiguration(
                app_name=workload_config.app_name,
                zone=zone,
                host=host,
                no_pods=workload_config.no_pods,
                n_clients=n_clients,
                app_container_image=image,
                exp_run_config=exp_run_config,
                pod_factory=profiling_app.pod_factory
            )

            logger.info(f'run: {workload_config.params}')
            run_profiling_experiment(config)

        except Exception as e:
            logger.error(e)

    else:
        workload_config.params['exp']['requests']['n'] = workload_config.n
        workload_config.params['exp']['requests']['ia'] = workload_config.ia
        workload_config.params['exp']['requests']['n_clients'] = workload_config.n_clients
        workload_config.params['exp']['requests']['no_pods'] = workload_config.no_pods

        client_group = profiling_app.spawn_group(rds, galileo, workload_config)

        def requests():
            client_group.request(n=workload_config.n, ia=workload_config.ia).wait()
            client_group.close()

        try:
            exp_run_config = ExperimentRunConfiguration(
                creator=creator,
                requests=requests,
                master_node=master_node,
                galileo_context=workload_config.context,
                metadata=workload_config.params,
                hosts=[host]
            )

            config = ProfilingExperimentConfiguration(
                app_name=workload_config.app_name,
                zone=zone,
                host=host,
                no_pods=workload_config.no_pods,
                n_clients=workload_config.n_clients,
                app_container_image=image,
                exp_run_config=exp_run_config,
                pod_factory=profiling_app.pod_factory
            )

            logger.info(f'run: {workload_config.params}')
            run_profiling_experiment(config)
        except Exception as e:
            logger.error(e)


def run_profiling_experiment(config: ProfilingExperimentConfiguration):
    pod_names = None
    params = config.exp_run_config.metadata
    image = config.app_container_image
    name = config.app_name
    host = config.host
    no_pods = config.no_pods
    n_clients = config.n_clients

    params['exp']['host'] = host
    params['exp']['zone'] = config.zone
    params['exp']['app_name'] = config.app_name
    params['exp']['app_container_image'] = config.app_container_image

    try:
        labels = {
            function_label: config.app_name,
            zone_label: config.zone
        }

        pod_names = spawn_pods(image, name, host, labels, no_pods, config.pod_factory)
        logger.info('Sleep for 5 seconds, to wait that pods are placed')
        time.sleep(5)
        pods = get_pods(pod_names)

        logger.info("Set weights for Pod(s)")
        set_weights_rr(pods, config.zone, name)

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