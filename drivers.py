class BaseDriver():
    @classmethod
    def check_settings(cls, user_settings):
        return True

    @classmethod
    def transport_file(cls, user_settings, file_url, target_path):
        return True


class DropboxDriver(BaseDriver):
    pass


drivers = {'dropbox': DropboxDriver}

