import requests

from config import IVLE_APIKEY, SERVER_PATH


def get_user_id_and_email(token):
    request = requests.get(
        'https://ivle.nus.edu.sg/api/Lapi.svc/Profile_View?APIKey=%s&AuthToken=%s' % (IVLE_APIKEY, token))
    data = request.json()['Results'][0]
    return {x: data[x] for x in ['UserID', 'Email']}


def get_ivle_login_url(callback_url):
    return "https://ivle.nus.edu.sg/api/login/?apikey=%s&url=%s" % (IVLE_APIKEY, callback_url)


def get_modules_list(user):
    request = requests.get('https://ivle.nus.edu.sg/api/Lapi.svc/Modules_Student?APIKey=%s&AuthToken=%s&Duration=0&IncludeAllInfo=false' % (
                                IVLE_APIKEY, user.ivle_token))
    if request.json()['Comments'] == 'Invalid login!':
        raise Exception  # TODO
    modules_list = []
    for module in request.json()['Results']:
        modules_list.append({x: module[x] for x in ['CourseCode', 'ID']})
    return modules_list
