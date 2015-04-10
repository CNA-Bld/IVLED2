import config

from flask import Flask, render_template, redirect, session, request, url_for, get_flashed_messages, flash, abort
import json

from api import ivle
import dropbox
from oauth2client.client import OAuth2WebServerFlow

import models
import drivers

app = Flask(__name__)


@app.route("/")
def index():
    return render_template('index.html')


@app.route("/dashboard/")
def dashboard():
    if 'user_id' not in session or session['user_id'] == '':
        return redirect(url_for('login'))
    user = models.User(session['user_id'])
    selected_modules = ', '.join(sorted([course['Code'] for course in user.modules])) or 'None'
    return render_template('dashboard.html', selected_modules=selected_modules, target=user.target, target_settings=user.target_settings,
                           DROPBOX_APPKEY=config.DROPBOX_APPKEY, user_id=user.user_id, key=user.key, sync_enabled=user.enabled,
                           uploadable_folder=user.uploadable_folder, email=user.email)
    # return 'Logged in as %s' % session['user_id']


@app.route("/modules/")
def modules():
    if 'user_id' not in session or session['user_id'] == '':
        return redirect(url_for('login'))
    user = models.User(session['user_id'])
    mods = ivle.get_modules_list(user)
    selected_modules = [course['Code'] for course in user.modules]
    return render_template('modules.html', modules=mods, selected_modules=selected_modules)


@app.route("/modules/submit/", methods=['POST'])
def modules_submit():
    if 'user_id' not in session or session['user_id'] == '':
        return redirect(url_for('login'))
    user = models.User(session['user_id'])
    courses = []
    for course in request.form:
        course_code, course_id = str(course).split('|')
        courses.append({'Code': course_code, 'ID': course_id})
    with user.lock:
        user.sync_from_db()
        user.modules = courses
        user.update()
    return ""


@app.route("/modules/get/")
def modules_get():
    if 'user_id' not in session or session['user_id'] == '':
        return redirect(url_for('login'))
    user = models.User(session['user_id'])
    selected_modules = ', '.join(sorted([course['Code'] for course in user.modules])) or 'None'
    return selected_modules


@app.route("/settings/submit/", methods=['POST'])
def settings_submit():
    if 'user_id' not in session or session['user_id'] == '':
        return redirect(url_for('login'))
    user = models.User(session['user_id'])
    with user.lock:
        user.sync_from_db()
        try:
            user.enabled = bool(request.form.get('sync_enabled', ''))
            if (not user.enabled) or (drivers.drivers[user.target].check_settings(user.target_settings)):
                user.uploadable_folder = bool(request.form.get('uploadable_folder', ''))
                user.email = request.form.get('email', user.email)
                user.update()
                return json.dumps({'result': True})
            else:  # TODO: Should never reach
                user.enabled = False
                user.update()
                return json.dumps({'result': False, 'message': 'An unknown error happened. Please refresh the page and try again.'})
        except drivers.SyncException as e:
            user.enabled = False
            user.uploadable_folder = bool(request.form.get('uploadable_folder', ''))
            user.email = request.form.get('email', user.email)
            user.update()
            return json.dumps({'result': False, 'message': e.message})


# Target: Dropbox

def get_dropbox_auth_flow():
    redirect_uri = url_for('auth_dropbox_callback', _external=True, _scheme='https')
    return dropbox.client.DropboxOAuth2Flow(config.DROPBOX_APPKEY, config.DROPBOX_APPSECRET, redirect_uri,
                                            session, 'dropbox-auth-csrf-token')


@app.route("/auth/dropbox/")
def auth_dropbox():
    if 'user_id' not in session or session['user_id'] == '':
        return redirect(url_for('login'))
    user = models.User(session['user_id'])
    redirect_uri = get_dropbox_auth_flow().start()
    session['dropbox-auth-csrf-token'] = str(session['dropbox-auth-csrf-token'])  # Temporary walkaround for Dropbox SDK Bug on 3.x
    return redirect(redirect_uri)


@app.route("/auth/dropbox/callback/")
def auth_dropbox_callback():
    if 'user_id' not in session or session['user_id'] == '':
        return redirect(url_for('login'))
    user = models.User(session['user_id'])
    try:
        access_token, user_id, url_state = get_dropbox_auth_flow().finish(request.args)
    except dropbox.client.DropboxOAuth2Flow.BadRequestException:
        abort(400)
    except dropbox.client.DropboxOAuth2Flow.BadStateException:
        abort(400)
    except dropbox.client.DropboxOAuth2Flow.CsrfException:
        abort(403)
    except dropbox.client.DropboxOAuth2Flow.NotApprovedException:
        flash('Not approved?', 'warning')
        return redirect(url_for('dashboard'))
    except dropbox.client.DropboxOAuth2Flow.ProviderException as e:
        app.logger.exception("Auth error" + str(e))
        abort(403)
    with user.lock:
        user.sync_from_db()
        user.target = 'dropbox'
        if user.last_target != 'dropbox':
            user.target_settings = {'token': access_token, 'folder': '', 'files_revision': {}}
            flash('Successfully logged in to Dropbox as %s' % dropbox.client.DropboxClient(user.target_settings['token']).account_info()['display_name'], 'info')
        else:
            user.target_settings['token'] = access_token
            flash('Successfully refreshed token for Dropbox user %s' % dropbox.client.DropboxClient(user.target_settings['token']).account_info()['display_name'],
                  'info')
        user.update()
    return redirect(url_for('dashboard'))


