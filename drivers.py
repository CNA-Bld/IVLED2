import dropbox
from api import ivle


class SyncException(BaseException):
    # Retry means to not give up. It is not guaranteed that will immediately retry - will after a while.
    # If retry is False during transferring file we will give up that file and never try again.
    # If disable_user is True we will disable the user until he manually re-enable it.
    def __init__(self, message, retry=False, send_email=False, disable_user=False):
        self.retry = retry
        self.send_email = send_email
        self.disable_user = disable_user
        self.message = message
        super()


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


class NullDriver(BaseDriver):
    @classmethod
    def check_settings(cls, user_settings):
        raise SyncException("You have not selected a target service.", retry=False, send_email=True, disable_user=True)

    @classmethod
    def transport_file(cls, user_settings, file_url, target_path):
        raise SyncException("You have not selected a target service.", retry=False, send_email=True, disable_user=True)


class DropboxDriver(BaseDriver):
    @classmethod
    def check_settings(cls, user_settings):
        if not user_settings['token']:
            raise SyncException("You are not logged in to Dropbox or your token is expired.", retry=False, send_email=True, disable_user=True)
        if not user_settings['folder']:
            raise SyncException("You have not set your target folder.", retry=False, send_email=True, disable_user=True)
        try:
            dropbox_client = dropbox.client.DropboxClient(user_settings['token'])
            if dropbox_client.account_info():
                return True
        except dropbox.rest.ErrorResponse as e:
            if e.status == 401:
                raise SyncException("You are not logged in to Dropbox or your token is expired.", retry=False, send_email=True, disable_user=True)
            return False  # TODO

    @classmethod
    def transport_file(cls, user_settings, file_url, target_path):
        if not cls.check_settings(user_settings):
            return  # TODO
        try:
            dropbox_client = dropbox.client.DropboxClient(user_settings['token'])
            dropbox_client.put_file(target_path, ivle.get_file(file_url), overwrite=False)
        except dropbox.rest.ErrorResponse as e:
            if e.status == 401:
                raise SyncException("You are not logged in to Dropbox or your token is expired.", retry=True, send_email=True, disable_user=True)
            return False  # TODO


drivers = {'dropbox': DropboxDriver, '': NullDriver, None: NullDriver}

