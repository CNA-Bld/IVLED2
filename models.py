from utils import db
import random
import string
import redis_lock


class User():
    def __init__(self, user_id, user_email=None):
        self.user_id = user_id
        self.lock = redis_lock.Lock(db.r, user_id)
        if db.get_user_dict(user_id):
            self.__dict__.update(db.get_user_dict(user_id))
        else:
            self.email = user_email
            self.ivle_token = ''
            self.modules = []
            self.enabled = False
            self.uploadable_folder = False
            self.target = None
            self.target_settings = {}
            self.synced_files = []
            self.key = ''.join(random.SystemRandom().choice(string.ascii_letters + string.digits) for _ in range(16))
            self.update()

    def update_ivle_token(self, new_token):
        self.acquire_lock()
        self.ivle_token = new_token
        self.update()
        self.release_lock()

    def unauth_target(self, clear_synced_files=True):
        self.acquire_lock()
        self.target = None
        self.target_settings = {}
        if clear_synced_files:
            self.synced_files = []
        self.enabled = False
        self.update()
        self.release_lock()

    def to_dict(self):
        return self.__dict__

    def acquire_lock(self):
        self.lock.acquire(True)
        self.__dict__.update(db.get_user_dict(self.user_id))

    def release_lock(self):
        self.lock.release()

    def update(self):
        db.update_user(self)