@app.route("/auth/dropbox/logout/")
def auth_dropbox_unauth():
    if 'user_id' not in session or session['user_id'] == '':
        return redirect(url_for('login'))
    user = models.User(session['user_id'])
    user.unauth_target(True)
    flash('Successfully logged out from Dropbox.', 'warning')
    return redirect(url_for('dashboard'))


@app.route("/internal/dropbox/folder/")
def dropbox_folder():
    user_id = request.args.get('user_id', '')
    if not user_id:
        return "Unauthorized!", 403
    user = models.User(user_id)
    if request.args.get('key', '') != user.key:
        return "Unauthorized!", 403
    dropbox_client = dropbox.client.DropboxClient(user.target_settings['token'])
    try:
        file_list = dropbox_client.search('/', '.Your_Workbin_Files')
        for file in file_list:
            dropbox_client.file_delete(file['path'])
    except:
        pass  # TODO
    return ""


@app.route("/internal/dropbox/update_folder/")
def dropbox_update_folder():
    if 'user_id' not in session or session['user_id'] == '':
        return redirect(url_for('login'))
    user = models.User(session['user_id'])
    dropbox_client = dropbox.client.DropboxClient(user.target_settings['token'])
    file_list = dropbox_client.search('/', '.Your_Workbin_Files')
    if file_list:
        with user.lock:
            user.sync_from_db()
            new_path = file_list[0]['path']
            user.target_settings['folder'] = new_path[:new_path.rfind('/') + 1]
            user.update()
        dropbox_client.file_delete(new_path)
        return user.target_settings['folder']
    else:
        return "[Unknown Error, Please Retry]"  # TODO


# End of Dropbox


# Target: Google Drive
def get_google_auth_flow():
    redirect_uri = url_for('auth_google_callback', _external=True, _scheme='https')
    return OAuth2WebServerFlow(config.GOOGLE_CLIENT_ID, config.GOOGLE_CLIENT_SECRET, config.GOOGLE_OAUTH_SCOPE, redirect_uri=redirect_uri,
                               approval_prompt='force')


@app.route("/auth/google/")
def auth_google():
    if 'user_id' not in session or session['user_id'] == '':
        return redirect(url_for('login'))
    user = models.User(session['user_id'])
    redirect_uri = get_google_auth_flow().step1_get_authorize_url()
    return redirect(redirect_uri)


@app.route("/auth/google/callback/")
def auth_google_callback():
    if 'user_id' not in session or session['user_id'] == '':
        return redirect(url_for('login'))
    user = models.User(session['user_id'])
    code = request.args.get('code', '')
    error = request.args.get('error', '')
    if error:
        flash('Error: ' + error, 'warning')
        return redirect(url_for('dashboard'))
    try:
        credentials = get_google_auth_flow().step2_exchange(code)
        if credentials.invalid:
            flash('Credential Invalid.', 'warning')
            return redirect(url_for('dashboard'))
    except Exception as e:
        flash('Error: ' + str(e), 'warning')
        return redirect(url_for('dashboard'))
    with user.lock:
        user.sync_from_db()
        user.target = 'google'
        if user.last_target != 'google':
            flash('Logged in to Google Drive.', 'info')
            user.target_settings = {'credentials': credentials.to_json(), 'parent_id': ''}
        else:
            flash('Refreshed Google Drive token.', 'info')
            user.target_settings['credentials'] = credentials.to_json()
        user.update()
    return redirect(url_for('dashboard'))


@app.route("/auth/google/logout/")
def auth_google_unauth():
    if 'user_id' not in session or session['user_id'] == '':
        return redirect(url_for('login'))
    user = models.User(session['user_id'])
    user.unauth_target(True)
    flash('Successfully logged out from Google Drive.', 'warning')
    return redirect(url_for('dashboard'))


@app.route("/internal/google/folder_ui/")
def google_folder_ui():
    if 'user_id' not in session or session['user_id'] == '':
        return redirect(url_for('login'))
    user = models.User(session['user_id'])
    return render_template('google_folder_ui.html', user_id=user.user_id, key=user.key)


