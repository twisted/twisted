
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
Test cases for twisted.protocols.pop3 module.
"""

import StringIO
import string
import hmac
import base64

from twisted.trial import unittest
from twisted import mail
import twisted.mail.protocols
import twisted.protocols.pop3
import twisted.internet.protocol
from twisted import protocols
from twisted import internet
from twisted.protocols import pop3
from twisted.internet import protocol
from twisted.test.test_protocols import StringIOWithoutClosing
from twisted.protocols import loopback
from twisted.python import failure

from twisted import cred
import twisted.cred.portal
import twisted.cred.checkers
import twisted.cred.credentials

from proto_helpers import LineSendingProtocol

class MyVirtualPOP3(mail.protocols.VirtualPOP3):

    magic = '<moshez>'
    
    def authenticateUserAPOP(self, user, digest):
        user, domain = self.lookupDomain(user)
        return self.service.domains['baz.com'].authenticateUserAPOP(user, digest, self.magic, domain)
    
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
            return map(len, self.list)
        return len(self.list[i])

    def getMessage(self, i):
        return StringIO.StringIO(self.list[i])

    def getUidl(self, i):
        return i

    def deleteMessage(self, i):
        self.list[i] = ''

    def sync(self):
        pass

class MyPOP3Downloader(pop3.POP3Client):

    def handle_WELCOME(self, line):
        pop3.POP3Client.handle_WELCOME(self, line)
        self.apop('hello@baz.com', 'world')

    def handle_APOP(self, line):
        parts = line.split()
        code = parts[0]
        data = (parts[1:] or ['NONE'])[0]
        if code != '+OK':
            print parts
            raise AssertionError, 'code is ' + code
        self.lines = []
        self.retr(1)

    def handle_RETR_continue(self, line):
        self.lines.append(line)

    def handle_RETR_end(self):
        self.message = '\n'.join(self.lines) + '\n'
        self.quit()

    def handle_QUIT(self, line):
        if line[:3] != '+OK':
            raise AssertionError, 'code is '+code


class POP3TestCase(unittest.TestCase):

    message = '''\
Subject: urgent

Someone set up us the bomb!
'''

    expectedOutput = '''\
+OK <moshez>\015
+OK Authentication succeeded\015
+OK \015
1 0\015
.\015
+OK %d\015
Subject: urgent\015
\015
Someone set up us the bomb!\015
.\015
+OK \015
''' % len(message)

    def setUp(self):
        self.factory = internet.protocol.Factory()
        self.factory.domains = {}
        self.factory.domains['baz.com'] = DummyDomain()
        self.factory.domains['baz.com'].addUser('hello')
        self.factory.domains['baz.com'].addMessage('hello', self.message)

    def testMessages(self):
        client = LineSendingProtocol([
            'APOP hello@baz.com world',
            'UIDL',
            'RETR 1',
            'QUIT',
        ])
        server =  MyVirtualPOP3()
        server.service = self.factory
        loopback.loopbackTCP(server, client)
        
        output = '\r\n'.join(client.response) + '\r\n'
        self.assertEquals(output, self.expectedOutput)

    def testLoopback(self):
        protocol =  MyVirtualPOP3()
        protocol.service = self.factory
        clientProtocol = MyPOP3Downloader()
        loopback.loopback(protocol, clientProtocol)
        self.failUnlessEqual(clientProtocol.message, self.message)
        protocol.connectionLost(failure.Failure(Exception("Test harness disconnect")))


class DummyPOP3(pop3.POP3):

    magic = '<moshez>'

    def authenticateUserAPOP(self, user, password):
        return pop3.IMailbox, DummyMailbox(), lambda: None

class DummyMailbox(pop3.Mailbox):

    messages = [
'''\
From: moshe
To: moshe

How are you, friend?
''']

    def __init__(self):
        self.messages = DummyMailbox.messages[:]

    def listMessages(self, i=None):
        if i is None:
            return map(len, self.messages)
        return len(self.messages[i])

    def getMessage(self, i):
        return StringIO.StringIO(self.messages[i])

    def getUidl(self, i):
        return str(i)

    def deleteMessage(self, i):
        self.messages[i] = ''


class AnotherPOP3TestCase(unittest.TestCase):

    def runTest(self, lines, expected):
        dummy = DummyPOP3()
        client = LineSendingProtocol([
            "APOP moshez dummy",
            "LIST",
            "UIDL",
            "RETR 1",
            "RETR 2",
            "DELE 1",
            "RETR 1",
            "QUIT",
        ])
        expected_output = '+OK <moshez>\r\n+OK Authentication succeeded\r\n+OK 1\r\n1 44\r\n.\r\n+OK \r\n1 0\r\n.\r\n+OK 44\r\nFrom: moshe\r\nTo: moshe\r\n\r\nHow are you, friend?\r\n.\r\n-ERR index out of range\r\n+OK \r\n-ERR message deleted\r\n+OK \r\n'
        loopback.loopback(dummy, client)
        self.failUnlessEqual(expected_output, '\r\n'.join(client.response) + '\r\n')
        dummy.connectionLost(failure.Failure(Exception("Test harness disconnect")))
                             

    def testBuffer(self):
        lines = string.split('''\
APOP moshez dummy
LIST
UIDL
RETR 1
RETR 2
DELE 1
RETR 1
QUIT''', '\n')
        expected_output = '+OK <moshez>\r\n+OK Authentication succeeded\r\n+OK 1\r\n1 44\r\n.\r\n+OK \r\n1 0\r\n.\r\n+OK 44\r\nFrom: moshe\r\nTo: moshe\r\n\r\nHow are you, friend?\r\n.\r\n-ERR index out of range\r\n+OK \r\n-ERR message deleted\r\n+OK \r\n'
        self.runTest(lines, expected_output)

    def testNoop(self):
        lines = ['APOP spiv dummy', 'NOOP', 'QUIT']
        expected_output = '+OK <moshez>\r\n+OK Authentication succeeded\r\n+OK \r\n+OK \r\n'
        self.runTest(lines, expected_output)

    def testAuthListing(self):
        p = DummyPOP3()
        p.factory = internet.protocol.Factory()
        p.factory.challengers = {'Auth1': None, 'secondAuth': None, 'authLast': None}
        client = LineSendingProtocol([
            "AUTH",
            "QUIT",
        ])
        
        loopback.loopback(p, client)
        self.failUnless(client.response[1].startswith('+OK'))
        self.assertEquals(client.response[2:6], ["AUTH1", "SECONDAUTH", "AUTHLAST", "."])
    
    def testIllegalPASS(self):
        dummy = DummyPOP3()
        client = LineSendingProtocol([
            "PASS fooz",
            "QUIT"
        ])
        expected_output = '+OK <moshez>\r\n-ERR USER required before PASS\r\n+OK \r\n'
        loopback.loopback(dummy, client)
        self.failUnlessEqual(expected_output, '\r\n'.join(client.response) + '\r\n')
        dummy.connectionLost(failure.Failure(Exception("Test harness disconnect")))


class TestServerFactory:
    __implements__ = (pop3.IServerFactory,)

    def cap_IMPLEMENTATION(self):
        return "Test Implementation String"
    
    def cap_EXPIRE(self):
        return 60
    
    challengers = {"SCHEME_1": None, "SCHEME_2": None}
        
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

class CapabilityTestCase(unittest.TestCase):
    def setUp(self):
        s = StringIO.StringIO()
        p = pop3.POP3()
        p.factory = TestServerFactory()
        p.transport = internet.protocol.FileWrapper(s)
        p.connectionMade()
        p.do_CAPA()
        
        self.caps = p.listCapabilities()
        self.pcaps = s.getvalue().splitlines()

        s = StringIO.StringIO()
        p.mbox = TestMailbox()
        p.transport = internet.protocol.FileWrapper(s)
        p.do_CAPA()

        self.lpcaps = s.getvalue().splitlines()
        p.connectionLost(failure.Failure(Exception("Test harness disconnect")))

    def contained(self, s, *caps):
        for c in caps:
            self.assertIn(s, c)

    def testUIDL(self):
        self.contained("UIDL", self.caps, self.pcaps, self.lpcaps)
        
    def testTOP(self):
        self.contained("TOP", self.caps, self.pcaps, self.lpcaps)
    
    def testUSER(self):
        self.contained("USER", self.caps, self.pcaps, self.lpcaps)
    
    def testEXPIRE(self):
        self.contained("EXPIRE 60 USER", self.caps, self.pcaps)
        self.contained("EXPIRE 25", self.lpcaps)
    
    def testIMPLEMENTATION(self):
        self.contained(
            "IMPLEMENTATION Test Implementation String",
            self.caps, self.pcaps, self.lpcaps
        )

    def testSASL(self):
        self.contained(
            "SASL SCHEME_1 SCHEME_2",
            self.caps, self.pcaps, self.lpcaps
        )
    
    def testLOGIN_DELAY(self):
        self.contained("LOGIN-DELAY 120 USER", self.caps, self.pcaps)
        self.assertIn("LOGIN-DELAY 100", self.lpcaps)

class GlobalCapabilitiesTestCase(unittest.TestCase):
    def setUp(self):
        s = StringIO.StringIO()
        p = pop3.POP3()
        p.factory = TestServerFactory()
        p.factory.pue = p.factory.puld = False
        p.transport = internet.protocol.FileWrapper(s)
        p.connectionMade()
        p.do_CAPA()
        
        self.caps = p.listCapabilities()
        self.pcaps = s.getvalue().splitlines()

        s = StringIO.StringIO()
        p.mbox = TestMailbox()
        p.transport = internet.protocol.FileWrapper(s)
        p.do_CAPA()

        self.lpcaps = s.getvalue().splitlines()
        p.connectionLost(failure.Failure(Exception("Test harness disconnect")))

    def contained(self, s, *caps):
        for c in caps:
            self.assertIn(s, c)

    def testEXPIRE(self):
        self.contained("EXPIRE 60", self.caps, self.pcaps, self.lpcaps)
    
    def testLOGIN_DELAY(self):
        self.contained("LOGIN-DELAY 120", self.caps, self.pcaps, self.lpcaps)

class TestRealm:
    def requestAvatar(self, avatarId, mind, *interfaces):
        if avatarId == 'testuser':
            return pop3.IMailbox, DummyMailbox(), lambda: None
        assert False

class SASLTestCase(unittest.TestCase):
    def testValidLogin(self):
        p = pop3.POP3()
        p.factory = TestServerFactory()
        p.factory.challengers = {'CRAM-MD5': cred.credentials.CramMD5Credentials}
        p.portal = cred.portal.Portal(TestRealm())
        ch = cred.checkers.InMemoryUsernamePasswordDatabaseDontUse()
        ch.addUser('testuser', 'testpassword')
        p.portal.registerChecker(ch)
        
        s = StringIO.StringIO()
        p.transport = internet.protocol.FileWrapper(s)
        p.connectionMade()
        
        p.lineReceived("CAPA")
        self.failUnless(s.getvalue().find("SASL CRAM-MD5") >= 0)

        p.lineReceived("AUTH CRAM-MD5")
        chal = s.getvalue().splitlines()[-1][2:]
        chal = base64.decodestring(chal)
        response = hmac.HMAC('testpassword', chal).hexdigest()

        p.lineReceived(base64.encodestring('testuser ' + response).rstrip('\n'))
        self.failUnless(p.mbox)
        self.failUnless(s.getvalue().splitlines()[-1].find("+OK") >= 0)
        p.connectionLost(failure.Failure(Exception("Test harness disconnect")))

class DualFunctionTestCase(unittest.TestCase):
    def testLIST(self):
        p = pop3.POP3()
        p.mbox = DummyMailbox()
            
        s = StringIO.StringIO()
        p.transport = internet.protocol.FileWrapper(s)
        p.connectionMade()
        s.truncate(0)
        
        p.lineReceived("LIST 1")
        self.assertEquals(s.getvalue(), "+OK 44\r\n")
        s.truncate(0)
        
        p.lineReceived("LIST")
        self.assertEquals(s.getvalue(), "+OK 1\r\n1 44\r\n.\r\n")
        s.truncate(0)

        p.connectionLost(failure.Failure(Exception("Test harness disconnect")))

    
    def testUIDL(self):
        p = pop3.POP3()
        p.mbox = DummyMailbox()
        
        s = StringIO.StringIO()
        p.transport = internet.protocol.FileWrapper(s)
        p.connectionMade()
        s.truncate(0)
        
        p.lineReceived("UIDL 1")
        self.assertEquals(s.getvalue(), "+OK 0\r\n")
        s.truncate(0)
        
        p.lineReceived("UIDL")
        self.assertEquals(s.getvalue(), "+OK \r\n1 0\r\n.\r\n")
        s.truncate(0)

        p.connectionLost(failure.Failure(Exception("Test harness disconnect")))
