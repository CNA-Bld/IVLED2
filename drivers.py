import dropbox


class BaseDriver():
    # Drivers should do error handling here. Throw an Exception to trigger an email being sent to the user.
    @classmethod
    def check_settings(cls, user_settings):
        return True

    # Error handling here. Return True if transfer succeeded. Return False if a retry is needed.
    # Throw an Exception to trigger an email being sent to the user.
    @classmethod
    def transport_file(cls, user_settings, file_url, target_path):
        return True


class DropboxDriver(BaseDriver):
    @classmethod
    def check_settings(cls, user_settings):
        if not user_settings['token'] or not user_settings['folder']:
            return False
        try:
            dropbox_client = dropbox.client.DropboxClient(user_settings['token'])
            if dropbox_client.account_info():
                return True
        except:
            return False  # TODO


drivers = {'dropbox': DropboxDriver}

