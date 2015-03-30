import requests
import utils.misc

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
        raise Exception()  # TODO
    modules_list = []
    for module in request.json()['Results']:
        modules_list.append({x: module[x] for x in ['CourseCode', 'ID']})
    return modules_list


def validate_token(user):
    try:
        result = requests.get('https://ivle.nus.edu.sg/api/Lapi.svc/Validate?APIKey=%s&Token=%s' % (IVLE_APIKEY, user.ivle_token)).json()
    except:
        return True  # TODO: IVLE API Bug Here
    if result['Success']:
        return True
    else:
        return False


def parse_folder(user, folder, father_directory):
    file_list = []
    father_directory = father_directory.strip()
    if (not folder['AllowUpload']) or user.uploadable_folder:
        if len(folder['Files']) > 0:  # There do exist folders containing both files and folders.
            for single_file in folder['Files']:
                if not (utils.misc.is_ignored_file(single_file['FileName'])):
                    file_list.append({'path': father_directory + folder['FolderName'].strip(' .') + '/' + single_file['FileName'],
                                      'ID': single_file['ID']})
        if len(folder['Folders']) > 0:
            for single_folder in folder['Folders']:
                file_list.extend(parse_folder(user, single_folder, father_directory + folder['FolderName'].strip(' .') + '/'))
    return file_list


def read_file_list(user, CourseCode, CourseID):
    data = requests.get('https://ivle.nus.edu.sg/api/Lapi.svc/Workbins?APIKey=%s&AuthToken=%s&CourseID=%s&Duration=0&WorkbinID=&TitleOnly=false' % (
        IVLE_APIKEY, user.ivle_token, CourseID)).json()
    file_list = []
    if len(data['Results']) > 1:  # We treat modules with one or more workbins differently because we do not want to merge files in different workbins.
        for workbin in data['Results']:
            if len(workbin['Folders']) > 0:  # It is not allowed to have files in the root directory of a workbin.
                for folder in workbin['Folders']:
                    file_list.extend(parse_folder(user, folder, '/%s/%s/' % (
                        utils.misc.module_code_safe_check(CourseCode), utils.misc.module_code_safe_check(workbin['Title']).strip(' .'))))
    elif len(data['Results']) == 1:
        workbin = data['Results'][0]
        if len(workbin['Folders']) > 0:
            for folder in workbin['Folders']:
                file_list.extend(parse_folder(user, folder, '/%s/' % utils.misc.module_code_safe_check(CourseCode)))
    return file_list


def read_all_file_list(user):
    file_list = []
    for module in user.modules:
        file_list.extend(read_file_list(user, module['Code'], module['ID']))
    return file_list


def get_file_url(user, file_id):
    return "https://ivle.nus.edu.sg/api/downloadfile.ashx?APIKey=%s&AuthToken=%s&ID=%s&target=workbin" % (IVLE_APIKEY, user.ivle_token, file_id)


class IVLEUnknownErrorException(BaseException):
    pass


def get_file(url):
    request = requests.get(url)
    if request.headers['Content-Type'] == 'text/html' and 'Your actions have caused an error' in request.content:
        raise IVLEUnknownErrorException()  # TODO: IVLE Bug
    elif request.status_code == 200:
        return request.content
    else:
        raise IVLEUnknownErrorException()  # TODO: A lot of IVLE Bugs
