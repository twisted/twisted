#
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

import sys, os
from twisted.trial import unittest

from twisted.protocols import xmlstream

class AuthStandin(xmlstream.Authenticator):
    namespace = "testns"
    def __init__(self, testcase):
        xmlstream.Authenticator.__init__(self, "foob")
        self.testcase = testcase
        self.started = False
    
    def streamStarted(self, rootelem):
        self.started = True
        self.testcase.assertEquals(rootelem["id"], "12345")
        self.testcase.assertEquals(rootelem["from"], "testharness")

class XmlStreamTest(unittest.TestCase):
    # Stand-in method to make this object look like a transport
    def loseConnection(self):
        self.protocol.connectionLost("no reason")
    
    def streamErrorEvent(self, errelem):
        self.errorOccurred = True
        self.assertEquals(errelem["id"], "123")

    def streamEndEvent(self, _):
        self.streamEnded = True
        
    def testBasicOp(self):
        # Setup
        self.errorOccurred = False
        self.streamEnded = False
        outlist = []
        as = AuthStandin(self)
        xs = xmlstream.XmlStream(as)

        # Crazy mixup here to get all the transport/protocol emulation
        # setup
        self.protocol = xs
        xs.transport = self
        
        # Override send method, so we can examine output
        xs.send = outlist.append
        xs.addObserver(xmlstream.STREAM_ERROR_EVENT,
                       self.streamErrorEvent)
        xs.addObserver(xmlstream.STREAM_END_EVENT,
                       self.streamEndEvent)

        # Go...
        xs.connectionMade()
        self.assertEquals(outlist[0], "<stream:stream xmlns='testns' xmlns:stream='http://etherx.jabber.org/streams' to='foob'>")
        
        xs.dataReceived("<stream:stream xmlns='testns' xmlns:stream='http://etherx.jabber.org/streams' from='testharness' id='12345'>")
        self.assertEquals(as.started, True)

        self.assertEquals(self.errorOccurred, False)
        self.assertEquals(self.streamEnded, False)
        xs.dataReceived("<stream:error id='123'/>")
        self.assertEquals(self.errorOccurred, True)
        self.assertEquals(self.streamEnded, True)
