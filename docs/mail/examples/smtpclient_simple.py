# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Demonstrate sending mail via SMTP.
"""

from __future__ import print_function

import sys
from email.mime.text import MIMEText

from twisted.python import log
from twisted.mail.smtp import sendmail
from twisted.internet import reactor


def send(message, subject, sender, recipients, host):
    """
    Send email to one or more addresses.
    """
    msg = MIMEText(message)
    msg['Subject'] = subject
    msg['From'] = sender
    msg['To'] = ', '.join(recipients)

    dfr = sendmail(host, sender, recipients, msg.as_string())
    def success(r):
        reactor.stop()
    def error(e):
        print(e)
        reactor.stop()
    dfr.addCallback(success)
    dfr.addErrback(error)

    reactor.run()


if __name__ == '__main__':
    msg = 'This is the message body'
    subject = 'This is the message subject'

    host = 'smtp.example.com'
    sender = 'sender@example.com'
    recipients = ['recipient@example.com']

    log.startLogging(sys.stdout)
    send(msg, subject, sender, recipients, host)

