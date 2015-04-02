import rq

import models
from utils import db
from utils import mail
from config import *
from drivers import drivers, SyncException
import api.ivle

user_queue = rq.Queue('user', connection=db.r)
file_queue = rq.Queue('file', connection=db.r)


def queue_all_user():
    for user_name in db.get_users():
        user_name = user_name.decode("utf-8")
        if models.User(user_name).enabled and (not user_queue.fetch_job(user_name) or user_queue.fetch_job(user_name).status == 'finished'):
            user_queue.enqueue_call(func=do_user, args=(user_name,), job_id=user_name)
    user_queue.enqueue_call(func=queue_all_user, job_id='METAJOB')


def do_user(user_name):
    user = models.User(user_name)
    try:
        if not (user.enabled and drivers[user.target].check_settings(user.target_settings)):
            return  # TODO: Should not come here
    except SyncException as e:
        if e.disable_user:
            user.acquire_lock()
            user.enabled = False
            user.update()
            user.release_lock()
        if e.send_email:
            pass  # TODO: Handler not ready yet.
        return
    except Exception as e:
        return  # TODO: Inform admin

    try:
        if not api.ivle.validate_token(user):
            pass  # TODO: Handler not ready yet, should send email
    except Exception as e:
        return  # TODO

    try:
        file_list = api.ivle.read_all_file_list(user)
    except Exception as e:  # TODO: Should be Json Parsing Exception & Network Exception - not ready yet
        return

    for file in file_list:
        if file['ID'] not in user.synced_files and not file_queue.fetch_job('%s:%s' % (user_name, file['ID'])):
            file_queue.enqueue_call(func=do_file, args=(user_name, file['ID'], file['path']), job_id='%s:%s' % (user_name, file['ID']))


def do_file(user_name, file_id, file_path):
    user = models.User(user_name)
    url = api.ivle.get_file_url(user, file_id)
    if file_id in user.synced_files:
        return  # TODO
    try:
        if not (user.enabled and drivers[user.target].check_settings(user.target_settings)):
            pass
    except SyncException as e:
        if e.disable_user:
            user.acquire_lock()
            user.enabled = False
            user.update()
            user.release_lock()
        if e.send_email:
            pass  # TODO: Handler not ready yet.
        return
    except Exception as e:
        pass  # TODO: Inform admin

    try:
        drivers[user.target].transport_file(user.target_settings, url, file_path)
        user.acquire_lock()
        user.synced_files.append(file_id)
        user.update()
        user.release_lock()
    except SyncException as e:
        if not e.retry:
            user.acquire_lock()
            user.synced_files.append(file_id)
            user.update()
            user.release_lock()
        if e.send_email:
            pass  # TODO: Handler not ready yet.
        if e.disable_user:
            user.acquire_lock()
            user.enabled = False
            user.update()
            user.release_lock()
        return
        # file_queue.enqueue_call(func=do_file, args=(user_name, file_id, file_path), job_id='%s:%s' % (user_name, file_id))
    except api.ivle.IVLEUnknownErrorException as e:
        return  # TODO: Walao eh IVLE bug again
    except Exception as e:
        return  # TODO: inform admin

# queue_all_user()
