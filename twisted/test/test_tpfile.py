
# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.


from twisted.trial import unittest
from twisted.protocols import loopback
from twisted.protocols import basic
from twisted.internet import protocol

import StringIO

class BufferingServer(protocol.Protocol):
    buffer = ''
    def dataReceived(self, data):
        self.buffer += data

class FileSendingClient(protocol.Protocol):
    def __init__(self, f):
        self.f = f
    
    def connectionMade(self):
        s = basic.FileSender()
        d = s.beginFileTransfer(self.f, self.transport, lambda x: x)
        d.addCallback(lambda r: self.transport.loseConnection())

class FileSenderTestCase(unittest.TestCase):
    def testSendingFile(self):
        testStr = 'xyz' * 100 + 'abc' * 100 + '123' * 100
        s = BufferingServer()
        c = FileSendingClient(StringIO.StringIO(testStr))
        
        loopback.loopbackTCP(s, c)
        self.assertEquals(s.buffer, testStr)
