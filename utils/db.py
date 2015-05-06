from config import REDIS_HOST, REDIS_PORT, REDIS_DB
from utils.misc import generate_random_string

import redis
import pickle

r = redis.Redis(REDIS_HOST, REDIS_PORT, REDIS_DB)

PREFIX = 'IVLED2:'

PREFIX_USER = PREFIX + 'USER:'
SET_NAME_USER = PREFIX + 'USERS'

PREFIX_EMERGENCY_LOGIN = PREFIX + 'EMERGENCY:'


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
    d = user.to_dict().copy()
    d.pop('lock', None)
    return set_value(PREFIX_USER + user.user_id, d)


def get_users():
    return r.smembers(SET_NAME_USER)


def add_user_to_set(user_id):
    return r.sadd(SET_NAME_USER, user_id)


def generate_user_emergency(user_id):
    authcode = generate_random_string(32)
    key = PREFIX_EMERGENCY_LOGIN + user_id
    r.set(key, authcode)
    r.expire(key, 1800)
    return authcode


def check_user_emergency(user_id, authcode):
    key = PREFIX_EMERGENCY_LOGIN + user_id
    if r.get(key):
        if authcode.encode('ascii') == r.get(key):
            r.delete(key)
            return True
        else:
            return False
    else:
        return False
