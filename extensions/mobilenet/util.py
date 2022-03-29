import base64
import time
from typing import List

import redis
import requests
from galileo.shell.shell import Galileo, ClientGroup

from galileoexperiments.utils.arrivalprofile import clear_list, read_and_save_profile


def spawn_zone_group(zone: str, clients: int, g: Galileo, image_url: str) -> ClientGroup:
    return spawn_group(g, clients, f'mobilenet-{zone}', image_url=image_url, labels={'galileo_zone': zone})


def spawn_group(g: Galileo, clients: int, service_name: str, image_url: str, labels: dict = None):
    path = f'/function/mobilenet'
    return g.spawn(service_name, clients,
                   parameters={'method': 'post', 'path': path, 'kwargs': {'data': get_image(image_url)}},
                   worker_labels=labels)


def prepare_image(url: str):
    r = requests.get(url)
    r.raise_for_status()
    return base64.b64encode(r.content).decode('utf-8')


def get_image(url: str) -> str:
    data = prepare_image(url)
    return '{"picture": "%s"}' % data


def spawn_client_group(profile_paths: List[str], zone: str, rds: redis.Redis, galileo: Galileo, image_url: str):
    c = spawn_zone_group(zone, len(profile_paths), galileo, image_url)
    time.sleep(1)
    for index, client in enumerate(c.clients):
        profile_path = profile_paths[index]
        clear_list(client.client_id, rds)
        read_and_save_profile(profile_path, client, rds)
    return c
