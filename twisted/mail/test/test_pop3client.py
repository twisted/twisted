# -*- test-case-name: twisted.mail.test.test_pop3client -*-
# Copyright (c) 2001-2004 Divmod Inc.
# See LICENSE for details.

from twisted.mail.pop3 import AdvancedPOP3Client as POP3Client
from twisted.mail.pop3 import InsecureAuthenticationDisallowed
from twisted.mail.pop3 import ServerErrorResponse
from twisted.protocols import loopback
from twisted.internet import defer, error

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

class POP3ClientLoginTestCase(unittest.TestCase):
    def testNegativeGreeting(self):
        p, t = setUp(greet=False)
        p.allowInsecureLogin = True
        d = p.login("username", "password")
        p.dataReceived('-ERR Offline for maintenance\r\n')
        return unittest.assertFailure(
            d, ServerErrorResponse).addCallback(
            lambda exc: self.assertEquals(exc.args[0], "Offline for maintenance"))


    def testOkUser(self):
        p, t = setUp()
        d = p.user("username")
        self.assertEquals(t.value(), "USER username\r\n")
        p.dataReceived("+OK send password\r\n")
        return d.addCallback(unittest.assertEqual, "send password")

    def testBadUser(self):
        p, t = setUp()
        d = p.user("username")
        self.assertEquals(t.value(), "USER username\r\n")
        p.dataReceived("-ERR account suspended\r\n")
        return unittest.assertFailure(
            d, ServerErrorResponse).addCallback(
            lambda exc: self.assertEquals(exc.args[0], "account suspended"))

    def testOkPass(self):
        p, t = setUp()
        d = p.password("password")
        self.assertEquals(t.value(), "PASS password\r\n")
        p.dataReceived("+OK you're in!\r\n")
        return d.addCallback(unittest.assertEqual, "you're in!")

    def testBadPass(self):
        p, t = setUp()
        d = p.password("password")
        self.assertEquals(t.value(), "PASS password\r\n")
        p.dataReceived("-ERR go away\r\n")
        return unittest.assertFailure(
            d, ServerErrorResponse).addCallback(
            lambda exc: self.assertEquals(exc.args[0], "go away"))

    def testOkLogin(self):
        p, t = setUp()
        p.allowInsecureLogin = True
        d = p.login("username", "password")
        self.assertEquals(t.value(), "USER username\r\n")
        p.dataReceived("+OK go ahead\r\n")
        self.assertEquals(t.value(), "USER username\r\nPASS password\r\n")
        p.dataReceived("+OK password accepted\r\n")
        return d.addCallback(unittest.assertEqual, "password accepted")

    def testBadPasswordLogin(self):
        p, t = setUp()
        p.allowInsecureLogin = True
        d = p.login("username", "password")
        self.assertEquals(t.value(), "USER username\r\n")
        p.dataReceived("+OK waiting on you\r\n")
        self.assertEquals(t.value(), "USER username\r\nPASS password\r\n")
        p.dataReceived("-ERR bogus login\r\n")
        return unittest.assertFailure(
            d, ServerErrorResponse).addCallback(
            lambda exc: self.assertEquals(exc.args[0], "bogus login"))

    def testBadUsernameLogin(self):
        p, t = setUp()
        p.allowInsecureLogin = True
        d = p.login("username", "password")
        self.assertEquals(t.value(), "USER username\r\n")
        p.dataReceived("-ERR bogus login\r\n")
        return unittest.assertFailure(
            d, ServerErrorResponse).addCallback(
            lambda exc: self.assertEquals(exc.args[0], "bogus login"))

    def testServerGreeting(self):
        p, t = setUp(greet=False)
        p.dataReceived("+OK lalala this has no challenge\r\n")
        self.assertEquals(p.serverChallenge, None)

    def testServerGreetingWithChallenge(self):
        p, t = setUp(greet=False)
        p.dataReceived("+OK <here is the challenge>\r\n")
        self.assertEquals(p.serverChallenge, "<here is the challenge>")

    def testAPOP(self):
        p, t = setUp(greet=False)
        p.dataReceived("+OK <challenge string goes here>\r\n")
        d = p.login("username", "password")
        self.assertEquals(t.value(), "APOP username f34f1e464d0d7927607753129cabe39a\r\n")
        p.dataReceived("+OK Welcome!\r\n")
        return d.addCallback(unittest.assertEqual, "Welcome!")

    def testInsecureLoginRaisesException(self):
        p, t = setUp(greet=False)
        p.dataReceived("+OK Howdy")
        d = p.login("username", "password")
        self.failIf(t.value())
        return unittest.assertFailure(
            d, InsecureAuthenticationDisallowed)

class ListConsumer:
    def __init__(self):
        self.data = {}

    def consume(self, (item, value)):
        self.data.setdefault(item, []).append(value)

class MessageConsumer:
    def __init__(self):
        self.data = []

    def consume(self, line):
        self.data.append(line)

