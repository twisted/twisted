"""
Test cases for twisted.pop3 module.
"""

from pyunit import unittest
from twisted import mail
import twisted.protocols.pop3, twisted.protocols.protocol
from twisted import protocols
from twisted.test.test_protocols import StringIOWithoutClosing
import StringIO

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
            print `self.output.getvalue()`
            print `self.expectedOutput`
            raise AssertionError(self.output.getvalue(), self.expectedOutput)

testCases = [POP3TestCase]
