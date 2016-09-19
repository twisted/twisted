# -*- test-case-name: twisted.mail.test.test_pop3client -*-
# Copyright (c) 2001-2004 Divmod Inc.
# See LICENSE for details.

import sys
import inspect

from zope.interface import directlyProvides

from twisted.mail.pop3 import AdvancedPOP3Client as POP3Client
from twisted.mail.pop3 import InsecureAuthenticationDisallowed
from twisted.mail.pop3 import ServerErrorResponse
from twisted.protocols import loopback
from twisted.internet import reactor, defer, error, protocol, interfaces
from twisted.python import log

from twisted.trial import unittest
from twisted.test.proto_helpers import StringTransport
from twisted.protocols import basic

from twisted.mail.test import pop3testserver

try:
    from twisted.test.ssl_helpers import ClientTLSContext, ServerTLSContext
except ImportError:
    ClientTLSContext = ServerTLSContext = None



class StringTransportWithConnectionLosing(StringTransport):
    def loseConnection(self):
        self.protocol.connectionLost(error.ConnectionDone())


capCache = {"TOP": None, "LOGIN-DELAY": "180", "UIDL": None, \
            "STLS": None, "USER": None, "SASL": "LOGIN"}
def setUp(greet=True):
    p = POP3Client()

    # Skip the CAPA login will issue if it doesn't already have a
    # capability cache
    p._capCache = capCache

    t = StringTransportWithConnectionLosing()
    t.protocol = p
    p.makeConnection(t)

    if greet:
        p.dataReceived('+OK Hello!\r\n')

    return p, t



def strip(f):
    return lambda result, f=f: f()



class POP3ClientLoginTests(unittest.TestCase):
    def testNegativeGreeting(self):
        p, t = setUp(greet=False)
        p.allowInsecureLogin = True
        d = p.login("username", "password")
        p.dataReceived('-ERR Offline for maintenance\r\n')
        return self.assertFailure(
            d, ServerErrorResponse).addCallback(
            lambda exc: self.assertEqual(exc.args[0], "Offline for maintenance"))


    def testOkUser(self):
        p, t = setUp()
        d = p.user("username")
        self.assertEqual(t.value(), "USER username\r\n")
        p.dataReceived("+OK send password\r\n")
        return d.addCallback(self.assertEqual, "send password")


    def testBadUser(self):
        p, t = setUp()
        d = p.user("username")
        self.assertEqual(t.value(), "USER username\r\n")
        p.dataReceived("-ERR account suspended\r\n")
        return self.assertFailure(
            d, ServerErrorResponse).addCallback(
            lambda exc: self.assertEqual(exc.args[0], "account suspended"))


    def testOkPass(self):
        p, t = setUp()
        d = p.password("password")
        self.assertEqual(t.value(), "PASS password\r\n")
        p.dataReceived("+OK you're in!\r\n")
        return d.addCallback(self.assertEqual, "you're in!")


    def testBadPass(self):
        p, t = setUp()
        d = p.password("password")
        self.assertEqual(t.value(), "PASS password\r\n")
        p.dataReceived("-ERR go away\r\n")
        return self.assertFailure(
            d, ServerErrorResponse).addCallback(
            lambda exc: self.assertEqual(exc.args[0], "go away"))


    def testOkLogin(self):
        p, t = setUp()
        p.allowInsecureLogin = True
        d = p.login("username", "password")
        self.assertEqual(t.value(), "USER username\r\n")
        p.dataReceived("+OK go ahead\r\n")
        self.assertEqual(t.value(), "USER username\r\nPASS password\r\n")
        p.dataReceived("+OK password accepted\r\n")
        return d.addCallback(self.assertEqual, "password accepted")


    def testBadPasswordLogin(self):
        p, t = setUp()
        p.allowInsecureLogin = True
        d = p.login("username", "password")
        self.assertEqual(t.value(), "USER username\r\n")
        p.dataReceived("+OK waiting on you\r\n")
        self.assertEqual(t.value(), "USER username\r\nPASS password\r\n")
        p.dataReceived("-ERR bogus login\r\n")
        return self.assertFailure(
            d, ServerErrorResponse).addCallback(
            lambda exc: self.assertEqual(exc.args[0], "bogus login"))


    def testBadUsernameLogin(self):
        p, t = setUp()
        p.allowInsecureLogin = True
        d = p.login("username", "password")
        self.assertEqual(t.value(), "USER username\r\n")
        p.dataReceived("-ERR bogus login\r\n")
        return self.assertFailure(
            d, ServerErrorResponse).addCallback(
            lambda exc: self.assertEqual(exc.args[0], "bogus login"))


    def testServerGreeting(self):
        p, t = setUp(greet=False)
        p.dataReceived("+OK lalala this has no challenge\r\n")
        self.assertEqual(p.serverChallenge, None)


    def testServerGreetingWithChallenge(self):
        p, t = setUp(greet=False)
        p.dataReceived("+OK <here is the challenge>\r\n")
        self.assertEqual(p.serverChallenge, "<here is the challenge>")


    def testAPOP(self):
        p, t = setUp(greet=False)
        p.dataReceived("+OK <challenge string goes here>\r\n")
        d = p.login("username", "password")
        self.assertEqual(t.value(), "APOP username f34f1e464d0d7927607753129cabe39a\r\n")
        p.dataReceived("+OK Welcome!\r\n")
        return d.addCallback(self.assertEqual, "Welcome!")


    def testInsecureLoginRaisesException(self):
        p, t = setUp(greet=False)
        p.dataReceived("+OK Howdy\r\n")
        d = p.login("username", "password")
        self.assertFalse(t.value())
        return self.assertFailure(
            d, InsecureAuthenticationDisallowed)


    def testSSLTransportConsideredSecure(self):
        """
        If a server doesn't offer APOP but the transport is secured using
        SSL or TLS, a plaintext login should be allowed, not rejected with
        an InsecureAuthenticationDisallowed exception.
        """
        p, t = setUp(greet=False)
        directlyProvides(t, interfaces.ISSLTransport)
        p.dataReceived("+OK Howdy\r\n")
        d = p.login("username", "password")
        self.assertEqual(t.value(), "USER username\r\n")
        t.clear()
        p.dataReceived("+OK\r\n")
        self.assertEqual(t.value(), "PASS password\r\n")
        p.dataReceived("+OK\r\n")
        return d



