
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
