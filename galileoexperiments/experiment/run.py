import logging
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Callable

from galileoexperiments.api.model import ProfilingExperimentConfiguration, ScenarioExperimentConfiguration, \
    ExperimentRunConfiguration
from galileoexperiments.utils.k8s import start_telemd_kubernetes_adapter, stop_telemd_kubernetes_adapter
from galileoexperiments.utils.rds import wait_for_galileo_events

logger = logging.getLogger(__name__)


def run_profiling_experiment(config: ProfilingExperimentConfiguration):
    run_experiment(config.exp_run_config, config.app_workload_config.requests)

# TODO test profiling again and scenario

def run_scenario_experiment(config: ScenarioExperimentConfiguration):
    # make callable that calls all AppWorkloadConfigurations and waits for all to end
    async_requests = []
    for app in config.apps:
        async_requests.append(app.requests)

    def requests():
        with ThreadPoolExecutor(max_workers=len(async_requests)) as executor:
            for async_request in async_requests:
                executor.submit(async_request)

    return run_experiment(config.exp_run_config, requests)


def run_experiment(config: ExperimentRunConfiguration, requests: Callable):
    metadata = config.metadata
    if metadata is None:
        metadata = {}
    try:

        # discover workers
        workers = config.galileo.discover()
        logger.info(f"Discovered workers: {workers}")
        time.sleep(1)

        # toggle tracing
        logger.info("Start tracing")
        config.galileo.start_tracing()

        # unpause telemd
        logger.info(f"Unpause telemd")
        config.telemd.start_telemd()

        # start exp
        logger.info("Start experiment and wait for 1 second")
        config.exp.start(
            name=config.exp_name,
            creator=config.creator,
            metadata=metadata
        )
        time.sleep(1)

        # start telemd kubernetes adapter
        start_telemd_kubernetes_adapter(config.master_node)
        logger.info("Waiting for telemd_kubernetes adapter to publish galileo events")
        wait_for_galileo_events(config.rds)
        time.sleep(1)

        # set requests
        logger.info("start requests")
        requests()


    except Exception as e:
        logger.error(e)
    finally:
        logger.info("Stop tracing")
        config.galileo.stop_tracing()
        logger.info("Pause telemd")
        config.telemd.stop_telemd()
        logger.info("Stop exp")
        config.exp.stop()
        logger.info("Shutdown telemd kubernetes adapter")
        stop_telemd_kubernetes_adapter()
