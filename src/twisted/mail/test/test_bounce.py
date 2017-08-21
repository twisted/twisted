# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

from twisted.trial import unittest
from twisted.mail import bounce
import email.message
import email.parser
from io import BytesIO, StringIO

class BounceTests(unittest.TestCase):
    """
    Bounce message generation
    """

    def test_bounceFormatUnicode(self):
        fromAddress, to, s = bounce.generateBounce(StringIO(u'''\
From: Moshe Zadka <moshez@example.com>
To: nonexistent@example.org
Subject: test

'''), u'moshez@example.com', u'nonexistent@example.org')
        self.assertEqual(fromAddress, b'')
        self.assertEqual(to, b'moshez@example.com')
        emailParser = email.parser.Parser()
        mess = emailParser.parse(StringIO(s.decode("utf-8")))
        self.assertEqual(mess['To'], 'moshez@example.com')
        self.assertEqual(mess['From'], 'postmaster@example.org')
        self.assertEqual(mess['subject'],
                        'Returned Mail: see transcript for details')


    def test_bounceFormatBytes(self):
        fromAddress, to, s = bounce.generateBounce(BytesIO(b'''\
From: Moshe Zadka <moshez@example.com>
To: nonexistent@example.org
Subject: test

'''), b'moshez@example.com', b'nonexistent@example.org')
        self.assertEqual(fromAddress, b'')
        self.assertEqual(to, b'moshez@example.com')
        emailParser = email.parser.Parser()
        mess = emailParser.parse(StringIO(s.decode("utf-8")))
        self.assertEqual(mess['To'], 'moshez@example.com')
        self.assertEqual(mess['From'], 'postmaster@example.org')
        self.assertEqual(mess['subject'],
                         'Returned Mail: see transcript for details')
