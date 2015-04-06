from config import SMTP_SERVER, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, SMTP_FROM, MODULE_VERSION, ADMIN_EMAILS

import gzip, zlib
import base64
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

EXCEPTION_FORMAT = '''An error happened during syncing: %s

Please try to fix the problem at <a href="https://nusync.sshz.org/">https://nusync.sshz.org/</a>.

If you believe that this is an error, please include the following information while contacting the developer:
%s'''

SIGN = '''

This is a system generated email, please do not reply. Please contact support@sshz.org if you have any question.

IVLED2 Module %s
''' % MODULE_VERSION


def get_smtp_client():
    return smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT)


def send_smtp(to, content):
    with get_smtp_client() as smtp:
        smtp.login(SMTP_USER, SMTP_PASSWORD)
        smtp.sendmail(SMTP_USER, to, content)


def prepare_email(to, subject, content):
    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = "%s <%s>" % (SMTP_FROM, SMTP_USER)
    msg['To'] = to
    msg.attach(MIMEText(content, 'plain'))
    msg.attach(MIMEText(content.replace('\n', '<br/>'), 'html'))
    return msg


def send_email(to, subject, content):
    return send_smtp(to, prepare_email(to, 'NUSync: ' + subject, content + SIGN).as_string())


def send_error_to_user(email, message, tb, lcs):
    return send_email(email, 'An Error Happened.', EXCEPTION_FORMAT % (message, compress_traceback(tb, lcs)))


def send_error_to_admin(tb, lcs):
    for email in ADMIN_EMAILS:
        send_email(email, 'Error', "Locals = %s\n%s" % (lcs, tb))


def compress_traceback(tb, lcs):
    return base64.b64encode(zlib.compress(("Locals = %s\n%s" % (lcs, tb)).encode('ascii'))).decode("utf-8")


def decompress_traceback(compressed_tb):
    return zlib.decompress(base64.b64decode(compressed_tb.encode('ascii'))).decode("utf-8")
