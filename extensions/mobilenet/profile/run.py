import copy
import logging
import time

from galileo.shell.shell import Galileo, init, RoutingTableHelper, Telemd, Experiment
from galileo.worker.context import Context

from extensions.mobilenet.k8s import mobilenet_pod_factory
from extensions.mobilenet.util import spawn_client_group, spawn_zone_group
from galileoexperiments.api.model import ExperimentRunConfiguration, ProfileExperimentConfiguration, \
    ProfileWorkloadConfiguration
from galileoexperiments.experiment.profile.run import run_profile_experiment

logger = logging.getLogger(__name__)


def run_profile(workload_config: ProfileWorkloadConfiguration):
    name = 'mobilenet'
    # prepare params object that will be saved later as metadata
    params = {
        'service': {
            'image_url': 'https://i.imgur.com/0jx0gP8.png'
        }
    }
    params['exp'] = {
        "requests": {}
    }

    # start experiment
    ctx = Context()
    rds = ctx.create_redis()
    g = init(rds)
    image_url = params['service']['image_url']
    galileo: Galileo = g['g']
    client_group = None

    request_list = []
    zone = workload_config.zone
    creator = workload_config.creator
    master_node = workload_config.master_node
    host = workload_config.host
    image = workload_config.image

    use_profiles = workload_config.profiles is not None
    if use_profiles:
        for no_pods in workload_config.no_pods:
            profiles = workload_config.profiles
            client_group = spawn_client_group(profiles, zone, rds, galileo, image_url)
            n_clients = len(profiles)
            params['exp']['requests']['profiles'] = profiles
            params['exp']['requests']['no_pods'] = no_pods

            def requests():
                client_group.request(ia=('prerecorded', 'ran')).wait()
                client_group.close()

            try:
                exp_run_config = ExperimentRunConfiguration(
                    creator=creator,
                    requests=requests,
                    master_node=master_node,
                    galileo_context=g,
                    rds=rds,
                    metadata=params,
                    hosts=[host]
                )

                config = ProfileExperimentConfiguration(
                    app_name=name,
                    zone=zone,
                    host=host,
                    no_pods=no_pods,
                    n_clients=n_clients,
                    app_container_image=image,
                    exp_run_config=exp_run_config,
                    pod_factory=mobilenet_pod_factory
                )

                logger.info(f'run: {params}')
                run_profile_experiment(config)

                time.sleep(15)
            except Exception as e:
                logger.error(e)

    else:
        for n in workload_config.n:
            for ia in workload_config.ia:
                for n_clients in workload_config.n_clients:
                    for no_pods in workload_config.no_pods:
                        client_group = spawn_zone_group(zone, n_clients, galileo, image_url)
                        params['exp']['requests']['n'] = n
                        params['exp']['requests']['ia'] = ia
                        params['exp']['requests']['n_clients'] = n_clients
                        params['exp']['requests']['no_pods'] = no_pods

                        # this is the place configure your clients
                        # you can start multiple client groups that potentially send requests to different services
                        # but make sure that you wait at the end, otherwise the experiment will immediately stop
                        def requests():
                            client_group.request(n=n, ia=ia).wait()
                            client_group.close()

                        try:
                            exp_run_config = ExperimentRunConfiguration(
                                creator=creator,
                                requests=requests,
                                master_node=master_node,
                                galileo_context=g,
                                rds=rds,
                                metadata=params,
                                hosts=[host]
                            )

                            config = ProfileExperimentConfiguration(
                                app_name=name,
                                zone=zone,
                                host=host,
                                no_pods=no_pods,
                                n_clients=n_clients,
                                app_container_image=image,
                                exp_run_config=exp_run_config,
                                pod_factory=mobilenet_pod_factory
                            )

                            logger.info(f'run: {params}')
                            run_profile_experiment(config)

                            time.sleep(15)
                        except Exception as e:
                            logger.error(e)


    for settings in request_list:
        params = settings[0]
        requests = settings[1]

