
# Twisted, the Framework of Your Internet
# Copyright (C) 2001 Matthew W. Lefkowitz
# 
# This library is free software; you can redistribute it and/or
# modify it under the terms of version 2.1 of the GNU Lesser General Public
# License as published by the Free Software Foundation.
# 
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
# 
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

"""
Test cases for twisted.smtp module.
"""

from pyunit import unittest
from twisted.internet import main
import twisted.protocols.protocol, twisted.protocols.smtp
from twisted import protocols
from twisted.test.test_protocols import StringIOWithoutClosing


class DummyDomain:

   def __init__(self, names):
       self.messages = {}
       for name in names:
           self.messages[name] = []

   def exists(self, name, domain, protocol):
       return self.messages.has_key(name)

   def saveMessage(self, origin, name, message, domain):
       self.messages[name].append(message)

class SMTPTestCase(unittest.TestCase):

    messages = [('foo@bar.com', ['foo@baz.com', 'qux@baz.com'], '''\
Subject: urgent\015
\015
Someone set up us the bomb!\015
''')]

    mbox = {'foo': ['Subject: urgent\n\nSomeone set up us the bomb!\n']}

    def setUp(self):
        self.factory = protocols.protocol.Factory()
        self.factory.domains = {}
        self.factory.domains['baz.com'] = DummyDomain(['foo'])
        self.output = StringIOWithoutClosing()
        self.transport = protocols.protocol.FileWrapper(self.output)

    def testMessages(self):
        protocol =  protocols.smtp.DomainSMTP()
        protocol.factory = self.factory
        protocol.makeConnection(self.transport)
        protocol.lineReceived('HELO yyy.com')
        for message in self.messages:
            protocol.lineReceived('MAIL FROM:<%s>' % message[0])
            for target in message[1]:
                protocol.lineReceived('RCPT TO:<%s>' % target)
            protocol.lineReceived('DATA')
            protocol.dataReceived(message[2])
            protocol.lineReceived('.')
        protocol.lineReceived('QUIT')
        if self.mbox != self.factory.domains['baz.com'].messages:
            raise AssertionError(self.server.domains['baz.com'].messages)

mail = '''\
Subject: hello

Goodbye
'''

class MySMTPClient(protocols.smtp.SMTPClient):

    def __init__(self):
        protocols.smtp.SMTPClient.__init__(self, 'foo.baz')
        self.mail = 'moshez@foo.bar', ['moshez@foo.bar'], mail

    def getMailFrom(self):
        return self.mail[0]

    def getMailTo(self):
        return self.mail[1]

    def getMailData(self):
        return self.mail[2]

    def sentMail(self, addresses):
        self.mail = None, None, None


class SMTPClientTestCase(unittest.TestCase):

    expected_output='''\
HELO foo.baz\r
MAIL FROM:<moshez@foo.bar>\r
RCPT TO:<moshez@foo.bar>\r
DATA\r
Subject: hello\r
\r
Goodbye\r
.\r
QUIT\r
'''

    def setUp(self):
        self.output = StringIOWithoutClosing()
        self.transport = protocols.protocol.FileWrapper(self.output)

    def testMessages(self):
        protocol = MySMTPClient()
        protocol.makeConnection(self.transport)
        protocol.lineReceived('220 hello')
        protocol.lineReceived('250 nice to meet you')
        protocol.lineReceived('250 great')
        protocol.lineReceived('250 great')
        protocol.lineReceived('354 go on, lad')
        protocol.lineReceived('250 gotcha')
        protocol.lineReceived('221 see ya around')
        if self.output.getvalue() != self.expected_output:
            raise AssertionError(`self.output.getvalue()`)

testCases = [SMTPTestCase, SMTPClientTestCase]
