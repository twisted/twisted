
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
import twisted.protocols.protocol, twisted.protocols.smtp
from twisted import protocols
from twisted.protocols import loopback, smtp, protocol
from twisted.python import defer
from twisted.test.test_protocols import StringIOWithoutClosing
import string


class DummyMessage:

    def __init__(self, domain, user):
        self.domain = domain
        self.user = user
        self.buffer = []

    def lineReceived(self, line):
        self.buffer.append(line)

    def eomReceived(self):
        message = string.join(self.buffer, '\n')+'\n'
        self.domain.messages[self.user.name].append(message)
        deferred = defer.Deferred()
        deferred.callback("saved")
        return deferred


class DummyDomain:

   def __init__(self, names):
       self.messages = {}
       for name in names:
           self.messages[name] = []

   def exists(self, user, success, failure):
       if self.messages.has_key(user.name):
           success(user)
       else:
           failure(user)

   def startMessage(self, user):
       return DummyMessage(self, user)

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



class LoopbackSMTPTestCase(unittest.TestCase):

    def testMessages(self):
        factory = protocols.protocol.Factory()
        factory.domains = {}
        factory.domains['foo.bar'] = DummyDomain(['moshez'])
        protocol =  protocols.smtp.DomainSMTP()
        protocol.factory = factory
        clientProtocol = MySMTPClient()
        loopback.loopback(protocol, clientProtocol)

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


class DummySMTPMessage:

    def __init__(self, protocol, users):
        self.protocol = protocol
        self.users = users
        self.buffer = []

    def lineReceived(self, line):
        self.buffer.append(line)

    def eomReceived(self):
        message = string.join(self.buffer, '\n')+'\n'
        helo, origin = self.users[0].helo, self.users[0].orig
        recipients = []
        for user in self.users:
            recipients.append(user.name+'@'+user.domain)
        self.protocol.messages.append((helo, origin, recipients, message))
        deferred = defer.Deferred()
        deferred.callback("saved")
        return deferred

class DummySMTP(smtp.SMTP):

    def connectionMade(self):
        smtp.SMTP.connectionMade(self)
        self.messages = []

    def handleMessageStart(self, users):
        return [DummySMTPMessage(self, users)]


class AnotherSMTPTestCase(unittest.TestCase):

    messages = [ ('foo.com', 'moshez@foo.com', ['moshez@bar.com'], '''\
From: Moshe
To: Moshe

Hi,
how are you?
'''),
                 ('foo.com', 'tttt@rrr.com', ['uuu@ooo', 'yyy@eee'], '''\
Subject: pass

..rrrr..
''')
              ]

    expected_output = '220 Spammers beware, your ass is on fire\015\012250 Nice to meet you\015\012250 From address accepted\015\012250 Address recognized\015\012354 Continue\015\012250 Delivery in progress\015\012250 From address accepted\015\012250 Address recognized\015\012250 Address recognized\015\012354 Continue\015\012250 Delivery in progress\015\012221 See you later\015\012'

    input = 'HELO foo.com\r\n'
    for _, from_, to_, message in messages:
        input = input + 'MAIL FROM:<%s>\r\n' % from_
        for item in to_:
            input = input + 'RCPT TO:<%s>\r\n' % item
        input = input + 'DATA\r\n'
        for line in string.split(message, '\n')[:-1]:
            if line[:1] == '.': line = '.' + line
            input = input + line + '\r\n'
        input = input + '.' + '\r\n'
    input = input + 'QUIT\r\n'

    def testBuffer(self):
        output = StringIOWithoutClosing()
        a = DummySMTP()
        a.makeConnection(protocol.FileWrapper(output))
        a.dataReceived(self.input)
        if a.messages != self.messages:
            raise AssertionError(a.messages)
        if output.getvalue() != self.expected_output:
            raise AssertionError(`output.getvalue()`)


testCases = [SMTPTestCase, SMTPClientTestCase, LoopbackSMTPTestCase, AnotherSMTPTestCase]