class ListConsumer:
    def __init__(self):
        self.data = {}


    def consume(self, result):
        (item, value) = result
        self.data.setdefault(item, []).append(value)



class MessageConsumer:
    def __init__(self):
        self.data = []


    def consume(self, line):
        self.data.append(line)



class POP3ClientListTests(unittest.TestCase):
    def testListSize(self):
        p, t = setUp()
        d = p.listSize()
        self.assertEqual(t.value(), "LIST\r\n")
        p.dataReceived("+OK Here it comes\r\n")
        p.dataReceived("1 3\r\n2 2\r\n3 1\r\n.\r\n")
        return d.addCallback(self.assertEqual, [3, 2, 1])


    def testListSizeWithConsumer(self):
        p, t = setUp()
        c = ListConsumer()
        f = c.consume
        d = p.listSize(f)
        self.assertEqual(t.value(), "LIST\r\n")
        p.dataReceived("+OK Here it comes\r\n")
        p.dataReceived("1 3\r\n2 2\r\n3 1\r\n")
        self.assertEqual(c.data, {0: [3], 1: [2], 2: [1]})
        p.dataReceived("5 3\r\n6 2\r\n7 1\r\n")
        self.assertEqual(c.data, {0: [3], 1: [2], 2: [1], 4: [3], 5: [2], 6: [1]})
        p.dataReceived(".\r\n")
        return d.addCallback(self.assertIdentical, f)


    def testFailedListSize(self):
        p, t = setUp()
        d = p.listSize()
        self.assertEqual(t.value(), "LIST\r\n")
        p.dataReceived("-ERR Fatal doom server exploded\r\n")
        return self.assertFailure(
            d, ServerErrorResponse).addCallback(
            lambda exc: self.assertEqual(exc.args[0], "Fatal doom server exploded"))


    def testListUID(self):
        p, t = setUp()
        d = p.listUID()
        self.assertEqual(t.value(), "UIDL\r\n")
        p.dataReceived("+OK Here it comes\r\n")
        p.dataReceived("1 abc\r\n2 def\r\n3 ghi\r\n.\r\n")
        return d.addCallback(self.assertEqual, ["abc", "def", "ghi"])


    def testListUIDWithConsumer(self):
        p, t = setUp()
        c = ListConsumer()
        f = c.consume
        d = p.listUID(f)
        self.assertEqual(t.value(), "UIDL\r\n")
        p.dataReceived("+OK Here it comes\r\n")
        p.dataReceived("1 xyz\r\n2 abc\r\n5 mno\r\n")
        self.assertEqual(c.data, {0: ["xyz"], 1: ["abc"], 4: ["mno"]})
        p.dataReceived(".\r\n")
        return d.addCallback(self.assertIdentical, f)


    def testFailedListUID(self):
        p, t = setUp()
        d = p.listUID()
        self.assertEqual(t.value(), "UIDL\r\n")
        p.dataReceived("-ERR Fatal doom server exploded\r\n")
        return self.assertFailure(
            d, ServerErrorResponse).addCallback(
            lambda exc: self.assertEqual(exc.args[0], "Fatal doom server exploded"))



