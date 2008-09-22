# Copyright (c) 2001-2008 Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Test cases for twisted.mail.smtp module.
"""

from zope.interface import implements

from twisted.trial import unittest, util
from twisted.protocols import basic, loopback
from twisted.mail import smtp
from twisted.internet import defer, protocol, reactor, interfaces
from twisted.internet import address, error, task
from twisted.test.test_protocols import StringIOWithoutClosing
from twisted.test.proto_helpers import StringTransport

from twisted import cred
import twisted.cred.error
import twisted.cred.portal
import twisted.cred.checkers
import twisted.cred.credentials

from twisted.cred.portal import IRealm, Portal
from twisted.cred.checkers import ICredentialsChecker, AllowAnonymousAccess
from twisted.cred.credentials import IAnonymous
from twisted.cred.error import UnauthorizedLogin

from twisted.mail import imap4


try:
    from twisted.test.ssl_helpers import ClientTLSContext, ServerTLSContext
except ImportError:
    ClientTLSContext = ServerTLSContext = None

import re

try:
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO

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
        self.transport = protocol.FileWrapper(self.output)

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

    testMessages.suppress = [util.suppress(message='DomainSMTP', category=DeprecationWarning)]

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
        return loopback.loopbackTCP(server, client)

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
        return self.loopback(protocol, clientProtocol)
    testMessages.suppress = [util.suppress(message='DomainSMTP', category=DeprecationWarning)]

class LoopbackSMTPTestCase(LoopbackTestCase, unittest.TestCase):
    clientClass = MySMTPClient

class LoopbackESMTPTestCase(LoopbackTestCase, unittest.TestCase):
    clientClass = MyESMTPClient


class FakeSMTPServer(basic.LineReceiver):

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
        d = self.loopback(server, client)
        d.addCallback(lambda x :
                      self.assertEquals(server.buffer, self.expected_output))
        return d

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



class DummyChecker:
    implements(cred.checkers.ICredentialsChecker)

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
    implements(smtp.IMessageDelivery)

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

        d = self.loopback(server, client)
        d.addCallback(lambda x : self.assertEquals(server.authenticated, 1))
        return d

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
            ['', '<>'],
            [smtp.Address(''), '<>'],
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
            self.assertEqual(smtp.xtext_encode(case), (expected, len(case)))
            self.assertEquals(case.encode('xtext'), expected)
            self.assertEqual(
                smtp.xtext_decode(expected), (case, len(expected)))
            self.assertEquals(expected.decode('xtext'), case)


    def test_encodeWithErrors(self):
        """
        Specifying an error policy to C{unicode.encode} with the
        I{xtext} codec should produce the same result as not
        specifying the error policy.
        """
        text = u'Hello world'
        self.assertEqual(
            smtp.xtext_encode(text, 'strict'),
            (text.encode('xtext'), len(text)))
        self.assertEqual(
            text.encode('xtext', 'strict'),
            text.encode('xtext'))


    def test_decodeWithErrors(self):
        """
        Similar to L{test_encodeWithErrors}, but for C{str.decode}.
        """
        bytes = 'Hello world'
        self.assertEqual(
            smtp._slowXTextDecode(bytes, 'strict'),
            (bytes.decode('xtext'), len(bytes)))
        # This might be the same as _slowXTextDecode, but it might also be the
        # fast version instead.
        self.assertEqual(
            smtp.xtext_decode(bytes, 'strict'),
            (bytes.decode('xtext'), len(bytes)))
        self.assertEqual(
            bytes.decode('xtext', 'strict'),
            bytes.decode('xtext'))



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

        def check(ignored):
            self.assertEquals(client.tls, True)
            self.assertEquals(server.startedTLS, True)

        return self.loopback(server, client).addCallback(check)

if ClientTLSContext is None:
    for case in (TLSTestCase,):
        case.skip = "OpenSSL not present"

if not interfaces.IReactorSSL.providedBy(reactor):
    for case in (TLSTestCase,):
        case.skip = "Reactor doesn't support SSL"

class EmptyLineTestCase(unittest.TestCase):
    def testEmptyLineSyntaxError(self):
        proto = smtp.SMTP()
        output = StringIOWithoutClosing()
        transport = protocol.FileWrapper(output)
        proto.makeConnection(transport)
        proto.lineReceived('')
        proto.setTimeout(None)

        out = output.getvalue().splitlines()
        self.assertEquals(len(out), 2)
        self.failUnless(out[0].startswith('220'))
        self.assertEquals(out[1], "500 Error: bad syntax")



class TimeoutTestCase(unittest.TestCase, LoopbackMixin):
    """
    Check that SMTP client factories correctly use the timeout.
    """

    def _timeoutTest(self, onDone, clientFactory):
        """
        Connect the clientFactory, and check the timeout on the request.
        """
        clock = task.Clock()
        client = clientFactory.buildProtocol(
            address.IPv4Address('TCP', 'example.net', 25))
        client.callLater = clock.callLater
        t = StringTransport()
        client.makeConnection(t)
        t.protocol = client
        def check(ign):
            self.assertEquals(clock.seconds(), 0.5)
        d = self.assertFailure(onDone, smtp.SMTPTimeoutError
            ).addCallback(check)
        # The first call should not trigger the timeout
        clock.advance(0.1)
        # But this one should
        clock.advance(0.4)
        return d


    def test_SMTPClient(self):
        """
        Test timeout for L{smtp.SMTPSenderFactory}: the response L{Deferred}
        should be errback with a L{smtp.SMTPTimeoutError}.
        """
        onDone = defer.Deferred()
        clientFactory = smtp.SMTPSenderFactory(
            'source@address', 'recipient@address',
            StringIO("Message body"), onDone,
            retries=0, timeout=0.5)
        return self._timeoutTest(onDone, clientFactory)


    def test_ESMTPClient(self):
        """
        Test timeout for L{smtp.ESMTPSenderFactory}: the response L{Deferred}
        should be errback with a L{smtp.SMTPTimeoutError}.
        """
        onDone = defer.Deferred()
        clientFactory = smtp.ESMTPSenderFactory(
            'username', 'password',
            'source@address', 'recipient@address',
            StringIO("Message body"), onDone,
            retries=0, timeout=0.5)
        return self._timeoutTest(onDone, clientFactory)



class SingletonRealm(object):
    """
    Trivial realm implementation which is constructed with an interface and an
    avatar and returns that avatar when asked for that interface.
    """
    implements(IRealm)

    def __init__(self, interface, avatar):
        self.interface = interface
        self.avatar = avatar


    def requestAvatar(self, avatarId, mind, *interfaces):
        for iface in interfaces:
            if iface is self.interface:
                return iface, self.avatar, lambda: None



class NotImplementedDelivery(object):
    """
    Non-implementation of L{smtp.IMessageDelivery} which only has methods which
    raise L{NotImplementedError}.  Subclassed by various tests to provide the
    particular behavior being tested.
    """
    def validateFrom(self, helo, origin):
        raise NotImplementedError("This oughtn't be called in the course of this test.")


    def validateTo(self, user):
        raise NotImplementedError("This oughtn't be called in the course of this test.")


    def receivedHeader(self, helo, origin, recipients):
        raise NotImplementedError("This oughtn't be called in the course of this test.")



class SMTPServerTestCase(unittest.TestCase):
    """
    Test various behaviors of L{twisted.mail.smtp.SMTP} and
    L{twisted.mail.smtp.ESMTP}.
    """
    def testSMTPGreetingHost(self, serverClass=smtp.SMTP):
        """
        Test that the specified hostname shows up in the SMTP server's
        greeting.
        """
        s = serverClass()
        s.host = "example.com"
        t = StringTransport()
        s.makeConnection(t)
        s.connectionLost(error.ConnectionDone())
        self.assertIn("example.com", t.value())


    def testSMTPGreetingNotExtended(self):
        """
        Test that the string "ESMTP" does not appear in the SMTP server's
        greeting since that string strongly suggests the presence of support
        for various SMTP extensions which are not supported by L{smtp.SMTP}.
        """
        s = smtp.SMTP()
        t = StringTransport()
        s.makeConnection(t)
        s.connectionLost(error.ConnectionDone())
        self.assertNotIn("ESMTP", t.value())


    def testESMTPGreetingHost(self):
        """
        Similar to testSMTPGreetingHost, but for the L{smtp.ESMTP} class.
        """
        self.testSMTPGreetingHost(smtp.ESMTP)


    def testESMTPGreetingExtended(self):
        """
        Test that the string "ESMTP" does appear in the ESMTP server's
        greeting since L{smtp.ESMTP} does support the SMTP extensions which
        that advertises to the client.
        """
        s = smtp.ESMTP()
        t = StringTransport()
        s.makeConnection(t)
        s.connectionLost(error.ConnectionDone())
        self.assertIn("ESMTP", t.value())


    def test_acceptSenderAddress(self):
        """
        Test that a C{MAIL FROM} command with an acceptable address is
        responded to with the correct success code.
        """
        class AcceptanceDelivery(NotImplementedDelivery):
            """
            Delivery object which accepts all senders as valid.
            """
            def validateFrom(self, helo, origin):
                return origin

        realm = SingletonRealm(smtp.IMessageDelivery, AcceptanceDelivery())
        portal = Portal(realm, [AllowAnonymousAccess()])
        proto = smtp.SMTP()
        proto.portal = portal
        trans = StringTransport()
        proto.makeConnection(trans)

        # Deal with the necessary preliminaries
        proto.dataReceived('HELO example.com\r\n')
        trans.clear()

        # Try to specify our sender address
        proto.dataReceived('MAIL FROM:<alice@example.com>\r\n')

        # Clean up the protocol before doing anything that might raise an
        # exception.
        proto.connectionLost(error.ConnectionLost())

        # Make sure that we received exactly the correct response
        self.assertEqual(
            trans.value(),
            '250 Sender address accepted\r\n')


    def test_deliveryRejectedSenderAddress(self):
        """
        Test that a C{MAIL FROM} command with an address rejected by a
        L{smtp.IMessageDelivery} instance is responded to with the correct
        error code.
        """
        class RejectionDelivery(NotImplementedDelivery):
            """
            Delivery object which rejects all senders as invalid.
            """
            def validateFrom(self, helo, origin):
                raise smtp.SMTPBadSender(origin)

        realm = SingletonRealm(smtp.IMessageDelivery, RejectionDelivery())
        portal = Portal(realm, [AllowAnonymousAccess()])
        proto = smtp.SMTP()
        proto.portal = portal
        trans = StringTransport()
        proto.makeConnection(trans)

        # Deal with the necessary preliminaries
        proto.dataReceived('HELO example.com\r\n')
        trans.clear()

        # Try to specify our sender address
        proto.dataReceived('MAIL FROM:<alice@example.com>\r\n')

        # Clean up the protocol before doing anything that might raise an
        # exception.
        proto.connectionLost(error.ConnectionLost())

        # Make sure that we received exactly the correct response
        self.assertEqual(
            trans.value(),
            '550 Cannot receive from specified address '
            '<alice@example.com>: Sender not acceptable\r\n')


    def test_portalRejectedSenderAddress(self):
        """
        Test that a C{MAIL FROM} command with an address rejected by an
        L{smtp.SMTP} instance's portal is responded to with the correct error
        code.
        """
        class DisallowAnonymousAccess(object):
            """
            Checker for L{IAnonymous} which rejects authentication attempts.
            """
            implements(ICredentialsChecker)

            credentialInterfaces = (IAnonymous,)

            def requestAvatarId(self, credentials):
                return defer.fail(UnauthorizedLogin())

        realm = SingletonRealm(smtp.IMessageDelivery, NotImplementedDelivery())
        portal = Portal(realm, [DisallowAnonymousAccess()])
        proto = smtp.SMTP()
        proto.portal = portal
        trans = StringTransport()
        proto.makeConnection(trans)

        # Deal with the necessary preliminaries
        proto.dataReceived('HELO example.com\r\n')
        trans.clear()

        # Try to specify our sender address
        proto.dataReceived('MAIL FROM:<alice@example.com>\r\n')

        # Clean up the protocol before doing anything that might raise an
        # exception.
        proto.connectionLost(error.ConnectionLost())

        # Make sure that we received exactly the correct response
        self.assertEqual(
            trans.value(),
            '550 Cannot receive from specified address '
            '<alice@example.com>: Sender not acceptable\r\n')


    def test_portalRejectedAnonymousSender(self):
        """
        Test that a C{MAIL FROM} command issued without first authenticating
        when a portal has been configured to disallow anonymous logins is
        responded to with the correct error code.
        """
        realm = SingletonRealm(smtp.IMessageDelivery, NotImplementedDelivery())
        portal = Portal(realm, [])
        proto = smtp.SMTP()
        proto.portal = portal
        trans = StringTransport()
        proto.makeConnection(trans)

        # Deal with the necessary preliminaries
        proto.dataReceived('HELO example.com\r\n')
        trans.clear()

        # Try to specify our sender address
        proto.dataReceived('MAIL FROM:<alice@example.com>\r\n')

        # Clean up the protocol before doing anything that might raise an
        # exception.
        proto.connectionLost(error.ConnectionLost())

        # Make sure that we received exactly the correct response
        self.assertEqual(
            trans.value(),
            '550 Cannot receive from specified address '
            '<alice@example.com>: Unauthenticated senders not allowed\r\n')



class ESMTPAuthenticationTestCase(unittest.TestCase):
    def assertServerResponse(self, bytes, response):
        """
        Assert that when the given bytes are delivered to the ESMTP server
        instance, it responds with the indicated lines.

        @type bytes: str
        @type response: list of str
        """
        self.transport.clear()
        self.server.dataReceived(bytes)
        self.assertEqual(
            response,
            self.transport.value().splitlines())


    def assertServerAuthenticated(self, loginArgs, username="username", password="password"):
        """
        Assert that a login attempt has been made, that the credentials and
        interfaces passed to it are correct, and that when the login request
        is satisfied, a successful response is sent by the ESMTP server
        instance.

        @param loginArgs: A C{list} previously passed to L{portalFactory}.
        """
        d, credentials, mind, interfaces = loginArgs.pop()
        self.assertEqual(loginArgs, [])
        self.failUnless(twisted.cred.credentials.IUsernamePassword.providedBy(credentials))
        self.assertEqual(credentials.username, username)
        self.failUnless(credentials.checkPassword(password))
        self.assertIn(smtp.IMessageDeliveryFactory, interfaces)
        self.assertIn(smtp.IMessageDelivery, interfaces)
        d.callback((smtp.IMessageDeliveryFactory, None, lambda: None))

        self.assertEqual(
            ["235 Authentication successful."],
            self.transport.value().splitlines())


    def setUp(self):
        """
        Create an ESMTP instance attached to a StringTransport.
        """
        self.server = smtp.ESMTP({
                'LOGIN': imap4.LOGINCredentials})
        self.server.host = 'localhost'
        self.transport = StringTransport(
            peerAddress=address.IPv4Address('TCP', '127.0.0.1', 12345))
        self.server.makeConnection(self.transport)


    def tearDown(self):
        """
        Disconnect the ESMTP instance to clean up its timeout DelayedCall.
        """
        self.server.connectionLost(error.ConnectionDone())


    def portalFactory(self, loginList):
        class DummyPortal:
            def login(self, credentials, mind, *interfaces):
                d = defer.Deferred()
                loginList.append((d, credentials, mind, interfaces))
                return d
        return DummyPortal()


    def test_authenticationCapabilityAdvertised(self):
        """
        Test that AUTH is advertised to clients which issue an EHLO command.
        """
        self.transport.clear()
        self.server.dataReceived('EHLO\r\n')
        responseLines = self.transport.value().splitlines()
        self.assertEqual(
            responseLines[0],
            "250-localhost Hello 127.0.0.1, nice to meet you")
        self.assertEqual(
            responseLines[1],
            "250 AUTH LOGIN")
        self.assertEqual(len(responseLines), 2)


    def test_plainAuthentication(self):
        """
        Test that the LOGIN authentication mechanism can be used
        """
        loginArgs = []
        self.server.portal = self.portalFactory(loginArgs)

        self.server.dataReceived('EHLO\r\n')
        self.transport.clear()

        self.assertServerResponse(
            'AUTH LOGIN\r\n',
            ["334 " + "User Name\0".encode('base64').strip()])

        self.assertServerResponse(
            'username'.encode('base64') + '\r\n',
            ["334 " + "Password\0".encode('base64').strip()])

        self.assertServerResponse(
            'password'.encode('base64').strip() + '\r\n',
            [])

        self.assertServerAuthenticated(loginArgs)


    def test_plainAuthenticationEmptyPassword(self):
        """
        Test that giving an empty password for plain auth succeeds.
        """
        loginArgs = []
        self.server.portal = self.portalFactory(loginArgs)

        self.server.dataReceived('EHLO\r\n')
        self.transport.clear()

        self.assertServerResponse(
            'AUTH LOGIN\r\n',
            ["334 " + "User Name\0".encode('base64').strip()])

        self.assertServerResponse(
            'username'.encode('base64') + '\r\n',
            ["334 " + "Password\0".encode('base64').strip()])

        self.assertServerResponse('\r\n', [])
        self.assertServerAuthenticated(loginArgs, password='')

    def test_plainAuthenticationInitialResponse(self):
        """
        The response to the first challenge may be included on the AUTH command
        line.  Test that this is also supported.
        """
        loginArgs = []
        self.server.portal = self.portalFactory(loginArgs)

        self.server.dataReceived('EHLO\r\n')
        self.transport.clear()

        self.assertServerResponse(
            'AUTH LOGIN ' + "username".encode('base64').strip() + '\r\n',
            ["334 " + "Password\0".encode('base64').strip()])

        self.assertServerResponse(
            'password'.encode('base64').strip() + '\r\n',
            [])

        self.assertServerAuthenticated(loginArgs)


    def test_abortAuthentication(self):
        """
        Test that a challenge/response sequence can be aborted by the client.
        """
        loginArgs = []
        self.server.portal = self.portalFactory(loginArgs)

        self.server.dataReceived('EHLO\r\n')
        self.server.dataReceived('AUTH LOGIN\r\n')

        self.assertServerResponse(
            '*\r\n',
            ['501 Authentication aborted'])


    def test_invalidBase64EncodedResponse(self):
        """
        Test that a response which is not properly Base64 encoded results in
        the appropriate error code.
        """
        loginArgs = []
        self.server.portal = self.portalFactory(loginArgs)

        self.server.dataReceived('EHLO\r\n')
        self.server.dataReceived('AUTH LOGIN\r\n')

        self.assertServerResponse(
            'x\r\n',
            ['501 Syntax error in parameters or arguments'])

        self.assertEqual(loginArgs, [])


    def test_invalidBase64EncodedInitialResponse(self):
        """
        Like L{test_invalidBase64EncodedResponse} but for the case of an
        initial response included with the C{AUTH} command.
        """
        loginArgs = []
        self.server.portal = self.portalFactory(loginArgs)

        self.server.dataReceived('EHLO\r\n')
        self.assertServerResponse(
            'AUTH LOGIN x\r\n',
            ['501 Syntax error in parameters or arguments'])

        self.assertEqual(loginArgs, [])
