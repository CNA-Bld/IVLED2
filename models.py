from utils import db
import random
import string


class User():
    def __init__(self, user_id, user_email=None):
        self.user_id = user_id
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
        self.ivle_token = new_token
        self.update()

    def to_dict(self):
        return self.__dict__

    def update(self):
        db.update_user(self)
