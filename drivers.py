import dropbox
import httplib2
from io import BytesIO
from oauth2client import client
import apiclient
from api import ivle
from utils.misc import get_mime_type
from config import GLOBAL_MAX_FILE_SIZE


class SyncException(Exception):
    # If retry is False during transferring file we will give up that file and never try again.
    # retry is ignored during user checking - i.e. unless it is never going to success, always set to True.
    # If disable_user is True we will disable the user until he manually re-enable it.
    def __init__(self, message, retry=True, send_email=False, disable_user=False, logout_user=False):
        self.retry = retry
        self.send_email = send_email
        self.disable_user = disable_user
        self.logout_user = logout_user
        self.message = message
        super()


class BaseDriver():
    MAX_FILE_SIZE = GLOBAL_MAX_FILE_SIZE

    # Drivers should do error handling here. Throw an Exception to trigger an email being sent to the user.
    # Should NEVER return False, raise an exception if something is wrong!
    @classmethod
    def check_settings(cls, user_settings):
        return True

    # Error handling here. Return True if transfer succeeded. Return False if a retry is needed.
    # Throw an Exception to trigger an email being sent to the user.
    # But except IVLEUnknownErrorException, which will be handled differently.
    # Should NEVER return False, raise an exception if something is wrong!
    @classmethod
    def transport_file(cls, user_settings, file_url, target_path):
        return True


class NullDriver(BaseDriver):
    @classmethod
    def check_settings(cls, user_settings):
        raise SyncException("You have not selected a target service.", retry=True, send_email=True, disable_user=True, logout_user=False)

    @classmethod
    def transport_file(cls, user_settings, file_url, target_path):
        raise SyncException("You have not selected a target service.", retry=True, send_email=True, disable_user=True, logout_user=False)


class DropboxDriver(BaseDriver):
    @classmethod
    def check_settings(cls, user_settings):
        if not user_settings['token']:
            raise SyncException("You are not logged in to Dropbox or your token is expired. Please re-login on the webpage.", retry=True, send_email=True,
                                disable_user=True, logout_user=True)
        if not user_settings['folder']:
            raise SyncException("You have not set your target folder.", retry=True, send_email=True, disable_user=True, logout_user=False)
        try:
            dropbox_client = dropbox.client.DropboxClient(user_settings['token'])
            if dropbox_client.account_info():
                return True
        except dropbox.rest.ErrorResponse as e:
            if e.status == 401:
                raise SyncException("You are not logged in to Dropbox or your token is expired. Please re-login on the webpage.", retry=True, send_email=True,
                                    disable_user=True, logout_user=True)
            raise e

    @classmethod
    def transport_file(cls, user_settings, file_url, target_path):
        if not cls.check_settings(user_settings):
            return  # Should never reach
        try:
            dropbox_client = dropbox.client.DropboxClient(user_settings['token'])
            file_data = dropbox_client.put_file(user_settings['folder'] + target_path, ivle.get_file(file_url),
                                                parent_rev=user_settings['files_revision'].get(target_path, ''))
            user_settings['files_revision'][target_path] = file_data['revision']
            return True
        except dropbox.rest.ErrorResponse as e:
            if e.status == 401:
                raise SyncException("You are not logged in to Dropbox or your token is expired. Please re-login on the webpage.", retry=True, send_email=True,
                                    disable_user=True, logout_user=True)
            elif e.status == 400:
                raise SyncException(e.error_msg, retry=True, send_email=False, disable_user=False, logout_user=False)
            elif e.status == 503:
                raise SyncException(
                    "Dropbox says you are over quota. We have temporarily disabled syncing for you. Please manually re-enable after cleaning up some files.",
                    retry=True, send_email=True,
                    disable_user=True, logout_user=False)
            raise e


class GoogleDriver(BaseDriver):
    @classmethod
    def check_settings(cls, user_settings):
        if not user_settings['credentials']:
            raise SyncException("You are not logged in to Google Drive or your token is expired. Please re-login on the webpage.", retry=True, send_email=True,
                                disable_user=True, logout_user=True)
        if not user_settings['parent_id']:
            raise SyncException("You have not set your target folder.", retry=True, send_email=True, disable_user=True, logout_user=False)
        try:
            service = cls.get_drive_client(user_settings)
            if cls.get_folder_name(service, user_settings['parent_id']):
                return True
        except client.AccessTokenRefreshError as e:
            raise SyncException("You are not logged in to Google Drive or your token is expired. Please re-login on the webpage.", retry=True, send_email=True,
                                disable_user=True, logout_user=True)
        except apiclient.errors.HttpError as e:
            raise SyncException(str(e), retry=True, send_email=False, disable_user=False, logout_user=False)
        except Exception as e:
            raise SyncException("Something might go wrong with your Google Drive settings. If you are not able to find the error, please inform the developer.",
                                retry=True, send_email=True, disable_user=True, logout_user=False)

    @classmethod
    def transport_file(cls, user_settings, file_url, target_path):
        if not cls.check_settings(user_settings):
            return  # Should never reach
        try:
            service = cls.get_drive_client(user_settings)
            path_id = cls.find_path(service, user_settings['parent_id'], target_path.split('/')[1:-1])
            media_body = apiclient.http.MediaIoBaseUpload(BytesIO(ivle.get_file(file_url)), mimetype=get_mime_type(target_path), resumable=True)
            body = {'title': target_path[target_path.rfind('/') + 1:], 'parents': [{'id': path_id}]}
            file = service.files().insert(body=body, media_body=media_body).execute()
            return bool(file['id'])
        except client.AccessTokenRefreshError as e:
            raise SyncException("You are not logged in to Google Drive or your token is expired. Please re-login on the webpage.", retry=True, send_email=True,
                                disable_user=True, logout_user=True)
        except apiclient.errors.HttpError as e:
            raise SyncException(str(e), retry=True, send_email=False, disable_user=False, logout_user=False)
        except Exception as e:
            raise SyncException("Something might go wrong with your Google Drive settings. If you are not able to find the error, please inform the developer.",
                                retry=True, send_email=True, disable_user=True, logout_user=False)

    @classmethod
    def find_path(cls, service, base_path_id, path):
        if not path:
            return base_path_id
        page_token = None
        while True:
            param = {}
            if page_token:
                param['pageToken'] = page_token
            children = service.children().list(folderId=base_path_id, **param).execute()
            for child in children.get('items', []):
                file = service.files().get(fileId=child['id']).execute()
                if file['mimeType'] == "application/vnd.google-apps.folder" and file['title'] == path[0]:
                    return cls.find_path(service, child['id'], path[1:])
            page_token = children.get('nextPageToken')
            if not page_token:
                body = {
                    'title': path[0],
                    "parents": [{"id": base_path_id}],
                    "mimeType": "application/vnd.google-apps.folder",
                }
                file = service.files().insert(body=body).execute()
                return cls.find_path(service, file['id'], path[1:])


    @classmethod
    def get_drive_client(cls, user_settings):
        if not user_settings['credentials']:
            raise SyncException("You are not logged in to Google Drive or your token is expired. Please re-login on the webpage.", retry=True, send_email=True,
                                disable_user=True, logout_user=True)
        credentials = client.OAuth2Credentials.from_json(user_settings['credentials'])
        http_auth = credentials.authorize(httplib2.Http())
        return apiclient.discovery.build('drive', 'v2', http=http_auth)

    @classmethod
    def get_folder_name(cls, service, folder_id):
        file = service.files().get(fileId=folder_id).execute()
        return file['title']


drivers = {'dropbox': DropboxDriver, 'google': GoogleDriver, '': NullDriver, None: NullDriver}

