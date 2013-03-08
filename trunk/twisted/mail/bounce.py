# -*- test-case-name: twisted.mail.test.test_bounce -*-
#
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.


import StringIO
import rfc822
import time
import os


from twisted.mail import smtp

BOUNCE_FORMAT = """\
From: postmaster@%(failedDomain)s
To: %(failedFrom)s
Subject: Returned Mail: see transcript for details
Message-ID: %(messageID)s
Content-Type: multipart/report; report-type=delivery-status;
    boundary="%(boundary)s"

--%(boundary)s

%(transcript)s

--%(boundary)s
Content-Type: message/delivery-status
Arrival-Date: %(ctime)s
Final-Recipient: RFC822; %(failedTo)s
"""

def generateBounce(message, failedFrom, failedTo, transcript=''):
    if not transcript:
        transcript = '''\
I'm sorry, the following address has permanent errors: %(failedTo)s.
I've given up, and I will not retry the message again.
''' % vars()

    boundary = "%s_%s_%s" % (time.time(), os.getpid(), 'XXXXX')
    failedAddress = rfc822.AddressList(failedTo)[0][1]
    failedDomain = failedAddress.split('@', 1)[1]
    messageID = smtp.messageid(uniq='bounce')
    ctime = time.ctime(time.time())

    fp = StringIO.StringIO()
    fp.write(BOUNCE_FORMAT % vars())
    orig = message.tell()
    message.seek(2, 0)
    sz = message.tell()
    message.seek(0, orig)
    if sz > 10000:
        while 1:
            line = message.readline()
            if len(line)<=1:
                break
            fp.write(line)
    else:
        fp.write(message.read())
    return '', failedFrom, fp.getvalue()
