
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
Test cases for twisted.pop3 module.
"""

from pyunit import unittest
from twisted import mail
import twisted.protocols.pop3, twisted.protocols.protocol
from twisted import protocols
from twisted.test.test_protocols import StringIOWithoutClosing
from twisted.protocols import loopback
import StringIO, string

class MyVirtualPOP3(protocols.pop3.VirtualPOP3):

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

class MyPOP3Downloader(protocols.pop3.POP3Client):

    def handle_WELCOME(self, line):
        protocols.pop3.POP3Client.handle_WELCOME(self, line)
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
        code, data = string.split(line)
        if code != '+OK':
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
        protocol.factory = self.factory
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
        protocol.factory = self.factory
        clientProtocol = MyPOP3Downloader()
        loopback.loopback(protocol, clientProtocol)
        self.failUnlessEqual(clientProtocol.message, self.message)

testCases = [POP3TestCase]
