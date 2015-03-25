import config

from flask import Flask, render_template, redirect, session, request, url_for, get_flashed_messages, flash, abort

from api import ivle
import dropbox

import models

app = Flask(__name__)


@app.route("/")
def index():
    return render_template('index.html')


@app.route("/dashboard/")
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user = models.User(session['user_id'])
    selected_modules = ', '.join(sorted([course['Code'] for course in user.modules])) or 'None'
    return render_template('dashboard.html', selected_modules=selected_modules, target=user.target, target_settings=user.target_settings,
                           DROPBOX_APPKEY=config.DROPBOX_APPKEY, user_id=user.user_id, key=user.key, sync_enabled=user.enabled,
                           uploadable_folder=user.uploadable_folder)
    # return 'Logged in as %s' % session['user_id']


@app.route("/modules/")
def modules():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user = models.User(session['user_id'])
    mods = ivle.get_modules_list(user)
    selected_modules = [course['Code'] for course in user.modules]
    return render_template('modules.html', modules=mods, selected_modules=selected_modules)


@app.route("/modules/submit/", methods=['POST'])
def modules_submit():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user = models.User(session['user_id'])
    courses = []
    for course in request.form:
        course_code, course_id = str(course).split('|')
        courses.append({'Code': course_code, 'ID': course_id})
    user.modules = courses
    user.update()
    return ""


@app.route("/modules/get/")
def modules_get():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user = models.User(session['user_id'])
    selected_modules = ', '.join(sorted([course['Code'] for course in user.modules])) or 'None'
    return selected_modules


@app.route("/settings/submit/", methods=['POST'])
def settings_submit():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user = models.User(session['user_id'])
    user.enabled = bool(request.form.get('sync_enabled', ''))
    user.uploadable_folder = bool(request.form.get('uploadable_folder', ''))
    user.update()
    return ''


# Target: Dropbox

def get_dropbox_auth_flow():
    redirect_uri = url_for('auth_dropbox_callback', _external=True, _scheme='https')
    return dropbox.client.DropboxOAuth2Flow(config.DROPBOX_APPKEY, config.DROPBOX_APPSECRET, redirect_uri,
                                            session, 'dropbox-auth-csrf-token')


@app.route("/auth/dropbox/")
def auth_dropbox():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user = models.User(session['user_id'])
    redirect_uri = get_dropbox_auth_flow().start()
    session['dropbox-auth-csrf-token'] = str(session['dropbox-auth-csrf-token'])  # Temporary walkaround for Dropbox SDK Bug on 3.x
    return redirect(redirect_uri)


@app.route("/auth/dropbox/callback/")
def auth_dropbox_callback():
    if 'user_id' not in session:
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
    user.target = 'dropbox'
    user.target_settings = {'token': access_token, 'folder': ''}
    user.update()
    flash('Successfully logged in to Dropbox as %s' % dropbox.client.DropboxClient(user.target_settings['token']).account_info()['display_name'], 'info')
    return redirect(url_for('dashboard'))


@app.route("/auth/dropbox/logout/")
def auth_dropbox_unauth():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user = models.User(session['user_id'])
    user.target = None
    user.target_settings = {}
    user.update()
    flash('Successfully logged out from Dropbox.', 'warning')
    return redirect(url_for('dashboard'))


@app.route("/internal/dropbox/folder/")
def dropbox_folder():
    user = models.User(request.args.get('user_id', ''))
    if request.args.get('key', '') != user.key:
        return "Unauthorized!", 403  # TODO
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
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user = models.User(session['user_id'])
    dropbox_client = dropbox.client.DropboxClient(user.target_settings['token'])
    file_list = dropbox_client.search('/', '.Your_Workbin_Files')
    if file_list:
        new_path = file_list[0]['path']
        user.target_settings['folder'] = new_path[:new_path.rfind('/') + 1]
        user.update()
        dropbox_client.file_delete(new_path)
        return user.target_settings['folder']
    else:
        return "[Unknown Error, Please Retry]"  # TODO


# End of Dropbox


# Target: Google Drive
@app.route("/auth/google/")
def auth_google():
    pass


# End of Google Drive

# Target: OneDrive
@app.route("/auth/onedrive/")
def auth_onedrive():
    pass


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
