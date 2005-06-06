# -*- test-case-name: twisted.mail.test.test_pop3client -*-
# Copyright (c) 2001-2004 Divmod Inc.
# See LICENSE for details.

from twisted.mail.pop3 import AdvancedPOP3Client as POP3Client
from twisted.mail.pop3 import InsecureAuthenticationDisallowed
from twisted.mail.pop3 import ServerErrorResponse

from twisted.trial import unittest
from twisted.test.proto_helpers import StringTransport

def setUp():
    p = POP3Client()
    t = StringTransport()
    p.makeConnection(t)
    return p, t

class POP3ClientLoginTestCase(unittest.TestCase):
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
        exc = self.assertRaises(ServerErrorResponse, unittest.wait, d)
        self.assertEquals(exc.args[0], "account suspended")

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
        exc = self.assertRaises(ServerErrorResponse, unittest.wait, d)
        self.assertEquals(exc.args[0], "go away")

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
        exc = self.assertRaises(ServerErrorResponse, unittest.wait, d)
        self.assertEquals(exc.args[0], "bogus login")

    def testBadUsernameLogin(self):
        p, t = setUp()
        p.allowInsecureLogin = True
        d = p.login("username", "password")
        self.assertEquals(t.value(), "USER username\r\n")
        p.dataReceived("-ERR bogus login\r\n")
        exc = self.assertRaises(ServerErrorResponse, unittest.wait, d)
        self.assertEquals(exc.args[0], "bogus login")

    def testServerGreeting(self):
        p, t = setUp()
        # Make sure it *isn't* in the instance dict, just for sanity
        self.failIfIn('serverChallenge', vars(p))
        p.dataReceived("+OK lalala this has no challenge\r\n")
        # Make sure it *is* in the instance dict and that it is None
        self.assertEquals(vars(p)['serverChallenge'], None)

    def testServerGreetingWithChallenge(self):
        p, t = setUp()
        # Make sure it *isn't* in the instance dict, just for sanity
        self.failIfIn('serverChallenge', vars(p))
        p.dataReceived("+OK <here is the challenge>\r\n")
        # Make sure it *is* in the instance dict and is what we sent
        self.assertEquals(vars(p)['serverChallenge'], "<here is the challenge>")

    def testAPOP(self):
        p, t = setUp()
        p.dataReceived("+OK <challenge string goes here>\r\n")
        d = p.login("username", "password")
        self.assertEquals(t.value(), "APOP username f34f1e464d0d7927607753129cabe39a\r\n")
        p.dataReceived("+OK Welcome!\r\n")
        return d.addCallback(unittest.assertEqual, "Welcome!")

    def testInsecureLoginRaisesException(self):
        p, t = setUp()
        p.dataReceived("+OK Howdy")
        d = p.login("username", "password")
        self.failIf(t.value())
        self.assertRaises(InsecureAuthenticationDisallowed, unittest.wait, d)

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
        exc = self.assertRaises(ServerErrorResponse, unittest.wait, d)
        self.assertEquals(exc.args[0], "Fatal doom server exploded")

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
        exc = self.assertRaises(ServerErrorResponse, unittest.wait, d)
        self.assertEquals(exc.args[0], "Fatal doom server exploded")

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
        exc = self.assertRaises(ServerErrorResponse, unittest.wait, d)
        self.assertEquals(exc.args[0], "Fatal doom server exploded")

class POP3ClientMiscTestCase(unittest.TestCase):
    def testCapability(self):
        p, t = setUp()
        d = p.capabilities()
        self.assertEquals(t.value(), "CAPA\r\n")
        p.dataReceived("+OK Capabilities on the way\r\n")
        p.dataReceived("X\r\nY\r\nZ\r\n.\r\n")
        return d.addCallback(unittest.assertEqual, ["X", "Y", "Z"])

    def testCapabilityWithConsumer(self):
        p, t = setUp()
        c = MessageConsumer()
        f = c.consume
        d = p.capabilities(f)
        self.assertEquals(t.value(), "CAPA\r\n")
        p.dataReceived("+OK Capabilities on the way\r\n")
        p.dataReceived("X\r\nY\r\nZ\r\n.\r\n")
        self.assertIdentical(unittest.wait(d), f)
        self.assertEquals(c.data, ["X", "Y", "Z"])

    def testCapabilityError(self):
        p, t = setUp()
        d = p.capabilities()
        self.assertEquals(t.value(), "CAPA\r\n")
        p.dataReceived("-ERR This server is lame!\r\n")
        exc = self.assertRaises(ServerErrorResponse, unittest.wait, d)
        self.assertEquals(exc.args[0], "This server is lame!")

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
        exc = self.assertRaises(ServerErrorResponse, unittest.wait, d)
        self.assertEquals(exc.args[0], "Winner is not you.")
