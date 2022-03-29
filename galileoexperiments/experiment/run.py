import logging
import time

from galileoexperiments.api.model import ExperimentRunConfiguration
from galileoexperiments.utils.k8s import start_telemd_kubernetes_adapter, stop_telemd_kubernetes_adapter
from galileoexperiments.utils.rds import wait_for_galileo_events

logger = logging.getLogger(__name__)


def run_experiment(config: ExperimentRunConfiguration):
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
        config.telemd.start_telemd(config.hosts)

        # start exp
        logger.info("Start experiment and wait for 1 second")
        config.exp.start(name=config.exp_name, creator=config.creator, metadata=metadata)
        time.sleep(1)

        # start telemd kubernetes adapter
        start_telemd_kubernetes_adapter(config.master_node)
        logger.info("Waiting for telemd_kubernetes adapter to publish galileo events")
        wait_for_galileo_events(config.rds)
        time.sleep(1)

        # set requests
        logger.info("start requests")
        config.requests()

        logger.info("finished requests")
    except Exception as e:
        logger.error(e)
    finally:
        logger.info("Stop tracing")
        config.galileo.stop_tracing()
        logger.info("Pause telemd")
        config.telemd.stop_telemd(config.hosts)
        logger.info("Stop exp")
        config.exp.stop()
        logger.info("Shutdown telemd kubernetes adapter")
        stop_telemd_kubernetes_adapter()
