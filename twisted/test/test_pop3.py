
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

from pyunit import unittest
from twisted import mail
import twisted.mail.protocols
import twisted.protocols.pop3, twisted.protocols.protocol
from twisted import protocols
from twisted.protocols import pop3
from twisted.internet import protocol
from twisted.test.test_protocols import StringIOWithoutClosing
from twisted.protocols import loopback
import StringIO, string

class MyVirtualPOP3(mail.protocols.VirtualPOP3):

    magic = '<moshez>'

class DummyDomain:

   def __init__(self):
       self.users = {}

   def addUser(self, name):
       self.users[name] = []

   def addMessage(self, name, message):
       self.users[name].append(message)

   def authenticateUserAPOP(self, name, magic, digest, domain):
       return ListMailbox(self.users[name])


class ListMailbox:

    def __init__(self, list):
        self.list = list

    def listMessages(self):
        return map(len, self.list)

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
        parts = string.split(line)
        code = parts[0]
        data = (parts[1:] or ['NONE'])[0]
        if code != '+OK':
            raise AssertionError, 'code is '+code
        self.lines = []
        self.retr(1)

    def handle_RETR_continue(self, line):
        self.lines.append(line)

    def handle_RETR_end(self):
        self.message = string.join(self.lines, '\n')+'\n'
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
+OK \015
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
        self.factory = protocols.protocol.Factory()
        self.factory.domains = {}
        self.factory.domains['baz.com'] = DummyDomain()
        self.factory.domains['baz.com'].addUser('hello')
        self.factory.domains['baz.com'].addMessage('hello', self.message)

    def testMessages(self):
        self.output = StringIOWithoutClosing()
        self.transport = protocols.protocol.FileWrapper(self.output)
        protocol =  MyVirtualPOP3()
        protocol.makeConnection(self.transport)
        protocol.service = self.factory
        protocol.lineReceived('APOP hello@baz.com world')
        protocol.lineReceived('UIDL')
        protocol.lineReceived('RETR 1')
        protocol.lineReceived('QUIT')
        if self.output.getvalue() != self.expectedOutput:
            #print `self.output.getvalue()`
            #print `self.expectedOutput`
            raise AssertionError(self.output.getvalue(), self.expectedOutput)

    def testLoopback(self):
        protocol =  MyVirtualPOP3()
        protocol.service = self.factory
        clientProtocol = MyPOP3Downloader()
        loopback.loopback(protocol, clientProtocol)
        self.failUnlessEqual(clientProtocol.message, self.message)


class DummyPOP3(pop3.POP3):

    magic = '<moshez>'

    def authenticateUserAPOP(self, user, password):
        return DummyMailbox()

class DummyMailbox(pop3.Mailbox):

    messages = [
'''\
From: moshe
To: moshe

How are you, friend?
''']

    def __init__(self):
        self.messages = DummyMailbox.messages[:]

    def listMessages(self):
        return map(len, self.messages)

    def getMessage(self, i):
        return StringIO.StringIO(self.messages[i])

    def getUidl(self, i):
        return str(i)

    def deleteMessage(self, i):
        self.messages[i] = ''


class AnotherPOP3TestCase(unittest.TestCase):

    def testBuffer(self):
        a = StringIOWithoutClosing()
        dummy = DummyPOP3()
        dummy.makeConnection(protocol.FileWrapper(a))
        lines = string.split('''\
APOP moshez dummy
LIST
UIDL
RETR 1
RETR 2
DELE 1
RETR 1
QUIT''', '\n')
        expected_output = '+OK <moshez>\r\n+OK \r\n+OK 1\r\n1 44\r\n.\r\n+OK \r\n1 0\r\n.\r\n+OK 44\r\nFrom: moshe\r\nTo: moshe\r\n\r\nHow are you, friend?\r\n.\r\n-ERR index out of range\r\n+OK \r\n-ERR message deleted\r\n+OK \r\n'
        for line in lines:
            dummy.lineReceived(line)
        self.failUnlessEqual(expected_output, a.getvalue(),
                             "\nExpected:\n%s\nResults:\n%s\n"
                             % (expected_output, a.getvalue()))


testCases = [POP3TestCase, AnotherPOP3TestCase]
