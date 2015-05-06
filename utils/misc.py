import mimetypes, random, string

def module_code_safe_check(module_code):  # TODO: All these safe check functions are dangerous.
    return module_code.replace('/', '_')


def is_ignored_file(filename):
    return filename.find('~$') == 0


def get_mime_type(filename):
    return mimetypes.guess_type(filename[filename.rfind('/')+1:])[0] or 'application/octet-stream'


def generate_random_string(length):
    return ''.join(random.SystemRandom().choice(string.ascii_letters + string.digits) for _ in range(length))

