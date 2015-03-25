import models
from utils import db
from utils import mail
import rq
import requests
from config import *
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
    file_list = api.ivle.read_all_file_list(user)
    for file in file_list:
        if file['ID'] not in user.synced_files and not file_queue.fetch_job('%s:%s' % (user_name, file['ID'])):
            file_queue.enqueue_call(func=do_file, args=(user_name, file['ID']), job_id='%s:%s' % (user_name, file['ID']))


def do_file(user_name, file_id):
    user = models.User(user_name)
    url = api.ivle.get_file_url(user, file_id)
    if user.target == 'dropbox':
        pass

# queue_all_user()
