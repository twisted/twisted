# -*- test-case-name: twisted.mail.test.test_bounce -*-
#
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.


"""
Support for bounce message generation.
"""
import StringIO
import email.utils
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
    """
    Generate a bounce message for an undeliverable email message.

    @type message: L{bytes}
    @param message: The undeliverable message.

    @type failedFrom: L{bytes}
    @param failedFrom: The originator of the undeliverable message.

    @type failedTo: L{bytes}
    @param failedTo: The destination of the undeliverable message.

    @type transcript: L{bytes}
    @param transcript: An error message to include in the bounce message.

    @rtype: 3-L{tuple} of (E{1}) L{bytes}, (E{2}) L{bytes}, (E{3}) L{bytes}
    @return: The originator, the destination and the contents of the bounce
        message.  The destination of the bounce message is the originator of
        the undeliverable message.
    """
    if not transcript:
        transcript = '''\
I'm sorry, the following address has permanent errors: %(failedTo)s.
I've given up, and I will not retry the message again.
''' % {'failedTo': failedTo}

    failedAddress = email.utils.parseaddr(failedTo)[1]
    data = {
        'boundary': "%s_%s_%s" % (time.time(), os.getpid(), 'XXXXX'),
        'ctime': time.ctime(time.time()),
        'failedAddress': failedAddress,
        'failedDomain': failedAddress.split('@', 1)[1],
        'failedFrom': failedFrom,
        'failedTo': failedTo,
        'messageID': smtp.messageid(uniq='bounce'),
        'message': message,
        'transcript': transcript,
        }

    fp = StringIO.StringIO()
    fp.write(BOUNCE_FORMAT % data)
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
