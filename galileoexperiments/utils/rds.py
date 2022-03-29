import redis


def wait_for_galileo_events(rds: redis.Redis):
    p = rds.pubsub( ignore_subscribe_messages=True)
    p.subscribe('galileo/events')
    for _ in p.listen():
        return
