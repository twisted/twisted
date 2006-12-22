# Copyright (c) 2001-2006 Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for twisted.words.protocols.jabber.server
"""

from twisted.trial import unittest
from twisted.words.protocols.jabber import server

class GenerateKeyTest(unittest.TestCase):

    def testBasic(self):
        secret = "s3cr3tf0rd14lb4ck"
        receiving = "example.net"
        originating = "example.com"
        id = "D60000229F"

        key = server.generateKey(secret, receiving, originating, id)

        self.assertEqual(key,
            '008c689ff366b50c63d69a3e2d2c0e0e1f8404b0118eb688a0102c87cb691bdc')
