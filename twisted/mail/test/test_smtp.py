# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Test cases for twisted.mail.smtp module.
"""

from zope.interface import implements

from twisted.python.util import LineLog
from twisted.trial import unittest, util
from twisted.protocols import basic, loopback
from twisted.mail import smtp
from twisted.internet import defer, protocol, reactor, interfaces
from twisted.internet import address, error, task
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



class BrokenMessage(object):
    """
    L{BrokenMessage} is an L{IMessage} which raises an unexpected exception
    from its C{eomReceived} method.  This is useful for creating a server which
    can be used to test client retry behavior.
    """
    implements(smtp.IMessage)

    def __init__(self, user):
        pass


    def lineReceived(self, line):
        pass


    def eomReceived(self):
        raise RuntimeError("Some problem, delivery is failing.")


    def connectionLost(self):
        pass



class DummyMessage(object):
    """
    L{BrokenMessage} is an L{IMessage} which saves the message delivered to it
    to its domain object.

    @ivar domain: A L{DummyDomain} which will be used to store the message once
        it is received.
    """
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



class DummyDomain(object):
    """
    L{DummyDomain} is an L{IDomain} which keeps track of messages delivered to
    it in memory.
    """
    def __init__(self, names):
        self.messages = {}
        for name in names:
            self.messages[name] = []


    def exists(self, user):
        if user.dest.local in self.messages:
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
        """
        Create an in-memory mail domain to which messages may be delivered by
        tests and create a factory and transport to do the delivering.
        """
        self.factory = smtp.SMTPFactory()
        self.factory.domains = {}
        self.factory.domains['baz.com'] = DummyDomain(['foo'])
        self.transport = StringTransport()


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
    def __init__(self, messageInfo=None):
        if messageInfo is None:
            messageInfo = (
                'moshez@foo.bar', ['moshez@foo.bar'], StringIO(mail))
        self._sender = messageInfo[0]
        self._recipient = messageInfo[1]
        self._data = messageInfo[2]


    def getMailFrom(self):
        return self._sender


    def getMailTo(self):
        return self._recipient


    def getMailData(self):
        return self._data


    def sendError(self, exc):
        self._error = exc


    def sentMail(self, code, resp, numOk, addresses, log):
        # Prevent another mail from being sent.
        self._sender = None
        self._recipient = None
        self._data = None



class MySMTPClient(MyClient, smtp.SMTPClient):
    def __init__(self, messageInfo=None):
        smtp.SMTPClient.__init__(self, 'foo.baz')
        MyClient.__init__(self, messageInfo)

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
    """
    Tests for L{smtp.SMTPClient}.
    """

    def test_timeoutConnection(self):
        """
        L{smtp.SMTPClient.timeoutConnection} calls the C{sendError} hook with a
        fatal L{SMTPTimeoutError} with the current line log.
        """
        error = []
        client = MySMTPClient()
        client.sendError = error.append
        client.makeConnection(StringTransport())
        client.lineReceived("220 hello")
        client.timeoutConnection()
        self.assertIsInstance(error[0], smtp.SMTPTimeoutError)
        self.assertTrue(error[0].isFatal)
        self.assertEqual(
            str(error[0]),
            "Timeout waiting for SMTP server response\n"
            "<<< 220 hello\n"
            ">>> HELO foo.baz\n")


    expected_output = [
        'HELO foo.baz', 'MAIL FROM:<moshez@foo.bar>',
        'RCPT TO:<moshez@foo.bar>', 'DATA',
        'Subject: hello', '', 'Goodbye', '.', 'RSET'
    ]

    def test_messages(self):
        """
        L{smtp.SMTPClient} sends I{HELO}, I{MAIL FROM}, I{RCPT TO}, and I{DATA}
        commands based on the return values of its C{getMailFrom},
        C{getMailTo}, and C{getMailData} methods.
        """
        client = MySMTPClient()
        server = FakeSMTPServer()
        d = self.loopback(server, client)
        d.addCallback(lambda x :
                      self.assertEqual(server.buffer, self.expected_output))
        return d


    def test_transferError(self):
        """
        If there is an error while producing the message body to the
        connection, the C{sendError} callback is invoked.
        """
        client = MySMTPClient(
            ('alice@example.com', ['bob@example.com'], StringIO("foo")))
        transport = StringTransport()
        client.makeConnection(transport)
        client.dataReceived(
            '220 Ok\r\n' # Greeting
            '250 Ok\r\n' # EHLO response
            '250 Ok\r\n' # MAIL FROM response
            '250 Ok\r\n' # RCPT TO response
            '354 Ok\r\n' # DATA response
            )

        # Sanity check - a pull producer should be registered now.
        self.assertNotIdentical(transport.producer, None)
        self.assertFalse(transport.streaming)

        # Now stop the producer prematurely, meaning the message was not sent.
        transport.producer.stopProducing()

        # The sendError hook should have been invoked as a result.
        self.assertIsInstance(client._error, Exception)


    def test_sendFatalError(self):
        """
        If L{smtp.SMTPClient.sendError} is called with an L{SMTPClientError}
        which is fatal, it disconnects its transport without writing anything
        more to it.
        """
        client = smtp.SMTPClient(None)
        transport = StringTransport()
        client.makeConnection(transport)
        client.sendError(smtp.SMTPClientError(123, "foo", isFatal=True))
        self.assertEqual(transport.value(), "")
        self.assertTrue(transport.disconnecting)


    def test_sendNonFatalError(self):
        """
        If L{smtp.SMTPClient.sendError} is called with an L{SMTPClientError}
        which is not fatal, it sends C{"QUIT"} and waits for the server to
        close the connection.
        """
        client = smtp.SMTPClient(None)
        transport = StringTransport()
        client.makeConnection(transport)
        client.sendError(smtp.SMTPClientError(123, "foo", isFatal=False))
        self.assertEqual(transport.value(), "QUIT\r\n")
        self.assertFalse(transport.disconnecting)


    def test_sendOtherError(self):
        """
        If L{smtp.SMTPClient.sendError} is called with an exception which is
        not an L{SMTPClientError}, it disconnects its transport without
        writing anything more to it.
        """
        client = smtp.SMTPClient(None)
        transport = StringTransport()
        client.makeConnection(transport)
        client.sendError(Exception("foo"))
        self.assertEqual(transport.value(), "")
        self.assertTrue(transport.disconnecting)



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
        self.delivery = SimpleDelivery(None)
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


    def test_buffer(self):
        """
        Exercise a lot of the SMTP client code.  This is a "shotgun" style unit
        test.  It does a lot of things and hopes that something will go really
        wrong if it is going to go wrong.  This test should be replaced with a
        suite of nicer tests.
        """
        transport = StringTransport()
        a = self.serverClass()
        class fooFactory:
            domain = 'foo.com'

        a.factory = fooFactory()
        a.makeConnection(transport)
        for (send, expect, msg, msgexpect) in self.data:
            if send:
                a.dataReceived(send)
            data = transport.value()
            transport.clear()
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
                data = transport.value()
                transport.clear()
                resp, msgdata = msgexpect
                if not re.match(resp, data):
                    raise AssertionError, (resp, data)
                for recip in msgdata[2]:
                    expected = list(msgdata[:])
                    expected[2] = [recip]
                    self.assertEqual(
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

    credentialInterfaces = (cred.credentials.IUsernamePassword,
                            cred.credentials.IUsernameHashedPassword)

    def requestAvatarId(self, credentials):
        return defer.maybeDeferred(
            credentials.checkPassword, self.users[credentials.username]
        ).addCallback(self._cbCheck, credentials.username)

    def _cbCheck(self, result, username):
        if result:
            return username
        raise cred.error.UnauthorizedLogin()



class SimpleDelivery(object):
    """
    L{SimpleDelivery} is a message delivery factory with no interesting
    behavior.
    """
    implements(smtp.IMessageDelivery)

    def __init__(self, messageFactory):
        self._messageFactory = messageFactory


    def receivedHeader(self, helo, origin, recipients):
        return None


    def validateFrom(self, helo, origin):
        return origin


    def validateTo(self, user):
        return lambda: self._messageFactory(user)



class DummyRealm:
    def requestAvatar(self, avatarId, mind, *interfaces):
        return smtp.IMessageDelivery, SimpleDelivery(None), lambda: None



class AuthTestCase(unittest.TestCase, LoopbackMixin):
    def test_crammd5Auth(self):
        """
        L{ESMTPClient} can authenticate using the I{CRAM-MD5} SASL mechanism.

        @see: U{http://tools.ietf.org/html/rfc2195}
        """
        realm = DummyRealm()
        p = cred.portal.Portal(realm)
        p.registerChecker(DummyChecker())

        server = DummyESMTP({'CRAM-MD5': cred.credentials.CramMD5Credentials})
        server.portal = p
        client = MyESMTPClient('testpassword')

        cAuth = smtp.CramMD5ClientAuthenticator('testuser')
        client.registerAuthenticator(cAuth)

        d = self.loopback(server, client)
        d.addCallback(lambda x : self.assertEqual(server.authenticated, 1))
        return d


    def test_loginAuth(self):
        """
        L{ESMTPClient} can authenticate using the I{LOGIN} SASL mechanism.

        @see: U{http://sepp.oetiker.ch/sasl-2.1.19-ds/draft-murchison-sasl-login-00.txt}
        """
        realm = DummyRealm()
        p = cred.portal.Portal(realm)
        p.registerChecker(DummyChecker())

        server = DummyESMTP({'LOGIN': imap4.LOGINCredentials})
        server.portal = p
        client = MyESMTPClient('testpassword')

        cAuth = smtp.LOGINAuthenticator('testuser')
        client.registerAuthenticator(cAuth)

        d = self.loopback(server, client)
        d.addCallback(lambda x: self.assertTrue(server.authenticated))
        return d


    def test_loginAgainstWeirdServer(self):
        """
        When communicating with a server which implements the I{LOGIN} SASL
        mechanism using C{"Username:"} as the challenge (rather than C{"User
        Name\\0"}), L{ESMTPClient} can still authenticate successfully using
        the I{LOGIN} mechanism.
        """
        realm = DummyRealm()
        p = cred.portal.Portal(realm)
        p.registerChecker(DummyChecker())

        server = DummyESMTP({'LOGIN': smtp.LOGINCredentials})
        server.portal = p

        client = MyESMTPClient('testpassword')
        cAuth = smtp.LOGINAuthenticator('testuser')
        client.registerAuthenticator(cAuth)

        d = self.loopback(server, client)
        d.addCallback(lambda x: self.assertTrue(server.authenticated))
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
            self.assertEqual(smtp.quoteaddr(c), e)

    def testUser(self):
        u = smtp.User('user@host', 'helo.host.name', None, None)
        self.assertEqual(str(u), 'user@host')

    def testXtextEncoding(self):
        cases = [
            ('Hello world', 'Hello+20world'),
            ('Hello+world', 'Hello+2Bworld'),
            ('\0\1\2\3\4\5', '+00+01+02+03+04+05'),
            ('e=mc2@example.com', 'e+3Dmc2@example.com')
        ]

        for (case, expected) in cases:
            self.assertEqual(smtp.xtext_encode(case), (expected, len(case)))
            self.assertEqual(case.encode('xtext'), expected)
            self.assertEqual(
                smtp.xtext_decode(expected), (case, len(expected)))
            self.assertEqual(expected.decode('xtext'), case)


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
            self.assertEqual(client.tls, True)
            self.assertEqual(server.startedTLS, True)

        return self.loopback(server, client).addCallback(check)

if ClientTLSContext is None:
    for case in (TLSTestCase,):
        case.skip = "OpenSSL not present"

if not interfaces.IReactorSSL.providedBy(reactor):
    for case in (TLSTestCase,):
        case.skip = "Reactor doesn't support SSL"

class EmptyLineTestCase(unittest.TestCase):
    def test_emptyLineSyntaxError(self):
        """
        If L{smtp.SMTP} receives an empty line, it responds with a 500 error
        response code and a message about a syntax error.
        """
        proto = smtp.SMTP()
        transport = StringTransport()
        proto.makeConnection(transport)
        proto.lineReceived('')
        proto.setTimeout(None)

        out = transport.value().splitlines()
        self.assertEqual(len(out), 2)
        self.failUnless(out[0].startswith('220'))
        self.assertEqual(out[1], "500 Error: bad syntax")



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
            self.assertEqual(clock.seconds(), 0.5)
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


    def test_resetTimeoutWhileSending(self):
        """
        The timeout is not allowed to expire after the server has accepted a
        DATA command and the client is actively sending data to it.
        """
        class SlowFile:
            """
            A file-like which returns one byte from each read call until the
            specified number of bytes have been returned.
            """
            def __init__(self, size):
                self._size = size

            def read(self, max=None):
                if self._size:
                    self._size -= 1
                    return 'x'
                return ''

        failed = []
        onDone = defer.Deferred()
        onDone.addErrback(failed.append)
        clientFactory = smtp.SMTPSenderFactory(
            'source@address', 'recipient@address',
            SlowFile(1), onDone, retries=0, timeout=3)
        clientFactory.domain = "example.org"
        clock = task.Clock()
        client = clientFactory.buildProtocol(
            address.IPv4Address('TCP', 'example.net', 25))
        client.callLater = clock.callLater
        transport = StringTransport()
        client.makeConnection(transport)

        client.dataReceived(
            "220 Ok\r\n" # Greet the client
            "250 Ok\r\n" # Respond to HELO
            "250 Ok\r\n" # Respond to MAIL FROM
            "250 Ok\r\n" # Respond to RCPT TO
            "354 Ok\r\n" # Respond to DATA
            )

        # Now the client is producing data to the server.  Any time
        # resumeProducing is called on the producer, the timeout should be
        # extended.  First, a sanity check.  This test is only written to
        # handle pull producers.
        self.assertNotIdentical(transport.producer, None)
        self.assertFalse(transport.streaming)

        # Now, allow 2 seconds (1 less than the timeout of 3 seconds) to
        # elapse.
        clock.advance(2)

        # The timeout has not expired, so the failure should not have happened.
        self.assertEqual(failed, [])

        # Let some bytes be produced, extending the timeout.  Then advance the
        # clock some more and verify that the timeout still hasn't happened.
        transport.producer.resumeProducing()
        clock.advance(2)
        self.assertEqual(failed, [])

        # The file has been completely produced - the next resume producing
        # finishes the upload, successfully.
        transport.producer.resumeProducing()
        client.dataReceived("250 Ok\r\n")
        self.assertEqual(failed, [])

        # Verify that the client actually did send the things expected.
        self.assertEqual(
            transport.value(),
            "HELO example.org\r\n"
            "MAIL FROM:<source@address>\r\n"
            "RCPT TO:<recipient@address>\r\n"
            "DATA\r\n"
            "x\r\n"
            ".\r\n"
            # This RSET is just an implementation detail.  It's nice, but this
            # test doesn't really care about it.
            "RSET\r\n")



class MultipleDeliveryFactorySMTPServerFactory(protocol.ServerFactory):
    """
    L{MultipleDeliveryFactorySMTPServerFactory} creates SMTP server protocol
    instances with message delivery factory objects supplied to it.  Each
    factory is used for one connection and then discarded.  Factories are used
    in the order they are supplied.
    """
    def __init__(self, messageFactories):
        self._messageFactories = messageFactories


    def buildProtocol(self, addr):
        p = protocol.ServerFactory.buildProtocol(self, addr)
        p.delivery = SimpleDelivery(self._messageFactories.pop(0))
        return p



class SMTPSenderFactoryRetryTestCase(unittest.TestCase):
    """
    Tests for the retry behavior of L{smtp.SMTPSenderFactory}.
    """
    def test_retryAfterDisconnect(self):
        """
        If the protocol created by L{SMTPSenderFactory} loses its connection
        before receiving confirmation of message delivery, it reconnects and
        tries to deliver the message again.
        """
        recipient = 'alice'
        message = "some message text"
        domain = DummyDomain([recipient])

        class CleanSMTP(smtp.SMTP):
            """
            An SMTP subclass which ensures that its transport will be
            disconnected before the test ends.
            """
            def makeConnection(innerSelf, transport):
                self.addCleanup(transport.loseConnection)
                smtp.SMTP.makeConnection(innerSelf, transport)

        # Create a server which will fail the first message deliver attempt to
        # it with a 500 and a disconnect, but which will accept a message
        # delivered over the 2nd connection to it.
        serverFactory = MultipleDeliveryFactorySMTPServerFactory([
                BrokenMessage,
                lambda user: DummyMessage(domain, user)])
        serverFactory.protocol = CleanSMTP
        serverPort = reactor.listenTCP(0, serverFactory, interface='127.0.0.1')
        serverHost = serverPort.getHost()
        self.addCleanup(serverPort.stopListening)

        # Set up a client to try to deliver a message to the above created
        # server.
        sentDeferred = defer.Deferred()
        clientFactory = smtp.SMTPSenderFactory(
            "bob@example.org", recipient + "@example.com",
            StringIO(message), sentDeferred)
        clientFactory.domain = "example.org"
        clientConnector = reactor.connectTCP(
            serverHost.host, serverHost.port, clientFactory)
        self.addCleanup(clientConnector.disconnect)

        def cbSent(ignored):
            """
            Verify that the message was successfully delivered and flush the
            error which caused the first attempt to fail.
            """
            self.assertEqual(
                domain.messages,
                {recipient: ["\n%s\n" % (message,)]})
            # Flush the RuntimeError that BrokenMessage caused to be logged.
            self.assertEqual(len(self.flushLoggedErrors(RuntimeError)), 1)
        sentDeferred.addCallback(cbSent)
        return sentDeferred



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


    def test_unexpectedLoginFailure(self):
        """
        If the L{Deferred} returned by L{Portal.login} fires with an
        exception of any type other than L{UnauthorizedLogin}, the exception
        is logged and the client is informed that the authentication attempt
        has failed.
        """
        loginArgs = []
        self.server.portal = self.portalFactory(loginArgs)

        self.server.dataReceived('EHLO\r\n')
        self.transport.clear()

        self.assertServerResponse(
            'AUTH LOGIN ' + 'username'.encode('base64').strip() + '\r\n',
            ['334 ' + 'Password\0'.encode('base64').strip()])
        self.assertServerResponse(
            'password'.encode('base64').strip() + '\r\n',
            [])

        d, credentials, mind, interfaces = loginArgs.pop()
        d.errback(RuntimeError("Something wrong with the server"))

        self.assertEqual(
            '451 Requested action aborted: local error in processing\r\n',
            self.transport.value())

        self.assertEqual(len(self.flushLoggedErrors(RuntimeError)), 1)



class SMTPClientErrorTestCase(unittest.TestCase):
    """
    Tests for L{smtp.SMTPClientError}.
    """
    def test_str(self):
        """
        The string representation of a L{SMTPClientError} instance includes
        the response code and response string.
        """
        err = smtp.SMTPClientError(123, "some text")
        self.assertEqual(str(err), "123 some text")


    def test_strWithNegativeCode(self):
        """
        If the response code supplied to L{SMTPClientError} is negative, it
        is excluded from the string representation.
        """
        err = smtp.SMTPClientError(-1, "foo bar")
        self.assertEqual(str(err), "foo bar")


    def test_strWithLog(self):
        """
        If a line log is supplied to L{SMTPClientError}, its contents are
        included in the string representation of the exception instance.
        """
        log = LineLog(10)
        log.append("testlog")
        log.append("secondline")
        err = smtp.SMTPClientError(100, "test error", log=log.str())
        self.assertEqual(
            str(err),
            "100 test error\n"
            "testlog\n"
            "secondline\n")



class SenderMixinSentMailTests(unittest.TestCase):
    """
    Tests for L{smtp.SenderMixin.sentMail}, used in particular by
    L{smtp.SMTPSenderFactory} and L{smtp.ESMTPSenderFactory}.
    """
    def test_onlyLogFailedAddresses(self):
        """
        L{smtp.SenderMixin.sentMail} adds only the addresses with failing
        SMTP response codes to the log passed to the factory's errback.
        """
        onDone = self.assertFailure(defer.Deferred(), smtp.SMTPDeliveryError)
        onDone.addCallback(lambda e: self.assertEqual(
                e.log, "bob@example.com: 199 Error in sending.\n"))

        clientFactory = smtp.SMTPSenderFactory(
            'source@address', 'recipient@address',
            StringIO("Message body"), onDone,
            retries=0, timeout=0.5)

        client = clientFactory.buildProtocol(
            address.IPv4Address('TCP', 'example.net', 25))

        addresses = [("alice@example.com", 200, "No errors here!"),
                     ("bob@example.com", 199, "Error in sending.")]
        client.sentMail(199, "Test response", 1, addresses, client.log)

        return onDone