class POP3ClientMessageTests(unittest.TestCase):
    def testRetrieve(self):
        p, t = setUp()
        d = p.retrieve(7)
        self.assertEqual(t.value(), "RETR 8\r\n")
        p.dataReceived("+OK Message incoming\r\n")
        p.dataReceived("La la la here is message text\r\n")
        p.dataReceived("..Further message text tra la la\r\n")
        p.dataReceived(".\r\n")
        return d.addCallback(
            self.assertEqual,
            ["La la la here is message text",
             ".Further message text tra la la"])


    def testRetrieveWithConsumer(self):
        p, t = setUp()
        c = MessageConsumer()
        f = c.consume
        d = p.retrieve(7, f)
        self.assertEqual(t.value(), "RETR 8\r\n")
        p.dataReceived("+OK Message incoming\r\n")
        p.dataReceived("La la la here is message text\r\n")
        p.dataReceived("..Further message text\r\n.\r\n")
        return d.addCallback(self._cbTestRetrieveWithConsumer, f, c)


    def _cbTestRetrieveWithConsumer(self, result, f, c):
        self.assertIdentical(result, f)
        self.assertEqual(c.data, ["La la la here is message text",
                                   ".Further message text"])


    def testPartialRetrieve(self):
        p, t = setUp()
        d = p.retrieve(7, lines=2)
        self.assertEqual(t.value(), "TOP 8 2\r\n")
        p.dataReceived("+OK 2 lines on the way\r\n")
        p.dataReceived("Line the first!  Woop\r\n")
        p.dataReceived("Line the last!  Bye\r\n")
        p.dataReceived(".\r\n")
        return d.addCallback(
            self.assertEqual,
            ["Line the first!  Woop",
             "Line the last!  Bye"])


    def testPartialRetrieveWithConsumer(self):
        p, t = setUp()
        c = MessageConsumer()
        f = c.consume
        d = p.retrieve(7, f, lines=2)
        self.assertEqual(t.value(), "TOP 8 2\r\n")
        p.dataReceived("+OK 2 lines on the way\r\n")
        p.dataReceived("Line the first!  Woop\r\n")
        p.dataReceived("Line the last!  Bye\r\n")
        p.dataReceived(".\r\n")
        return d.addCallback(self._cbTestPartialRetrieveWithConsumer, f, c)


    def _cbTestPartialRetrieveWithConsumer(self, result, f, c):
        self.assertIdentical(result, f)
        self.assertEqual(c.data, ["Line the first!  Woop",
                                   "Line the last!  Bye"])


    def testFailedRetrieve(self):
        p, t = setUp()
        d = p.retrieve(0)
        self.assertEqual(t.value(), "RETR 1\r\n")
        p.dataReceived("-ERR Fatal doom server exploded\r\n")
        return self.assertFailure(
            d, ServerErrorResponse).addCallback(
            lambda exc: self.assertEqual(exc.args[0], "Fatal doom server exploded"))


    def test_concurrentRetrieves(self):
        """
        Issue three retrieve calls immediately without waiting for any to
        succeed and make sure they all do succeed eventually.
        """
        p, t = setUp()
        messages = [
            p.retrieve(i).addCallback(
                self.assertEqual,
                ["First line of %d." % (i + 1,),
                 "Second line of %d." % (i + 1,)])
            for i
            in range(3)]

        for i in range(1, 4):
            self.assertEqual(t.value(), "RETR %d\r\n" % (i,))
            t.clear()
            p.dataReceived("+OK 2 lines on the way\r\n")
            p.dataReceived("First line of %d.\r\n" % (i,))
            p.dataReceived("Second line of %d.\r\n" % (i,))
            self.assertEqual(t.value(), "")
            p.dataReceived(".\r\n")

        return defer.DeferredList(messages, fireOnOneErrback=True)



