import rq

import time
import traceback
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
    time.sleep(60)  # TODO: Temporary hard code here
    user_queue.enqueue_call(func=queue_all_user, job_id='METAJOB')


def do_user(user_name):
    user = models.User(user_name)
    try:
        user.acquire_lock()
        if not (user.enabled and drivers[user.target].check_settings(user.target_settings)):
            return  # Drivers should always return True or throw Exception. This means user disabled somewhere, we skip the user.
    except SyncException as e:
        if e.disable_user:
            user.enabled = False
            user.update()
        if e.logout_user:
            user.target = None
            user.update()
        if e.send_email:
            mail.send_error_to_user(user.email, e.message, traceback.format_exc(), locals())
        else:
            mail.send_error_to_admin(traceback.format_exc(), locals())
        return
    except Exception as e:
        mail.send_error_to_admin(traceback.format_exc(), locals())  # TODO
        return
    finally:
        user.release_lock()

    try:
        if not api.ivle.validate_token(user):
            mail.send_email(user.email, 'IVLE Login Expired.', "Your IVLE login has expired. Please refresh by accessing our page and re-enable syncing.")
            user.acquire_lock()
            user.enabled = False
            user.update()
            user.release_lock()
    except Exception as e:
        mail.send_error_to_admin(traceback.format_exc(), locals())  # TODO
        return

    try:
        file_list = api.ivle.read_all_file_list(user)
    except Exception as e:
        mail.send_error_to_admin(traceback.format_exc(), locals())
        return  # TODO: Should be Json Parsing Exception & Network Exception - We skip the user and inform the admin

    for file in file_list:
        if file['ID'] not in user.synced_files and not file_queue.fetch_job('%s:%s' % (user_name, file['ID'])):
            file_queue.enqueue_call(func=do_file, args=(user_name, file['ID'], file['path']), job_id='%s:%s' % (user_name, file['ID']))


def do_file(user_name, file_id, file_path):
    user = models.User(user_name)
    url = api.ivle.get_file_url(user, file_id)
    if file_id in user.synced_files:
        return  # TODO
    try:
        user.acquire_lock()
        if not (user.enabled and drivers[user.target].check_settings(user.target_settings)):
            return  # TODO
        drivers[user.target].transport_file(user.target_settings, url, file_path)
        user.synced_files.append(file_id)
        user.update()
    except SyncException as e:
        if not e.retry:
            user.synced_files.append(file_id)
            user.update()
        if e.send_email:
            mail.send_error_to_user(user.email, e.message, traceback.format_exc(), locals())
        else:
            mail.send_error_to_admin(traceback.format_exc(), locals())
        if e.disable_user:
            user.enabled = False
            user.update()
        if e.logout_user:
            user.target = None
            user.update()
        return
    except api.ivle.IVLEUnknownErrorException as e:
        mail.send_error_to_admin(traceback.format_exc(), locals())
        return  # TODO: Walao eh IVLE bug again, skip it and inform the admin
    except Exception as e:
        mail.send_error_to_admin(traceback.format_exc(), locals())
        return  # TODO: inform admin
    finally:
        user.release_lock()

# queue_all_user()
