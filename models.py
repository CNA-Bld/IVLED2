from utils import db, misc
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
            self.last_target = None
            self.target_settings = {}
            self.synced_files = []
            self.key = misc.generate_random_string(16)
            self.update()

    def update_ivle_token(self, new_token):
        with self.lock:
            self.sync_from_db()
            self.ivle_token = new_token
            self.update()

    def unauth_target(self, clear_synced_files=True):
        with self.lock:
            self.sync_from_db()
            self.last_target = None  # This should always be manually called by user so no need to save last_target
            self.target = None
            if clear_synced_files:
                self.synced_files = []
            self.enabled = False
            self.update()

    def to_dict(self):
        return self.__dict__

    def sync_from_db(self):
        self.__dict__.update(db.get_user_dict(self.user_id))

    def update(self):
        db.update_user(self)

    def generate_emergency_code(self):
        return db.generate_user_emergency(self.user_id)

    def check_emergency_code(self, auth_code):
        return db.check_user_emergency(self.user_id, auth_code)

    @classmethod
    def user_exists(cls, user_id):
        return bool(db.get_user_dict(user_id))