class POP3ClientMiscTests(unittest.TestCase):
    def testCapability(self):
        p, t = setUp()
        d = p.capabilities(useCache=0)
        self.assertEqual(t.value(), "CAPA\r\n")
        p.dataReceived("+OK Capabilities on the way\r\n")
        p.dataReceived("X\r\nY\r\nZ\r\nA 1 2 3\r\nB 1 2\r\nC 1\r\n.\r\n")
        return d.addCallback(
            self.assertEqual,
            {"X": None, "Y": None, "Z": None,
             "A": ["1", "2", "3"],
             "B": ["1", "2"],
             "C": ["1"]})


    def testCapabilityError(self):
        p, t = setUp()
        d = p.capabilities(useCache=0)
        self.assertEqual(t.value(), "CAPA\r\n")
        p.dataReceived("-ERR This server is lame!\r\n")
        return d.addCallback(self.assertEqual, {})


    def testStat(self):
        p, t = setUp()
        d = p.stat()
        self.assertEqual(t.value(), "STAT\r\n")
        p.dataReceived("+OK 1 1212\r\n")
        return d.addCallback(self.assertEqual, (1, 1212))


    def testStatError(self):
        p, t = setUp()
        d = p.stat()
        self.assertEqual(t.value(), "STAT\r\n")
        p.dataReceived("-ERR This server is lame!\r\n")
        return self.assertFailure(
            d, ServerErrorResponse).addCallback(
            lambda exc: self.assertEqual(exc.args[0], "This server is lame!"))


    def testNoop(self):
        p, t = setUp()
        d = p.noop()
        self.assertEqual(t.value(), "NOOP\r\n")
        p.dataReceived("+OK No-op to you too!\r\n")
        return d.addCallback(self.assertEqual, "No-op to you too!")


    def testNoopError(self):
        p, t = setUp()
        d = p.noop()
        self.assertEqual(t.value(), "NOOP\r\n")
        p.dataReceived("-ERR This server is lame!\r\n")
        return self.assertFailure(
            d, ServerErrorResponse).addCallback(
            lambda exc: self.assertEqual(exc.args[0], "This server is lame!"))


    def testRset(self):
        p, t = setUp()
        d = p.reset()
        self.assertEqual(t.value(), "RSET\r\n")
        p.dataReceived("+OK Reset state\r\n")
        return d.addCallback(self.assertEqual, "Reset state")


    def testRsetError(self):
        p, t = setUp()
        d = p.reset()
        self.assertEqual(t.value(), "RSET\r\n")
        p.dataReceived("-ERR This server is lame!\r\n")
        return self.assertFailure(
            d, ServerErrorResponse).addCallback(
            lambda exc: self.assertEqual(exc.args[0], "This server is lame!"))


    def testDelete(self):
        p, t = setUp()
        d = p.delete(3)
        self.assertEqual(t.value(), "DELE 4\r\n")
        p.dataReceived("+OK Hasta la vista\r\n")
        return d.addCallback(self.assertEqual, "Hasta la vista")


    def testDeleteError(self):
        p, t = setUp()
        d = p.delete(3)
        self.assertEqual(t.value(), "DELE 4\r\n")
        p.dataReceived("-ERR Winner is not you.\r\n")
        return self.assertFailure(
            d, ServerErrorResponse).addCallback(
            lambda exc: self.assertEqual(exc.args[0], "Winner is not you."))



class SimpleClient(POP3Client):
    def __init__(self, deferred, contextFactory = None):
        self.deferred = deferred
        self.allowInsecureLogin = True


    def serverGreeting(self, challenge):
        self.deferred.callback(None)



class POP3HelperMixin:
    serverCTX = None
    clientCTX = None

    def setUp(self):
        d = defer.Deferred()
        self.server = pop3testserver.POP3TestServer(contextFactory=self.serverCTX)
        self.client = SimpleClient(d, contextFactory=self.clientCTX)
        self.client.timeout = 30
        self.connected = d


    def tearDown(self):
        del self.server
        del self.client
        del self.connected


    def _cbStopClient(self, ignore):
        self.client.transport.loseConnection()


    def _ebGeneral(self, failure):
        self.client.transport.loseConnection()
        self.server.transport.loseConnection()
        return failure


    def loopback(self):
        return loopback.loopbackTCP(self.server, self.client, noisy=False)



