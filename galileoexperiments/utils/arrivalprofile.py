import pickle

import redis
from galileo.worker.api import ClientDescription


def clear_list(list_key: str, rds: redis.Redis):
    while rds.llen(list_key) != 0:
        rds.lpop(list_key)


def read_and_save_profile(profile_path: str, client_desc: ClientDescription, rds: redis.Redis):
    with open(profile_path, 'rb') as fd:
        ias = pickle.load(fd)
        for index, ia in enumerate(ias):
            if ia == 0:
                # prevents of using 0 because it may lead to crash
                ias[index] = 0.00000000001
        list_key = client_desc.client_id
        print('clear list')
        clear_list(list_key, rds)
        print('list cleared, start push')
        rds.lpush(list_key, *ias[0:])
        llen = rds.llen(list_key)
        print('pushed list')
