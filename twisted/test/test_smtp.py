"""
Test cases for twisted.smtp module.
"""

from pyunit import unittest
from twisted.internet import main
import twisted.protocols.protocol, twisted.protocols.smtp
from twisted import protocols
from twisted.test.test_protocols import StringIOWithoutClosing


class DummyDomain:

   def __init__(self, names):
       self.messages = {}
       for name in names:
           self.messages[name] = []

   def exists(self, name, domain):
       return self.messages.has_key(name)

   def saveMessage(self, name, message, domain):
       self.messages[name].append(message)

class SMTPTestCase(unittest.TestCase):

    messages = [('foo@bar.com', ['foo@baz.com', 'qux@baz.com'], '''\
Subject: urgent\015
\015
Someone set up us the bomb!\015
''')]

    mbox = {'foo': ['Subject: urgent\n\nSomeone set up us the bomb!\n']}

    def setUp(self):
        s = main.Selector()
#        self.server = mail.VirtualSMTPServer(25, s)
        self.output = StringIOWithoutClosing()
        self.transport = protocols.protocol.FileWrapper(self.output)
        self.transport.server = self.server
#        self.server.domains['baz.com'] = DummyDomain(['foo'])

    def testMessages(self):
        protocol =  protocols.smtp.DomainSMTPHandler()
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
##        if self.mbox != self.server.domains['baz.com'].messages:
##            raise AssertionError(self.server.domains['baz.com'].messages)

testCases = [SMTPTestCase]
