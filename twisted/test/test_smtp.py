
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
Test cases for twisted.protocols.smtp module.
"""

from twisted.trial import unittest
import twisted.internet.protocol
import twisted.protocols.smtp
from twisted import protocols
from twisted import internet
from twisted.protocols import loopback
from twisted.protocols import smtp
from twisted.internet import defer, protocol, reactor, interfaces
from twisted.test.test_protocols import StringIOWithoutClosing
from twisted.python import components

from twisted import cred
import twisted.cred.error
import twisted.cred.portal
import twisted.cred.checkers
import twisted.cred.credentials

try:
    from ssl_helpers import ClientTLSContext, ServerTLSContext
except ImportError:
    ClientTLSContext = ServerTLSContext = None

import re

try:
    from cStringIO import StringIO
except ImportError:
    import StringIO

def spameater(*spam, **eggs):
    return None

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
        message = '\n'.join(self.buffer) + '\n'
        self.domain.messages[self.user.dest.local].append(message)
        deferred = defer.Deferred()
        deferred.callback("saved")
        return deferred


class DummyDomain:

   def __init__(self, names):
       self.messages = {}
       for name in names:
           self.messages[name] = []

   def exists(self, user):
       if self.messages.has_key(user.dest.local):
           return defer.succeed(lambda: self.startMessage(user))
       return defer.fail(smtp.SMTPBadRcpt(user))

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
        protocol.receivedHeader = spameater
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
        protocol.setTimeout(None)

mail = '''\
Subject: hello

Goodbye
'''

class MyClient:
    def __init__(self):
        self.mail = 'moshez@foo.bar', ['moshez@foo.bar'], mail

    def getMailFrom(self):
        return self.mail[0]

    def getMailTo(self):
        return self.mail[1]

    def getMailData(self):
        return StringIO(self.mail[2])

    def sentMail(self, code, resp, numOk, addresses, log):
        self.mail = None, None, None

class MySMTPClient(MyClient, smtp.SMTPClient):
    def __init__(self):
        smtp.SMTPClient.__init__(self, 'foo.baz')
        MyClient.__init__(self)

class MyESMTPClient(MyClient, smtp.ESMTPClient):
    def __init__(self, secret = '', contextFactory = None):
        smtp.ESMTPClient.__init__(self, secret, contextFactory, 'foo.baz')
        MyClient.__init__(self)

class LoopbackMixin:
    def loopback(self, server, client):
        loopback.loopbackTCP(server, client)

class LoopbackTestCase(LoopbackMixin):
    def testMessages(self):
        factory = smtp.SMTPFactory()
        factory.domains = {}
        factory.domains['foo.bar'] = DummyDomain(['moshez'])
        from twisted.mail.protocols import DomainSMTP
        protocol =  DomainSMTP()
        protocol.service = factory
        protocol.factory = factory
        clientProtocol = self.clientClass()
        self.loopback(protocol, clientProtocol)

class LoopbackSMTPTestCase(LoopbackTestCase, unittest.TestCase):
    clientClass = MySMTPClient

class LoopbackESMTPTestCase(LoopbackTestCase, unittest.TestCase):
    clientClass = MyESMTPClient


class FakeSMTPServer(protocols.basic.LineReceiver):

    clientData = [
        '220 hello', '250 nice to meet you',
        '250 great', '250 great', '354 go on, lad'
    ]

    def connectionMade(self):
        self.buffer = []
        self.clientData = self.clientData[:]
        self.clientData.reverse()
        self.sendLine(self.clientData.pop())
    
    def lineReceived(self, line):
        self.buffer.append(line)
        if line == "QUIT":
            self.transport.write("221 see ya around\r\n")
            self.transport.loseConnection()
        elif line == ".":
            self.transport.write("250 gotcha\r\n")
        elif line == "RSET":
            self.transport.loseConnection()

        if self.clientData:
            self.sendLine(self.clientData.pop())

        
class SMTPClientTestCase(unittest.TestCase, LoopbackMixin):

    expected_output = [
        'HELO foo.baz', 'MAIL FROM:<moshez@foo.bar>',
        'RCPT TO:<moshez@foo.bar>', 'DATA',
        'Subject: hello', '', 'Goodbye', '.', 'RSET'
    ]

    def testMessages(self):
        # this test is disabled temporarily
        client = MySMTPClient()
        server = FakeSMTPServer()
        self.loopback(server, client)
        self.assertEquals(server.buffer, self.expected_output)

class DummySMTPMessage:

    def __init__(self, protocol, users):
        self.protocol = protocol
        self.users = users
        self.buffer = []

    def lineReceived(self, line):
        self.buffer.append(line)

    def eomReceived(self):
        message = '\n'.join(self.buffer) + '\n'
        helo, origin = self.users[0].helo[0], str(self.users[0].orig)
        recipients = []
        for user in self.users:
            recipients.append(str(user))
        self.protocol.message[tuple(recipients)] = (helo, origin, recipients, message)
        return defer.succeed("saved")
        deferred.callback("saved")
        return deferred

class DummyProto:
    def connectionMade(self):
        self.dummyMixinBase.connectionMade(self)
        self.message = {}

    def startMessage(self, users):
        return DummySMTPMessage(self, users)

    def receivedHeader(*spam):
        return None
    
    def validateTo(self, user):
        self.delivery = DummyDelivery()
        return lambda: self.startMessage([user])
    
    def validateFrom(self, helo, origin):
        return origin

class DummySMTP(DummyProto, smtp.SMTP):
    dummyMixinBase = smtp.SMTP

class DummyESMTP(DummyProto, smtp.ESMTP):
    dummyMixinBase = smtp.ESMTP

class AnotherTestCase:
    serverClass = None
    clientClass = None

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
        a = self.serverClass()
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
                for recip in msgdata[2]:
                    expected = list(msgdata[:])
                    expected[2] = [recip]
                    self.assertEquals(
                        a.message[(recip,)],
                        tuple(expected)
                    )
        a.setTimeout(None)


class AnotherESMTPTestCase(AnotherTestCase, unittest.TestCase):
    serverClass = DummyESMTP
    clientClass = MyESMTPClient

class AnotherSMTPTestCase(AnotherTestCase, unittest.TestCase):
    serverClass = DummySMTP
    clientClass = MySMTPClient


# XXX - These need to be moved
from twisted.protocols import imap4

class DummyChecker:
    __implements__ = (cred.checkers.ICredentialsChecker,)
    
    users = {
        'testuser': 'testpassword'
    }
    
    credentialInterfaces = (cred.credentials.IUsernameHashedPassword,)
    
    def requestAvatarId(self, credentials):
        return defer.maybeDeferred(
            credentials.checkPassword, self.users[credentials.username]
        ).addCallback(self._cbCheck, credentials.username)

    def _cbCheck(self, result, username):
        if result:
            return username
        raise cred.error.UnauthorizedLogin()

class DummyDelivery:
    __implements__ = (smtp.IMessageDelivery,)
    
    def validateTo(self, user):
        return user
    
    def validateFrom(self, helo, origin):
        return origin
    
    def receivedHeader(*args):
        return None 

class DummyRealm:
    def requestAvatar(self, avatarId, mind, *interfaces):
        return smtp.IMessageDelivery, DummyDelivery(), lambda: None

class AuthTestCase(unittest.TestCase, LoopbackMixin):
    def testAuth(self):
        realm = DummyRealm()
        p = cred.portal.Portal(realm)
        p.registerChecker(DummyChecker())

        server = DummyESMTP({'CRAM-MD5': cred.credentials.CramMD5Credentials})
        server.portal = p
        client = MyESMTPClient('testpassword')

        cAuth = imap4.CramMD5ClientAuthenticator('testuser')
        client.registerAuthenticator(cAuth)
        
        self.loopback(server, client)

        self.assertEquals(server.authenticated, 1)

class SMTPHelperTestCase(unittest.TestCase):
    def testMessageID(self):
        d = {}
        for i in range(1000):
            m = smtp.messageid('testcase')
            self.failIf(m in d)
            d[m] = None
    
    def testQuoteAddr(self):
        cases = [
            ['user@host.name', '<user@host.name>'],
            ['"User Name" <user@host.name>', '<user@host.name>'],
            [smtp.Address('someguy@someplace'), '<someguy@someplace>'],
        ]
        
        for (c, e) in cases:
            self.assertEquals(smtp.quoteaddr(c), e)

    def testUser(self):
        u = smtp.User('user@host', 'helo.host.name', None, None)
        self.assertEquals(str(u), 'user@host')

    def testXtextEncoding(self):
        cases = [
            ('Hello world', 'Hello+20world'),
            ('Hello+world', 'Hello+2Bworld'),
            ('\0\1\2\3\4\5', '+00+01+02+03+04+05'),
            ('e=mc2@example.com', 'e+3Dmc2@example.com')
        ]
        
        for (case, expected) in cases:
            self.assertEquals(case.encode('xtext'), expected)
            self.assertEquals(expected.decode('xtext'), case)


class NoticeTLSClient(MyESMTPClient):
    tls = False
    
    def esmtpState_starttls(self, code, resp):
        MyESMTPClient.esmtpState_starttls(self, code, resp)
        self.tls = True

class TLSTestCase(unittest.TestCase, LoopbackMixin):
    def testTLS(self):
        clientCTX = ClientTLSContext()
        serverCTX = ServerTLSContext()
        
        client = NoticeTLSClient(contextFactory=clientCTX)
        server = DummyESMTP(contextFactory=serverCTX)
        
        self.loopback(server, client)
        
        self.assertEquals(client.tls, True)
        self.assertEquals(server.startedTLS, True)

if ClientTLSContext is None:
    for case in (TLSTestCase,):
        case.skip = "OpenSSL not present"

if not components.implements(reactor, interfaces.IReactorSSL):
    for case in (TLSTestCase,):
        case.skip = "Reactor doesn't support SSL"

class EmptyLineTestCase(unittest.TestCase):
    def testEmptyLineSyntaxError(self):
        proto = smtp.SMTP()
        output = StringIOWithoutClosing()
        transport = internet.protocol.FileWrapper(output)
        proto.makeConnection(transport)
        proto.lineReceived('')
        proto.setTimeout(None)

        out = output.getvalue().splitlines()
        self.assertEquals(len(out), 2)
        self.failUnless(out[0].startswith('220'))
        self.assertEquals(out[1], "500 Error: bad syntax")
