import rq

import models
from utils import db
from utils import mail
from config import *
from drivers import drivers
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
    if user.enabled and drivers[user.target].check_settings(user.target_settings):
        file_list = api.ivle.read_all_file_list(user)
        for file in file_list:
            if file['ID'] not in user.synced_files and not file_queue.fetch_job('%s:%s' % (user_name, file['ID'])):
                file_queue.enqueue_call(func=do_file, args=(user_name, file['ID'], file['path']), job_id='%s:%s' % (user_name, file['ID']))
    else:
        user.enabled = False
        user.update()
        # TODO


def do_file(user_name, file_id, file_path):
    user = models.User(user_name)
    url = api.ivle.get_file_url(user, file_id)
    if user.enabled and drivers[user.target].check_settings(user.target_settings):
        if drivers[user.target].transport_file(user.target_settings, url, file_path):
            user.synced_files.append(file_id)
            user.update()
        else:
            file_queue.enqueue_call(func=do_file, args=(user_name, file_id, file_path), job_id='%s:%s' % (user_name, file_id))
    else:
        user.enabled = False
        user.update()

# queue_all_user()