class TLSServerFactory(protocol.ServerFactory):
    class protocol(basic.LineReceiver):
        context = None
        output = []
        def connectionMade(self):
            self.factory.input = []
            self.output = self.output[:]
            map(self.sendLine, self.output.pop(0))
        def lineReceived(self, line):
            self.factory.input.append(line)
            map(self.sendLine, self.output.pop(0))
            if line == 'STLS':
                self.transport.startTLS(self.context)



class POP3TLSTests(unittest.TestCase):
    """
    Tests for POP3Client's support for TLS connections.
    """

    def test_startTLS(self):
        """
        POP3Client.startTLS starts a TLS session over its existing TCP
        connection.
        """
        sf = TLSServerFactory()
        sf.protocol.output = [
            ['+OK'], # Server greeting
            ['+OK', 'STLS', '.'], # CAPA response
            ['+OK'], # STLS response
            ['+OK', '.'], # Second CAPA response
            ['+OK'] # QUIT response
            ]
        sf.protocol.context = ServerTLSContext()
        port = reactor.listenTCP(0, sf, interface='127.0.0.1')
        self.addCleanup(port.stopListening)
        H = port.getHost().host
        P = port.getHost().port

        connLostDeferred = defer.Deferred()
        cp = SimpleClient(defer.Deferred(), ClientTLSContext())
        def connectionLost(reason):
            SimpleClient.connectionLost(cp, reason)
            connLostDeferred.callback(None)
        cp.connectionLost = connectionLost
        cf = protocol.ClientFactory()
        cf.protocol = lambda: cp

        conn = reactor.connectTCP(H, P, cf)

        def cbConnected(ignored):
            log.msg("Connected to server; starting TLS")
            return cp.startTLS()

        def cbStartedTLS(ignored):
            log.msg("Started TLS; disconnecting")
            return cp.quit()

        def cbDisconnected(ign):
            log.msg("Disconnected; asserting correct input received")
            self.assertEqual(
                sf.input,
                ['CAPA', 'STLS', 'CAPA', 'QUIT'])

        def cleanup(result):
            log.msg("Asserted correct input; disconnecting client and shutting down server")
            conn.disconnect()
            return connLostDeferred

        cp.deferred.addCallback(cbConnected)
        cp.deferred.addCallback(cbStartedTLS)
        cp.deferred.addCallback(cbDisconnected)
        cp.deferred.addBoth(cleanup)

        return cp.deferred



class POP3TimeoutTests(POP3HelperMixin, unittest.TestCase):
    def testTimeout(self):
        def login():
            d = self.client.login('test', 'twisted')
            d.addCallback(loggedIn)
            d.addErrback(timedOut)
            return d

        def loggedIn(result):
            self.fail("Successfully logged in!?  Impossible!")


        def timedOut(failure):
            failure.trap(error.TimeoutError)
            self._cbStopClient(None)

        def quit():
            return self.client.quit()

        self.client.timeout = 0.01

        # Tell the server to not return a response to client.  This
        # will trigger a timeout.
        pop3testserver.TIMEOUT_RESPONSE = True

        methods = [login, quit]
        map(self.connected.addCallback, map(strip, methods))
        self.connected.addCallback(self._cbStopClient)
        self.connected.addErrback(self._ebGeneral)
        return self.loopback()



if ClientTLSContext is None:
    for case in (POP3TLSTests,):
        case.skip = "OpenSSL not present"
elif interfaces.IReactorSSL(reactor, None) is None:
    for case in (POP3TLSTests,):
        case.skip = "Reactor doesn't support SSL"



import twisted.mail.pop3client

class POP3ClientModuleStructureTests(unittest.TestCase):
    """
    Miscellaneous tests more to do with module/package structure than
    anything to do with the POP3 client.
    """
    def test_all(self):
        """
        twisted.mail.pop3client.__all__ should be empty because all classes
        should be imported through twisted.mail.pop3.
        """
        self.assertEqual(twisted.mail.pop3client.__all__, [])


    def test_import(self):
        """
        Every public class in twisted.mail.pop3client should be available as a
        member of twisted.mail.pop3 with the exception of
        twisted.mail.pop3client.POP3Client which should be available as
        twisted.mail.pop3.AdvancedClient.
        """
        publicClasses = [c[0] for c in inspect.getmembers(
                                       sys.modules['twisted.mail.pop3client'],
                                       inspect.isclass)
                         if not c[0][0] == '_']

        for pc in publicClasses:
            if not pc == 'POP3Client':
                self.assertTrue(hasattr(twisted.mail.pop3, pc))
            else:
                self.assertTrue(hasattr(twisted.mail.pop3,
                    'AdvancedPOP3Client'))
