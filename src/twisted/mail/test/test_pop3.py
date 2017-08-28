# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Test cases for Ltwisted.mail.pop3} module.
"""

from __future__ import print_function

import hmac
import base64
import itertools

from collections import OrderedDict
from io import BytesIO

from zope.interface import implementer

from twisted import cred
from twisted import internet
from twisted import mail
from twisted.internet import defer
from twisted.mail import pop3
from twisted.protocols import loopback
from twisted.python import failure
from twisted.python.compat import intToBytes
from twisted.test.proto_helpers import LineSendingProtocol
from twisted.trial import unittest, util
import twisted.cred.checkers
import twisted.cred.credentials
import twisted.cred.portal
import twisted.internet.protocol
import twisted.mail.pop3
import twisted.mail.protocols


class UtilityTests(unittest.TestCase):
    """
    Test the various helper functions and classes used by the POP3 server
    protocol implementation.
    """

    def test_LineBuffering(self):
        """
        Test creating a LineBuffer and feeding it some lines.  The lines should
        build up in its internal buffer for a while and then get spat out to
        the writer.
        """
        output = []
        input = iter(itertools.cycle(['012', '345', '6', '7', '8', '9']))
        c = pop3._IteratorBuffer(output.extend, input, 6)
        i = iter(c)
        self.assertEqual(output, [])  # Nothing is buffer
        next(i)
        self.assertEqual(output, [])  # '012' is buffered
        next(i)
        self.assertEqual(output, [])  # '012345' is buffered
        next(i)
        self.assertEqual(output, ['012', '345', '6'])  # Nothing is buffered
        for n in range(5):
            next(i)
        self.assertEqual(output, ['012', '345', '6', '7', '8', '9', '012',
                                  '345'])


    def test_FinishLineBuffering(self):
        """
        Test that a LineBuffer flushes everything when its iterator is
        exhausted, and itself raises StopIteration.
        """
        output = []
        input = iter(['a', 'b', 'c'])
        c = pop3._IteratorBuffer(output.extend, input, 5)
        for i in c:
            pass
        self.assertEqual(output, ['a', 'b', 'c'])


    def test_SuccessResponseFormatter(self):
        """
        Test that the thing that spits out POP3 'success responses' works
        right.
        """
        self.assertEqual(
            pop3.successResponse(b'Great.'),
            b'+OK Great.\r\n')


    def test_StatLineFormatter(self):
        """
        Test that the function which formats stat lines does so appropriately.
        """
        statLine = list(pop3.formatStatResponse([]))[-1]
        self.assertEqual(statLine, b'+OK 0 0\r\n')

        statLine = list(pop3.formatStatResponse([10, 31, 0, 10101]))[-1]
        self.assertEqual(statLine, b'+OK 4 10142\r\n')


    def test_ListLineFormatter(self):
        """
        Test that the function which formats the lines in response to a LIST
        command does so appropriately.
        """
        listLines = list(pop3.formatListResponse([]))
        self.assertEqual(
            listLines,
            [b'+OK 0\r\n', b'.\r\n'])

        listLines = list(pop3.formatListResponse([1, 2, 3, 100]))
        self.assertEqual(
            listLines,
            [b'+OK 4\r\n', b'1 1\r\n', b'2 2\r\n', b'3 3\r\n', b'4 100\r\n',
             b'.\r\n'])


    def test_UIDListLineFormatter(self):
        """
        Test that the function which formats lines in response to a UIDL
        command does so appropriately.
        """
        UIDs = ['abc', 'def', 'ghi']
        listLines = list(pop3.formatUIDListResponse([], UIDs.__getitem__))
        self.assertEqual(
            listLines,
            [b'+OK \r\n', b'.\r\n'])

        listLines = list(pop3.formatUIDListResponse([123, 431, 591],
                         UIDs.__getitem__))
        self.assertEqual(
            listLines,
            [b'+OK \r\n', b'1 abc\r\n', b'2 def\r\n', b'3 ghi\r\n', b'.\r\n'])

        listLines = list(pop3.formatUIDListResponse([0, None, 591],
                         UIDs.__getitem__))
        self.assertEqual(
            listLines,
            [b'+OK \r\n', b'1 abc\r\n', b'3 ghi\r\n', b'.\r\n'])



class MyVirtualPOP3(mail.protocols.VirtualPOP3):

    magic = b'<moshez>'

    def authenticateUserAPOP(self, user, digest):
        user, domain = self.lookupDomain(user)
        return self.service.domains[b'baz.com'].authenticateUserAPOP(
            user, digest, self.magic, domain)



class DummyDomain:

    def __init__(self):
        self.users = {}


    def addUser(self, name):
        self.users[name] = []


    def addMessage(self, name, message):
        self.users[name].append(message)


    def authenticateUserAPOP(self, name, digest, magic, domain):
        return pop3.IMailbox, ListMailbox(self.users[name]), lambda: None



class ListMailbox:

    def __init__(self, list):
        self.list = list


    def listMessages(self, i=None):
        if i is None:
            return [len(l) for l in self.list]
        return len(self.list[i])


    def getMessage(self, i):
        return BytesIO(self.list[i])


    def getUidl(self, i):
        return i


    def deleteMessage(self, i):
        self.list[i] = b''


    def sync(self):
        pass



class MyPOP3Downloader(pop3.POP3Client):

    def handle_WELCOME(self, line):
        pop3.POP3Client.handle_WELCOME(self, line)
        self.apop(b'hello@baz.com', b'world')


    def handle_APOP(self, line):
        parts = line.split()
        code = parts[0]
        if code != b'+OK':
            raise AssertionError('code is: %s , parts is: %s ' % (code, parts))
        self.lines = []
        self.retr(1)


    def handle_RETR_continue(self, line):
        self.lines.append(line)


    def handle_RETR_end(self):
        self.message = b'\n'.join(self.lines) + b'\n'
        self.quit()


    def handle_QUIT(self, line):
        if line[:3] != b'+OK':
            raise AssertionError(b'code is ' + line)



class POP3Tests(unittest.TestCase):

    message = b'''\
Subject: urgent

Someone set up us the bomb!
'''

    expectedOutput = (b'''\
+OK <moshez>\015
+OK Authentication succeeded\015
+OK \015
1 0\015
.\015
+OK ''' + intToBytes(len(message)) + b'''\015
Subject: urgent\015
\015
Someone set up us the bomb!\015
.\015
+OK \015
''')

    def setUp(self):
        self.factory = internet.protocol.Factory()
        self.factory.domains = {}
        self.factory.domains[b'baz.com'] = DummyDomain()
        self.factory.domains[b'baz.com'].addUser(b'hello')
        self.factory.domains[b'baz.com'].addMessage(b'hello', self.message)


    def test_Messages(self):
        client = LineSendingProtocol([
            b'APOP hello@baz.com world',
            b'UIDL',
            b'RETR 1',
            b'QUIT',
        ])
        server = MyVirtualPOP3()
        server.service = self.factory
        def check(ignored):
            output = b'\r\n'.join(client.response) + b'\r\n'
            self.assertEqual(output, self.expectedOutput)
        return loopback.loopbackTCP(server, client).addCallback(check)


    def test_Loopback(self):
        protocol = MyVirtualPOP3()
        protocol.service = self.factory
        clientProtocol = MyPOP3Downloader()
        def check(ignored):
            self.assertEqual(clientProtocol.message, self.message)
            protocol.connectionLost(
                failure.Failure(Exception("Test harness disconnect")))
        d = loopback.loopbackAsync(protocol, clientProtocol)
        return d.addCallback(check)
    test_Loopback.suppress = [util.suppress(
         message="twisted.mail.pop3.POP3Client is deprecated")]


    def test_incorrectDomain(self):
        """
        Look up a user in a domain which this server does not support.
        """
        factory = internet.protocol.Factory()
        factory.domains = {}
        factory.domains[b'twistedmatrix.com'] = DummyDomain()

        server = MyVirtualPOP3()
        server.service = factory
        exc = self.assertRaises(pop3.POP3Error,
            server.authenticateUserAPOP, b'nobody@baz.com', b'password')
        self.assertEqual(exc.args[0], "no such domain " + repr(b'baz.com'))



class DummyPOP3(pop3.POP3):

    magic = b'<moshez>'

    def authenticateUserAPOP(self, user, password):
        return pop3.IMailbox, DummyMailbox(ValueError), lambda: None



class DummyMailbox(pop3.Mailbox):

    messages = [b'From: moshe\nTo: moshe\n\nHow are you, friend?\n']

    def __init__(self, exceptionType):
        self.messages = DummyMailbox.messages[:]
        self.exceptionType = exceptionType


    def listMessages(self, i=None):
        if i is None:
            return [len(m) for m in self.messages]
        if i >= len(self.messages):
            raise self.exceptionType()
        return len(self.messages[i])


    def getMessage(self, i):
        return BytesIO(self.messages[i])


    def getUidl(self, i):
        if i >= len(self.messages):
            raise self.exceptionType()
        return intToBytes(i)


    def deleteMessage(self, i):
        self.messages[i] = b''



class AnotherPOP3Tests(unittest.TestCase):

    def runTest(self, lines, expectedOutput):
        dummy = DummyPOP3()
        client = LineSendingProtocol(lines)
        d = loopback.loopbackAsync(dummy, client)
        return d.addCallback(self._cbRunTest, client, dummy, expectedOutput)


    def _cbRunTest(self, ignored, client, dummy, expectedOutput):
        self.assertEqual(b'\r\n'.join(expectedOutput),
                         b'\r\n'.join(client.response))
        dummy.connectionLost(failure.Failure(
                             Exception("Test harness disconnect")))
        return ignored


    def test_buffer(self):
        """
        Test a lot of different POP3 commands in an extremely pipelined
        scenario.

        This test may cover legitimate behavior, but the intent and
        granularity are not very good.  It would likely be an improvement to
        split it into a number of smaller, more focused tests.
        """
        return self.runTest(
            [b"APOP moshez dummy",
             b"LIST",
             b"UIDL",
             b"RETR 1",
             b"RETR 2",
             b"DELE 1",
             b"RETR 1",
             b"QUIT"],
            [b'+OK <moshez>',
             b'+OK Authentication succeeded',
             b'+OK 1',
             b'1 44',
             b'.',
             b'+OK ',
             b'1 0',
             b'.',
             b'+OK 44',
             b'From: moshe',
             b'To: moshe',
             b'',
             b'How are you, friend?',
             b'.',
             b'-ERR Bad message number argument',
             b'+OK ',
             b'-ERR message deleted',
             b'+OK '])


    def test_noop(self):
        """
        Test the no-op command.
        """
        return self.runTest(
            [b'APOP spiv dummy',
             b'NOOP',
             b'QUIT'],
            [b'+OK <moshez>',
             b'+OK Authentication succeeded',
             b'+OK ',
             b'+OK '])


    def test_AuthListing(self):
        p = DummyPOP3()
        p.factory = internet.protocol.Factory()
        p.factory.challengers = {b'Auth1': None, b'secondAuth': None,
                                 b'authLast': None}
        client = LineSendingProtocol([
            b"AUTH",
            b"QUIT",
        ])

        d = loopback.loopbackAsync(p, client)
        return d.addCallback(self._cbTestAuthListing, client)


    def _cbTestAuthListing(self, ignored, client):
        self.assertTrue(client.response[1].startswith(b'+OK'))
        self.assertEqual(sorted(client.response[2:5]),
                         [b"AUTH1", b"AUTHLAST", b"SECONDAUTH"])
        self.assertEqual(client.response[5], b".")


    def test_IllegalPASS(self):
        dummy = DummyPOP3()
        client = LineSendingProtocol([
            b"PASS fooz",
            b"QUIT"
        ])
        d = loopback.loopbackAsync(dummy, client)
        return d.addCallback(self._cbTestIllegalPASS, client, dummy)


    def _cbTestIllegalPASS(self, ignored, client, dummy):
        expected_output = (
            b'+OK <moshez>\r\n-ERR USER required before PASS\r\n+OK \r\n')
        self.assertEqual(expected_output,
                         b'\r\n'.join(client.response) + b'\r\n')
        dummy.connectionLost(failure.Failure(
                             Exception("Test harness disconnect")))


    def test_EmptyPASS(self):
        dummy = DummyPOP3()
        client = LineSendingProtocol([
            b"PASS ",
            b"QUIT"
        ])
        d = loopback.loopbackAsync(dummy, client)
        return d.addCallback(self._cbTestEmptyPASS, client, dummy)


    def _cbTestEmptyPASS(self, ignored, client, dummy):
        expected_output = (
            b'+OK <moshez>\r\n-ERR USER required before PASS\r\n+OK \r\n')
        self.assertEqual(expected_output,
                         b'\r\n'.join(client.response) + b'\r\n')
        dummy.connectionLost(failure.Failure(
                             Exception("Test harness disconnect")))



@implementer(pop3.IServerFactory)
class TestServerFactory:
    def cap_IMPLEMENTATION(self):
        return "Test Implementation String"


    def cap_EXPIRE(self):
        return 60

    challengers = OrderedDict([(b"SCHEME_1", None), (b"SCHEME_2", None)])

    def cap_LOGIN_DELAY(self):
        return 120

    pue = True
    def perUserExpiration(self):
        return self.pue

    puld = True
    def perUserLoginDelay(self):
        return self.puld



class TestMailbox:
    loginDelay = 100
    messageExpiration = 25



class CapabilityTests(unittest.TestCase):
    def setUp(self):
        s = BytesIO()
        p = pop3.POP3()
        p.factory = TestServerFactory()
        p.transport = internet.protocol.FileWrapper(s)
        p.connectionMade()
        p.do_CAPA()

        self.caps = p.listCapabilities()
        self.pcaps = s.getvalue().splitlines()

        s = BytesIO()
        p.mbox = TestMailbox()
        p.transport = internet.protocol.FileWrapper(s)
        p.do_CAPA()

        self.lpcaps = s.getvalue().splitlines()
        p.connectionLost(failure.Failure(Exception("Test harness disconnect")))


    def contained(self, s, *caps):
        for c in caps:
            self.assertIn(s, c)


    def test_UIDL(self):
        self.contained(b"UIDL", self.caps, self.pcaps, self.lpcaps)


    def test_TOP(self):
        self.contained(b"TOP", self.caps, self.pcaps, self.lpcaps)


    def test_USER(self):
        self.contained(b"USER", self.caps, self.pcaps, self.lpcaps)


    def test_EXPIRE(self):
        self.contained(b"EXPIRE 60 USER", self.caps, self.pcaps)
        self.contained(b"EXPIRE 25", self.lpcaps)


    def test_IMPLEMENTATION(self):
        self.contained(
            b"IMPLEMENTATION Test Implementation String",
            self.caps, self.pcaps, self.lpcaps
        )


    def test_SASL(self):
        self.contained(
            b"SASL SCHEME_1 SCHEME_2",
            self.caps, self.pcaps, self.lpcaps
        )


    def test_LOGIN_DELAY(self):
        self.contained(b"LOGIN-DELAY 120 USER", self.caps, self.pcaps)
        self.assertIn(b"LOGIN-DELAY 100", self.lpcaps)



class GlobalCapabilitiesTests(unittest.TestCase):
    def setUp(self):
        s = BytesIO()
        p = pop3.POP3()
        p.factory = TestServerFactory()
        p.factory.pue = p.factory.puld = False
        p.transport = internet.protocol.FileWrapper(s)
        p.connectionMade()
        p.do_CAPA()

        self.caps = p.listCapabilities()
        self.pcaps = s.getvalue().splitlines()

        s = BytesIO()
        p.mbox = TestMailbox()
        p.transport = internet.protocol.FileWrapper(s)
        p.do_CAPA()

        self.lpcaps = s.getvalue().splitlines()
        p.connectionLost(failure.Failure(Exception("Test harness disconnect")))


    def contained(self, s, *caps):
        for c in caps:
            self.assertIn(s, c)


    def test_EXPIRE(self):
        self.contained(b"EXPIRE 60", self.caps, self.pcaps, self.lpcaps)


    def test_LOGIN_DELAY(self):
        self.contained(b"LOGIN-DELAY 120", self.caps, self.pcaps, self.lpcaps)



class TestRealm:
    def requestAvatar(self, avatarId, mind, *interfaces):
        if avatarId == b'testuser':
            return pop3.IMailbox, DummyMailbox(ValueError), lambda: None
        assert False



class SASLTests(unittest.TestCase):
    def test_ValidLogin(self):
        p = pop3.POP3()
        p.factory = TestServerFactory()
        p.factory.challengers = {b'CRAM-MD5':
                                 cred.credentials.CramMD5Credentials}
        p.portal = cred.portal.Portal(TestRealm())
        ch = cred.checkers.InMemoryUsernamePasswordDatabaseDontUse()
        ch.addUser(b'testuser', b'testpassword')
        p.portal.registerChecker(ch)

        s = BytesIO()
        p.transport = internet.protocol.FileWrapper(s)
        p.connectionMade()

        p.lineReceived(b"CAPA")
        self.assertTrue(s.getvalue().find(b"SASL CRAM-MD5") >= 0)

        p.lineReceived(b"AUTH CRAM-MD5")
        chal = s.getvalue().splitlines()[-1][2:]
        chal = base64.decodestring(chal)
        response = hmac.HMAC(b'testpassword', chal).hexdigest().encode("utf-8")

        p.lineReceived(
            base64.encodestring(b'testuser ' + response).rstrip(b'\n'))
        self.assertTrue(p.mbox)
        self.assertTrue(s.getvalue().splitlines()[-1].find(b"+OK") >= 0)
        p.connectionLost(failure.Failure(Exception("Test harness disconnect")))



class CommandMixin:
    """
    Tests for all the commands a POP3 server is allowed to receive.
    """

    extraMessage = b'''\
From: guy
To: fellow

More message text for you.
'''


    def setUp(self):
        """
        Make a POP3 server protocol instance hooked up to a simple mailbox and
        a transport that buffers output to a BytesIO.
        """
        p = pop3.POP3()
        p.mbox = self.mailboxType(self.exceptionType)
        p.schedule = list
        self.pop3Server = p

        s = BytesIO()
        p.transport = internet.protocol.FileWrapper(s)
        p.connectionMade()
        s.seek(0)
        s.truncate(0)
        self.pop3Transport = s


    def tearDown(self):
        """
        Disconnect the server protocol so it can clean up anything it might
        need to clean up.
        """
        self.pop3Server.connectionLost(failure.Failure(
                                       Exception("Test harness disconnect")))


    def _flush(self):
        """
        Do some of the things that the reactor would take care of, if the
        reactor were actually running.
        """
        # Oh man FileWrapper is pooh.
        self.pop3Server.transport._checkProducer()


    def test_LIST(self):
        """
        Test the two forms of list: with a message index number, which should
        return a short-form response, and without a message index number, which
        should return a long-form response, one line per message.
        """
        p = self.pop3Server
        s = self.pop3Transport

        p.lineReceived(b"LIST 1")
        self._flush()
        self.assertEqual(s.getvalue(), b"+OK 1 44\r\n")
        s.seek(0)
        s.truncate(0)

        p.lineReceived(b"LIST")
        self._flush()
        self.assertEqual(s.getvalue(), b"+OK 1\r\n1 44\r\n.\r\n")


    def test_LISTWithBadArgument(self):
        """
        Test that non-integers and out-of-bound integers produce appropriate
        error responses.
        """
        p = self.pop3Server
        s = self.pop3Transport

        p.lineReceived(b"LIST a")
        self.assertEqual(
            s.getvalue(),
            b"-ERR Invalid message-number: a\r\n")
        s.seek(0)
        s.truncate(0)

        p.lineReceived(b"LIST 0")
        self.assertEqual(
            s.getvalue(),
            b"-ERR Invalid message-number: 0\r\n")
        s.seek(0)
        s.truncate(0)

        p.lineReceived(b"LIST 2")
        self.assertEqual(
            s.getvalue(),
            b"-ERR Invalid message-number: 2\r\n")
        s.seek(0)
        s.truncate(0)


    def test_UIDL(self):
        """
        Test the two forms of the UIDL command.  These are just like the two
        forms of the LIST command.
        """
        p = self.pop3Server
        s = self.pop3Transport

        p.lineReceived(b"UIDL 1")
        self.assertEqual(s.getvalue(), b"+OK 0\r\n")
        s.seek(0)
        s.truncate(0)

        p.lineReceived(b"UIDL")
        self._flush()
        self.assertEqual(s.getvalue(), b"+OK \r\n1 0\r\n.\r\n")


    def test_UIDLWithBadArgument(self):
        """
        Test that UIDL with a non-integer or an out-of-bounds integer produces
        the appropriate error response.
        """
        p = self.pop3Server
        s = self.pop3Transport

        p.lineReceived(b"UIDL a")
        self.assertEqual(
            s.getvalue(),
            b"-ERR Bad message number argument\r\n")
        s.seek(0)
        s.truncate(0)

        p.lineReceived(b"UIDL 0")
        self.assertEqual(
            s.getvalue(),
            b"-ERR Bad message number argument\r\n")
        s.seek(0)
        s.truncate(0)

        p.lineReceived(b"UIDL 2")
        self.assertEqual(
            s.getvalue(),
            b"-ERR Bad message number argument\r\n")
        s.seek(0)
        s.truncate(0)


    def test_STAT(self):
        """
        Test the single form of the STAT command, which returns a short-form
        response of the number of messages in the mailbox and their total size.
        """
        p = self.pop3Server
        s = self.pop3Transport

        p.lineReceived(b"STAT")
        self._flush()
        self.assertEqual(s.getvalue(), b"+OK 1 44\r\n")


    def test_RETR(self):
        """
        Test downloading a message.
        """
        p = self.pop3Server
        s = self.pop3Transport

        p.lineReceived(b"RETR 1")
        self._flush()
        self.assertEqual(
            s.getvalue(),
            b"+OK 44\r\n"
            b"From: moshe\r\n"
            b"To: moshe\r\n"
            b"\r\n"
            b"How are you, friend?\r\n"
            b".\r\n")
        s.seek(0)
        s.truncate(0)


    def test_RETRWithBadArgument(self):
        """
        Test that trying to download a message with a bad argument, either not
        an integer or an out-of-bounds integer, fails with the appropriate
        error response.
        """
        p = self.pop3Server
        s = self.pop3Transport

        p.lineReceived(b"RETR a")
        self.assertEqual(
            s.getvalue(),
            b"-ERR Bad message number argument\r\n")
        s.seek(0)
        s.truncate(0)

        p.lineReceived(b"RETR 0")
        self.assertEqual(
            s.getvalue(),
            b"-ERR Bad message number argument\r\n")
        s.seek(0)
        s.truncate(0)

        p.lineReceived(b"RETR 2")
        self.assertEqual(
            s.getvalue(),
            b"-ERR Bad message number argument\r\n")
        s.seek(0)
        s.truncate(0)


    def test_TOP(self):
        """
        Test downloading the headers and part of the body of a message.
        """
        p = self.pop3Server
        s = self.pop3Transport
        p.mbox.messages.append(self.extraMessage)

        p.lineReceived(b"TOP 1 0")
        self._flush()
        self.assertEqual(
            s.getvalue(),
            b"+OK Top of message follows\r\n"
            b"From: moshe\r\n"
            b"To: moshe\r\n"
            b"\r\n"
            b".\r\n")


    def test_TOPWithBadArgument(self):
        """
        Test that trying to download a message with a bad argument, either a
        message number which isn't an integer or is an out-of-bounds integer or
        a number of lines which isn't an integer or is a negative integer,
        fails with the appropriate error response.
        """
        p = self.pop3Server
        s = self.pop3Transport
        p.mbox.messages.append(self.extraMessage)

        p.lineReceived(b"TOP 1 a")
        self.assertEqual(
            s.getvalue(),
            b"-ERR Bad line count argument\r\n")
        s.seek(0)
        s.truncate(0)

        p.lineReceived(b"TOP 1 -1")
        self.assertEqual(
            s.getvalue(),
            b"-ERR Bad line count argument\r\n")
        s.seek(0)
        s.truncate(0)

        p.lineReceived(b"TOP a 1")
        self.assertEqual(
            s.getvalue(),
            b"-ERR Bad message number argument\r\n")
        s.seek(0)
        s.truncate(0)

        p.lineReceived(b"TOP 0 1")
        self.assertEqual(
            s.getvalue(),
            b"-ERR Bad message number argument\r\n")
        s.seek(0)
        s.truncate(0)

        p.lineReceived(b"TOP 3 1")
        self.assertEqual(
            s.getvalue(),
            b"-ERR Bad message number argument\r\n")
        s.seek(0)
        s.truncate(0)


    def test_LAST(self):
        """
        Test the exceedingly pointless LAST command, which tells you the
        highest message index which you have already downloaded.
        """
        p = self.pop3Server
        s = self.pop3Transport
        p.mbox.messages.append(self.extraMessage)

        p.lineReceived(b'LAST')
        self.assertEqual(
            s.getvalue(),
            b"+OK 0\r\n")
        s.seek(0)
        s.truncate(0)


    def test_RetrieveUpdatesHighest(self):
        """
        Test that issuing a RETR command updates the LAST response.
        """
        p = self.pop3Server
        s = self.pop3Transport
        p.mbox.messages.append(self.extraMessage)

        p.lineReceived(b'RETR 2')
        self._flush()
        s.seek(0)
        s.truncate(0)
        p.lineReceived(b'LAST')
        self.assertEqual(
            s.getvalue(),
            b'+OK 2\r\n')
        s.seek(0)
        s.truncate(0)


    def test_TopUpdatesHighest(self):
        """
        Test that issuing a TOP command updates the LAST response.
        """
        p = self.pop3Server
        s = self.pop3Transport
        p.mbox.messages.append(self.extraMessage)

        p.lineReceived(b'TOP 2 10')
        self._flush()
        s.seek(0)
        s.truncate(0)
        p.lineReceived(b'LAST')
        self.assertEqual(
            s.getvalue(),
            b'+OK 2\r\n')


    def test_HighestOnlyProgresses(self):
        """
        Test that downloading a message with a smaller index than the current
        LAST response doesn't change the LAST response.
        """
        p = self.pop3Server
        s = self.pop3Transport
        p.mbox.messages.append(self.extraMessage)

        p.lineReceived(b'RETR 2')
        self._flush()
        p.lineReceived(b'TOP 1 10')
        self._flush()
        s.seek(0)
        s.truncate(0)
        p.lineReceived(b'LAST')
        self.assertEqual(
            s.getvalue(),
            b'+OK 2\r\n')


    def test_ResetClearsHighest(self):
        """
        Test that issuing RSET changes the LAST response to 0.
        """
        p = self.pop3Server
        s = self.pop3Transport
        p.mbox.messages.append(self.extraMessage)

        p.lineReceived(b'RETR 2')
        self._flush()
        p.lineReceived(b'RSET')
        s.seek(0)
        s.truncate(0)
        p.lineReceived(b'LAST')
        self.assertEqual(
            s.getvalue(),
            b'+OK 0\r\n')



_listMessageDeprecation = (
    "twisted.mail.pop3.IMailbox.listMessages may not "
    "raise IndexError for out-of-bounds message numbers: "
    "raise ValueError instead.")
_listMessageSuppression = util.suppress(
    message=_listMessageDeprecation,
    category=PendingDeprecationWarning)

_getUidlDeprecation = (
    "twisted.mail.pop3.IMailbox.getUidl may not "
    "raise IndexError for out-of-bounds message numbers: "
    "raise ValueError instead.")
_getUidlSuppression = util.suppress(
    message=_getUidlDeprecation,
    category=PendingDeprecationWarning)

class IndexErrorCommandTests(CommandMixin, unittest.TestCase):
    """
    Run all of the command tests against a mailbox which raises IndexError
    when an out of bounds request is made.  This behavior will be deprecated
    shortly and then removed.
    """
    exceptionType = IndexError
    mailboxType = DummyMailbox

    def test_LISTWithBadArgument(self):
        return CommandMixin.test_LISTWithBadArgument(self)
    test_LISTWithBadArgument.suppress = [_listMessageSuppression]


    def test_UIDLWithBadArgument(self):
        return CommandMixin.test_UIDLWithBadArgument(self)
    test_UIDLWithBadArgument.suppress = [_getUidlSuppression]


    def test_TOPWithBadArgument(self):
        return CommandMixin.test_TOPWithBadArgument(self)
    test_TOPWithBadArgument.suppress = [_listMessageSuppression]


    def test_RETRWithBadArgument(self):
        return CommandMixin.test_RETRWithBadArgument(self)
    test_RETRWithBadArgument.suppress = [_listMessageSuppression]



class ValueErrorCommandTests(CommandMixin, unittest.TestCase):
    """
    Run all of the command tests against a mailbox which raises ValueError
    when an out of bounds request is made.  This is the correct behavior and
    after support for mailboxes which raise IndexError is removed, this will
    become just C{CommandTestCase}.
    """
    exceptionType = ValueError
    mailboxType = DummyMailbox



class SyncDeferredMailbox(DummyMailbox):
    """
    Mailbox which has a listMessages implementation which returns a Deferred
    which has already fired.
    """
    def listMessages(self, n=None):
        return defer.succeed(DummyMailbox.listMessages(self, n))



class IndexErrorSyncDeferredCommandTests(IndexErrorCommandTests):
    """
    Run all of the L{IndexErrorCommandTests} tests with a
    synchronous-Deferred returning IMailbox implementation.
    """
    mailboxType = SyncDeferredMailbox



class ValueErrorSyncDeferredCommandTests(ValueErrorCommandTests):
    """
    Run all of the L{ValueErrorCommandTests} tests with a
    synchronous-Deferred returning IMailbox implementation.
    """
    mailboxType = SyncDeferredMailbox



class AsyncDeferredMailbox(DummyMailbox):
    """
    Mailbox which has a listMessages implementation which returns a Deferred
    which has not yet fired.
    """
    def __init__(self, *a, **kw):
        self.waiting = []
        DummyMailbox.__init__(self, *a, **kw)


    def listMessages(self, n=None):
        d = defer.Deferred()
        # See AsyncDeferredMailbox._flush
        self.waiting.append((d, DummyMailbox.listMessages(self, n)))
        return d



class IndexErrorAsyncDeferredCommandTests(IndexErrorCommandTests):
    """
    Run all of the L{IndexErrorCommandTests} tests with an
    asynchronous-Deferred returning IMailbox implementation.
    """
    mailboxType = AsyncDeferredMailbox

    def _flush(self):
        """
        Fire whatever Deferreds we've built up in our mailbox.
        """
        while self.pop3Server.mbox.waiting:
            d, a = self.pop3Server.mbox.waiting.pop()
            d.callback(a)
        IndexErrorCommandTests._flush(self)



class ValueErrorAsyncDeferredCommandTests(ValueErrorCommandTests):
    """
    Run all of the L{IndexErrorCommandTests} tests with an
    asynchronous-Deferred returning IMailbox implementation.
    """
    mailboxType = AsyncDeferredMailbox

    def _flush(self):
        """
        Fire whatever Deferreds we've built up in our mailbox.
        """
        while self.pop3Server.mbox.waiting:
            d, a = self.pop3Server.mbox.waiting.pop()
            d.callback(a)
        ValueErrorCommandTests._flush(self)



class POP3MiscTests(unittest.TestCase):
    """
    Miscellaneous tests more to do with module/package structure than
    anything to do with the Post Office Protocol.
    """
    def test_all(self):
        """
        This test checks that all names listed in
        twisted.mail.pop3.__all__ are actually present in the module.
        """
        mod = twisted.mail.pop3
        for attr in mod.__all__:
            self.assertTrue(hasattr(mod, attr))
