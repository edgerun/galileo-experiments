import logging
import sys

from extensions.mobilenet.profile.run import run_profile
from galileoexperiments.api.model import ProfileWorkloadConfiguration

logger = logging.getLogger(__name__)


def main():
    logging.basicConfig(level=logging._nameToLevel['INFO'])

    if len(sys.argv) != 6:
        raise ValueError(
            'Program takes exactly five arguments: <creator> <host> <container-image> <zone> <master-node>')

    creator = sys.argv[1]
    host = sys.argv[2]
    image = sys.argv[3]
    zone = sys.argv[4]
    master_node = sys.argv[5]

    workload_config = ProfileWorkloadConfiguration(
        creator=creator,
        host=host,
        image=image,
        master_node=master_node,
        zone=zone,
        no_pods=[1, 2],
        n=[10],
        ia=[0.5],
        n_clients=[1]
    )
    run_profile(workload_config)


if __name__ == '__main__':
    main()
