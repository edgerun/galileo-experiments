import logging
import time

from galileo.shell.shell import RoutingTableHelper

from galileoexperiments.api.model import ProfileExperimentConfiguration
from galileoexperiments.experiment.run import run_experiment
from galileoexperiments.utils.constants import function_label, zone_label
from galileoexperiments.utils.helpers import set_weights_rr
from galileoexperiments.utils.k8s import spawn_pods, get_pods, remove_pods

logger = logging.getLogger(__name__)




def _run(config: ProfileExperimentConfiguration):
    if config.exp_run_config.exp_name is None:
        config.exp_run_config.exp_name = f'{config.app_name}-{int(time.time())}'
    logger.info("Set up experiment")

    rtbl: RoutingTableHelper = config.rtbl
    service = f'{config.app_name}-{config.zone}'

    try:
        url = f'{config.host}:8080'
        logger.info(f"Set routing table '{service} - {url}'")
        rtbl.set(service, [url], [1])
        run_experiment(config.exp_run_config)
    finally:
        if rtbl is not None:
            logger.info(f"Remove routing table '{service}'")
            rtbl.remove(service)


def run_profile_experiment(config: ProfileExperimentConfiguration):
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
        _run(config)
    except Exception as e:
        logger.error(e)
    finally:
        if pod_names is not None:
            logger.info(f'Remove {len(pod_names)} pods')
            remove_pods(pod_names)

