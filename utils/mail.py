from config import SMTP_SERVER, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, SMTP_FROM, MODULE_VERSION

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

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
    return send_smtp(to, prepare_email(to, 'IVLE Syncer: ' + subject, content + SIGN).as_string())
