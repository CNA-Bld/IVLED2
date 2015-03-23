from utils import db


class User():
    def __init__(self, user_id, user_email=None):
        self.user_id = user_id
        if db.get_user_dict(user_id):
            self.__dict__.update(db.get_user_dict(user_id))
        else:
            self.email = user_email
            self.ivle_token = ''
            self.dropbox_token = ''
            self.modules = []
            self.folder = ''
            self.enabled = False
            self.uploadable_folder = False
            self.completed_wizard = False
            self.update()

    def update_ivle_token(self, new_token):
        self.ivle_token = new_token
        self.update()

    def update_dropbox_token(self, new_token):
        self.dropbox_token = new_token
        self.update()

    def to_dict(self):
        return self.__dict__

    def update(self):
        db.update_user(self)

