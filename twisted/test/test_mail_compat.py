import os, string, shutil

from twisted.trial import unittest

goodmail = False
try:
    from twisted.protocols import smtp as bcsmtp, pop3 as bcpop3, imap4 as bcimap4
    from twisted.mail import smtp, pop3, imap4
except ImportError, e:
    goodmail = e


class TestCompatibility(unittest.TestCase):
    def testCompatibility(self):
        self.assertIdentical(bcsmtp.SMTPSenderFactory, smtp.SMTPSenderFactory)
        self.assertIdentical(bcpop3.POP3, pop3.POP3)
        self.assertIdentical(bcimap4.IMAP4Server, imap4.IMAP4Server)
        
if goodmail:
    TestCompatibility.skip = "Couldn't find twisted.mail package. %s" % goodmail