class POP3ClientListTestCase(unittest.TestCase):
    def testListSize(self):
        p, t = setUp()
        d = p.listSize()
        self.assertEquals(t.value(), "LIST\r\n")
        p.dataReceived("+OK Here it comes\r\n")
        p.dataReceived("1 3\r\n2 2\r\n3 1\r\n.\r\n")
        return d.addCallback(unittest.assertEqual, [3, 2, 1])

    def testListSizeWithConsumer(self):
        p, t = setUp()
        c = ListConsumer()
        f = c.consume
        d = p.listSize(f)
        self.assertEquals(t.value(), "LIST\r\n")
        p.dataReceived("+OK Here it comes\r\n")
        p.dataReceived("1 3\r\n2 2\r\n3 1\r\n")
        self.assertEquals(c.data, {0: [3], 1: [2], 2: [1]})
        p.dataReceived("5 3\r\n6 2\r\n7 1\r\n")
        self.assertEquals(c.data, {0: [3], 1: [2], 2: [1], 4: [3], 5: [2], 6: [1]})
        p.dataReceived(".\r\n")
        return d.addCallback(unittest.assertIdentical, f)

    def testFailedListSize(self):
        p, t = setUp()
        d = p.listSize()
        self.assertEquals(t.value(), "LIST\r\n")
        p.dataReceived("-ERR Fatal doom server exploded\r\n")
        return unittest.assertFailure(
            d, ServerErrorResponse).addCallback(
            lambda exc: self.assertEquals(exc.args[0], "Fatal doom server exploded"))

    def testListUID(self):
        p, t = setUp()
        d = p.listUID()
        self.assertEquals(t.value(), "UIDL\r\n")
        p.dataReceived("+OK Here it comes\r\n")
        p.dataReceived("1 abc\r\n2 def\r\n3 ghi\r\n.\r\n")
        return d.addCallback(unittest.assertEqual, ["abc", "def", "ghi"])

    def testListUIDWithConsumer(self):
        p, t = setUp()
        c = ListConsumer()
        f = c.consume
        d = p.listUID(f)
        self.assertEquals(t.value(), "UIDL\r\n")
        p.dataReceived("+OK Here it comes\r\n")
        p.dataReceived("1 xyz\r\n2 abc\r\n5 mno\r\n")
        self.assertEquals(c.data, {0: ["xyz"], 1: ["abc"], 4: ["mno"]})
        p.dataReceived(".\r\n")
        return d.addCallback(unittest.assertIdentical, f)

    def testFailedListUID(self):
        p, t = setUp()
        d = p.listUID()
        self.assertEquals(t.value(), "UIDL\r\n")
        p.dataReceived("-ERR Fatal doom server exploded\r\n")
        return unittest.assertFailure(
            d, ServerErrorResponse).addCallback(
            lambda exc: self.assertEquals(exc.args[0], "Fatal doom server exploded"))

class POP3ClientMessageTestCase(unittest.TestCase):
    def testRetrieve(self):
        p, t = setUp()
        d = p.retrieve(7)
        self.assertEquals(t.value(), "RETR 8\r\n")
        p.dataReceived("+OK Message incoming\r\n")
        p.dataReceived("La la la here is message text\r\n")
        p.dataReceived("..Further message text tra la la\r\n")
        p.dataReceived(".\r\n")
        return d.addCallback(
            unittest.assertEqual,
            ["La la la here is message text",
             ".Further message text tra la la"])

    def testRetrieveWithConsumer(self):
        p, t = setUp()
        c = MessageConsumer()
        f = c.consume
        d = p.retrieve(7, f)
        self.assertEquals(t.value(), "RETR 8\r\n")
        p.dataReceived("+OK Message incoming\r\n")
        p.dataReceived("La la la here is message text\r\n")
        p.dataReceived("..Further message text\r\n.\r\n")
        self.assertIdentical(unittest.wait(d), f)
        self.assertEquals(c.data, ["La la la here is message text",
                                   ".Further message text"])

    def testPartialRetrieve(self):
        p, t = setUp()
        d = p.retrieve(7, lines=2)
        self.assertEquals(t.value(), "TOP 8 2\r\n")
        p.dataReceived("+OK 2 lines on the way\r\n")
        p.dataReceived("Line the first!  Woop\r\n")
        p.dataReceived("Line the last!  Bye\r\n")
        p.dataReceived(".\r\n")
        return d.addCallback(
            unittest.assertEqual,
            ["Line the first!  Woop",
             "Line the last!  Bye"])

    def testPartialRetrieveWithConsumer(self):
        p, t = setUp()
        c = MessageConsumer()
        f = c.consume
        d = p.retrieve(7, f, lines=2)
        self.assertEquals(t.value(), "TOP 8 2\r\n")
        p.dataReceived("+OK 2 lines on the way\r\n")
        p.dataReceived("Line the first!  Woop\r\n")
        p.dataReceived("Line the last!  Bye\r\n")
        p.dataReceived(".\r\n")
        self.assertIdentical(unittest.wait(d), f)
        self.assertEquals(c.data, ["Line the first!  Woop",
                                   "Line the last!  Bye"])

    def testFailedRetrieve(self):
        p, t = setUp()
        d = p.retrieve(0)
        self.assertEquals(t.value(), "RETR 1\r\n")
        p.dataReceived("-ERR Fatal doom server exploded\r\n")
        return unittest.assertFailure(
            d, ServerErrorResponse).addCallback(
            lambda exc: self.assertEquals(exc.args[0], "Fatal doom server exploded"))