@app.route("/internal/google/folder/")
def google_folder():
    user_id = request.args.get('user_id', '')
    if not user_id:
        return "Unauthorized!", 403  # TODO
    user = models.User(user_id)
    if request.args.get('key', '') != user.key:
        return "Unauthorized!", 403  # TODO
    try:
        apiclient = drivers.GoogleDriver.get_drive_client(user.target_settings)
        params = {'q': "title = '.Your_Workbin_Files'"}
        files = apiclient.files().list(**params).execute()
        for file in files['items']:
            apiclient.files().delete(fileId=file['id']).execute()
    except:
        pass
    return "0"


@app.route("/internal/google/update_folder/")
def google_update_folder():
    if 'user_id' not in session or session['user_id'] == '':
        return redirect(url_for('login'))
    user = models.User(session['user_id'])
    apiclient = drivers.GoogleDriver.get_drive_client(user.target_settings)
    params = {'q': "title = '.Your_Workbin_Files'"}
    files = apiclient.files().list(**params).execute()
    if len(files['items']) > 0:
        with user.lock:
            user.sync_from_db()
            user.target_settings['parent_id'] = files['items'][0]['parents'][0]['id']
            user.update()
        apiclient.files().delete(fileId=files['items'][0]['id']).execute()
    else:
        pass  # TODO
    return ''


@app.route("/internal/google/get_folder/")
def google_get_folder():
    if 'user_id' not in session or session['user_id'] == '':
        return redirect(url_for('login'))
    user = models.User(session['user_id'])
    if user.target_settings['credentials'] and user.target_settings['parent_id']:
        try:
            apiclient = drivers.GoogleDriver.get_drive_client(user.target_settings)
            result = {'result': True, 'path': drivers.GoogleDriver.get_folder_name(apiclient, user.target_settings['parent_id'])}
        except Exception as e:
            result = {'result': False, 'info': 'Error: ' + str(e)}
    else:
        result = {'result': False, 'info': 'Unknown / Not Set'}
    return json.dumps(result)


# End of Google Drive

# Target: OneDrive
def get_onedrive_auth_flow():
    redirect_uri = url_for('auth_onedrive_callback', _external=True, _scheme='https')
    return OAuth2WebServerFlow(config.ONEDRIVE_CLIENT_ID, config.ONEDRIVE_CLIENT_SECRET, "wl.signin wl.offline_access onedrive.readwrite",
                               redirect_uri=redirect_uri, auth_uri="https://login.live.com/oauth20_authorize.srf",
                               token_uri="https://login.live.com/oauth20_token.srf", revoke_uri="https://login.live.com/oauth20_logout.srf")


@app.route("/auth/onedrive/")
def auth_onedrive():
    if 'user_id' not in session or session['user_id'] == '':
        return redirect(url_for('login'))
    user = models.User(session['user_id'])
    redirect_uri = get_onedrive_auth_flow().step1_get_authorize_url()
    return redirect(redirect_uri)


@app.route("/auth/onedrive/callback/")
def auth_onedrive_callback():
    if 'user_id' not in session or session['user_id'] == '':
        return redirect(url_for('login'))
    user = models.User(session['user_id'])
    code = request.args.get('code', '')
    error = request.args.get('error', '')
    if error:
        flash('Error: ' + error, 'warning')
        return redirect(url_for('dashboard'))
    try:
        credentials = get_onedrive_auth_flow().step2_exchange(code)
        if credentials.invalid:
            flash('Credential Invalid.', 'warning')
            return redirect(url_for('dashboard'))
    except Exception as e:
        flash('Error: ' + str(e), 'warning')
        return redirect(url_for('dashboard'))
    with user.lock:
        user.sync_from_db()
        user.target = 'onedrive'
        if user.last_target != 'onedrive':
            flash('Logged in to OneDrive.', 'info')
            user.target_settings = {'credentials': credentials.to_json(), 'path': ''}
        else:
            flash('Refreshed OneDrive token.', 'info')
            user.target_settings['credentials'] = credentials.to_json()
        user.update()
    return redirect(url_for('dashboard'))


# End of OneDrive


@app.route("/login/")
def login():
    return redirect(ivle.get_ivle_login_url(url_for('login_callback', _external=True, _scheme='https')))


@app.route("/login/callback/")
def login_callback():
    token = request.args.get('token', '')
    user_dict = ivle.get_user_id_and_email(token)
    user = models.User(user_dict['UserID'], user_dict['Email'])
    user.update_ivle_token(token)
    session['user_id'] = user.user_id
    flash('Successfully logged in as %s.' % user.user_id, 'info')
    return redirect(url_for('dashboard'))


@app.route("/logout/")
def logout():
    session.pop('user_id', None)
    return redirect(url_for('index'))


app.secret_key = config.FLASK_SECRET_KEY

if __name__ == '__main__':
    app.run(port=8000, debug=config.DEBUG)
