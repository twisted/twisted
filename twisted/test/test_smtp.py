
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

from twisted.trial import unittest
import twisted.internet.protocol, twisted.protocols.smtp
from twisted import protocols
from twisted import internet
from twisted.protocols import loopback, smtp
from twisted.internet import defer, protocol
from twisted.test.test_protocols import StringIOWithoutClosing
import string, re
from cStringIO import StringIO

class DummyMessage:

    def __init__(self, domain, user):
        self.domain = domain
        self.user = user
        self.buffer = []

    def lineReceived(self, line):
        # Throw away the generated Received: header
        if not re.match('Received: From yyy.com \(\[.*\]\) by localhost;', line):
            self.buffer.append(line)

    def eomReceived(self):
        message = string.join(self.buffer, '\n')+'\n'
        self.domain.messages[self.user.dest.local].append(message)
        deferred = defer.Deferred()
        deferred.callback("saved")
        return deferred


class DummyDomain:

   def __init__(self, names):
       self.messages = {}
       for name in names:
           self.messages[name] = []

   def exists(self, user, success, failure):
       if self.messages.has_key(user.dest.local):
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
        self.factory = smtp.SMTPFactory()
        self.factory.domains = {}
        self.factory.domains['baz.com'] = DummyDomain(['foo'])
        self.output = StringIOWithoutClosing()
        self.transport = internet.protocol.FileWrapper(self.output)

    def testMessages(self):
        from twisted.mail import protocols
        protocol =  protocols.DomainSMTP()
        protocol.service = self.factory
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
            raise AssertionError(self.factory.domains['baz.com'].messages)
        protocol.timeoutID.cancel()

mail = '''\
Subject: hello

Goodbye
'''

class MySMTPClient(protocols.smtp.SMTPClient):

    def __init__(self):
        protocols.smtp.SMTPClient.__init__(self, 'foo.baz')
        self.mail = 'moshez@foo.bar', ['moshez@foo.bar'], mail

    def lineReceived(self, line):
        protocols.smtp.SMTPClient.lineReceived(self, line)
    
    def getMailFrom(self):
        return self.mail[0]

    def getMailTo(self):
        return self.mail[1]

    def getMailData(self):
        return StringIO(self.mail[2])

    def sentMail(self, addresses):
        self.mail = None, None, None



class LoopbackSMTPTestCase(unittest.TestCase):

    def loopback(self, server, client):
        loopback.loopbackTCP(server, client)

    def testMessages(self):
        factory = smtp.SMTPFactory()
        factory.domains = {}
        factory.domains['foo.bar'] = DummyDomain(['moshez'])
        from twisted.mail.protocols import DomainSMTP
        protocol =  DomainSMTP()
        protocol.service = factory
        protocol.factory = factory
        clientProtocol = MySMTPClient()
        self.loopback(protocol, clientProtocol)
        protocol.timeoutID.cancel()


class FakeSMTPServer(protocols.basic.LineReceiver):

    clientData = '''\
220 hello
250 nice to meet you
250 great
250 great
354 go on, lad
'''

    def connectionMade(self):
        self.buffer = ''
        for line in string.split(self.clientData, '\n'):
            self.transport.write(line + '\r\n')

    def lineReceived(self, line):
        self.buffer = self.buffer + line + '\r\n'
        if line == "QUIT":
            self.transport.write("221 see ya around\r\n")
            self.transport.loseConnection()
        if line == ".":
            self.transport.write("250 gotcha\r\n")

        
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

    def xxxtestMessages(self):
        # this test is disabled temporarily
        client = MySMTPClient()
        server = FakeSMTPServer()
        loopback.loopbackTCP(server, client)
        self.assertEquals(server.buffer, self.expected_output)

class DummySMTPMessage:

    def __init__(self, protocol, users):
        self.protocol = protocol
        self.users = users
        self.buffer = []

    def lineReceived(self, line):
        # Throw away the generated Received: header
        if not re.match('Received: From foo.com \(\[.*\]\) by foo.com;', line):
            self.buffer.append(line)

    def eomReceived(self):
        message = string.join(self.buffer, '\n')+'\n'
        helo, origin = self.users[0].helo[0], str(self.users[0].orig)
        recipients = []
        for user in self.users:
            recipients.append(str(user))
        self.protocol.message = (helo, origin, recipients, message)
        deferred = defer.Deferred()
        deferred.callback("saved")
        return deferred

class DummySMTP(smtp.SMTP):

    def connectionMade(self):
        smtp.SMTP.connectionMade(self)
        self.message = None

    def startMessage(self, users):
        return [DummySMTPMessage(self, users)]

class AnotherSMTPTestCase(unittest.TestCase):

    messages = [ ('foo.com', 'moshez@foo.com', ['moshez@bar.com'],
                  'moshez@foo.com', ['moshez@bar.com'], '''\
From: Moshe
To: Moshe

Hi,
how are you?
'''),
                 ('foo.com', 'tttt@rrr.com', ['uuu@ooo', 'yyy@eee'],
                  'tttt@rrr.com', ['uuu@ooo', 'yyy@eee'], '''\
Subject: pass

..rrrr..
'''),
                 ('foo.com', '@this,@is,@ignored:foo@bar.com',
                  ['@ignore,@this,@too:bar@foo.com'],
                  'foo@bar.com', ['bar@foo.com'], '''\
Subject: apa
To: foo

123
.
456
'''),
              ]

    data = [
        ('', '220.*\r\n$', None, None),
        ('HELO foo.com\r\n', '250.*\r\n$', None, None),
        ('RSET\r\n', '250.*\r\n$', None, None),
        ]
    for helo_, from_, to_, realfrom, realto, msg in messages:
        data.append(('MAIL FROM:<%s>\r\n' % from_, '250.*\r\n',
                     None, None))
        for rcpt in to_:
            data.append(('RCPT TO:<%s>\r\n' % rcpt, '250.*\r\n',
                         None, None))

        data.append(('DATA\r\n','354.*\r\n',
                     msg, ('250.*\r\n',
                           (helo_, realfrom, realto, msg))))


    def testBuffer(self):
        output = StringIOWithoutClosing()
        a = DummySMTP()
        class fooFactory:
            domain = 'foo.com'

        a.factory = fooFactory()
        a.makeConnection(protocol.FileWrapper(output))
        for (send, expect, msg, msgexpect) in self.data:
            if send:
                a.dataReceived(send)
            data = output.getvalue()
            output.truncate(0)
            if not re.match(expect, data):
                raise AssertionError, (send, expect, data)
            if data[:3] == '354':
                for line in msg.splitlines():
                    if line and line[0] == '.':
                        line = '.' + line
                    a.dataReceived(line + '\r\n')
                a.dataReceived('.\r\n')
                # Special case for DATA. Now we want a 250, and then
                # we compare the messages
                data = output.getvalue()
                output.truncate()
                resp, msgdata = msgexpect
                if not re.match(resp, data):
                    raise AssertionError, (resp, data)
                self.assertEquals(a.message, msgdata)
        a.timeoutID.cancel()
