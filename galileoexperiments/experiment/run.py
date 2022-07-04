import logging
import time
from typing import Callable

from galileoexperiments.api.model import ProfilingExperimentConfiguration, ScenarioExperimentConfiguration, \
    ExperimentRunConfiguration
from galileoexperiments.utils.k8s import start_telemd_kubernetes_adapter, stop_telemd_kubernetes_adapter
from galileoexperiments.utils.rds import wait_for_galileo_events

logger = logging.getLogger(__name__)


def run_profiling_experiment(config: ProfilingExperimentConfiguration):
    run_experiment(config.exp_run_config, config.app_workload_config.requests)


def run_scenario_experiment(config: ScenarioExperimentConfiguration, requests: Callable):
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
        time.sleep(5)

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
