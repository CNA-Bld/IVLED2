def module_code_safe_check(module_code):  # TODO: All these safe check functions are dangerous.
    return module_code.replace('/', '_')


def is_ignored_file(filename):
    return filename.find('~$') == 0