class POP3ClientMiscTestCase(unittest.TestCase):
    def testCapability(self):
        p, t = setUp()
        d = p.capabilities(useCache=0)
        self.assertEquals(t.value(), "CAPA\r\n")
        p.dataReceived("+OK Capabilities on the way\r\n")
        p.dataReceived("X\r\nY\r\nZ\r\nA 1 2 3\r\nB 1 2\r\nC 1\r\n.\r\n")
        return d.addCallback(
            unittest.assertEqual,
            {"X": None, "Y": None, "Z": None,
             "A": ["1", "2", "3"],
             "B": ["1", "2"],
             "C": ["1"]})

    def testCapabilityError(self):
        p, t = setUp()
        d = p.capabilities(useCache=0)
        self.assertEquals(t.value(), "CAPA\r\n")
        p.dataReceived("-ERR This server is lame!\r\n")
        return unittest.assertFailure(
            d, ServerErrorResponse).addCallback(
            lambda exc: self.assertEquals(exc.args[0], "This server is lame!"))

    def testStat(self):
        p, t = setUp()
        d = p.stat()
        self.assertEquals(t.value(), "STAT\r\n")
        p.dataReceived("+OK 1 1212\r\n")
        return d.addCallback(unittest.assertEqual, (1, 1212))

    def testStatError(self):
        p, t = setUp()
        d = p.stat()
        self.assertEquals(t.value(), "STAT\r\n")
        p.dataReceived("-ERR This server is lame!\r\n")
        return unittest.assertFailure(
            d, ServerErrorResponse).addCallback(
            lambda exc: self.assertEquals(exc.args[0], "This server is lame!"))

    def testNoop(self):
        p, t = setUp()
        d = p.noop()
        self.assertEquals(t.value(), "NOOP\r\n")
        p.dataReceived("+OK No-op to you too!\r\n")
        return d.addCallback(unittest.assertEqual, "No-op to you too!")

    def testNoopError(self):
        p, t = setUp()
        d = p.noop()
        self.assertEquals(t.value(), "NOOP\r\n")
        p.dataReceived("-ERR This server is lame!\r\n")
        return unittest.assertFailure(
            d, ServerErrorResponse).addCallback(
            lambda exc: self.assertEquals(exc.args[0], "This server is lame!"))

    def testRset(self):
        p, t = setUp()
        d = p.reset()
        self.assertEquals(t.value(), "RSET\r\n")
        p.dataReceived("+OK Reset state\r\n")
        return d.addCallback(unittest.assertEqual, "Reset state")

    def testRsetError(self):
        p, t = setUp()
        d = p.reset()
        self.assertEquals(t.value(), "RSET\r\n")
        p.dataReceived("-ERR This server is lame!\r\n")
        return unittest.assertFailure(
            d, ServerErrorResponse).addCallback(
            lambda exc: self.assertEquals(exc.args[0], "This server is lame!"))

    def testDelete(self):
        p, t = setUp()
        d = p.delete(3)
        self.assertEquals(t.value(), "DELE 4\r\n")
        p.dataReceived("+OK Hasta la vista\r\n")
        return d.addCallback(unittest.assertEqual, "Hasta la vista")

    def testDeleteError(self):
        p, t = setUp()
        d = p.delete(3)
        self.assertEquals(t.value(), "DELE 4\r\n")
        p.dataReceived("-ERR Winner is not you.\r\n")
        return unittest.assertFailure(
            d, ServerErrorResponse).addCallback(
            lambda exc: self.assertEquals(exc.args[0], "Winner is not you."))


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
        loopback.loopbackTCP(self.server, self.client, noisy=False)


class POP3TLSTestCase(POP3HelperMixin, unittest.TestCase):
    serverCTX = ServerTLSContext and ServerTLSContext()
    clientCTX = ClientTLSContext and ClientTLSContext()

    def testStartTLS(self):
        def login():
            # this will startTLS automatically
            return self.client.login('test', 'twisted')

        def quit():
            return self.client.quit()

        methods = [login, quit]
        map(self.connected.addCallback, map(strip, methods))
        self.connected.addCallbacks(self._cbStopClient, self._ebGeneral)
        self.loopback()


class POP3TimeoutTestCase(POP3HelperMixin, unittest.TestCase):
    def testTimeout(self):
        def login():
            #this will startTLS automatically
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
        self.loopback()


if ClientTLSContext is None:
    for case in (POP3TLSTestCase,):
        case.skip = "OpenSSL not present"
