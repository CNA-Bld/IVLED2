from config import REDIS_HOST, REDIS_PORT, REDIS_DB

import redis
import pickle

r = redis.Redis(REDIS_HOST, REDIS_PORT, REDIS_DB)

PREFIX = 'IVLED2:'

PREFIX_USER = PREFIX + 'USER:'
SET_NAME_USER = PREFIX + 'USERS'

PREFIX_FILE = PREFIX + 'FILE:'


def set_value(key, value):
    r.set(key, pickle.dumps(value))


def get_value(key):
    pickled_value = r.get(key)
    if pickled_value is None:
        return None
    return pickle.loads(pickled_value)


def get_user_dict(user_id):
    return get_value(PREFIX_USER + user_id)


def update_user(user):
    add_user_to_set(user.user_id)
    return set_value(PREFIX_USER + user.user_id, user.to_dict())


def get_users():
    return r.smembers(SET_NAME_USER)


def add_user_to_set(user_id):
    return r.sadd(SET_NAME_USER, user_id)
