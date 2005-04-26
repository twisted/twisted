#
# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.


import sys, os
from twisted.trial import unittest

from twisted.xish import xmlstream
from twisted.xish import utility

class AuthStandin(xmlstream.ConnectAuthenticator):
    namespace = "testns"
    def __init__(self, testcase):
        xmlstream.Authenticator.__init__(self, "foob")
        self.testcase = testcase
    
    def streamStarted(self, rootelem):
        self.testcase.streamStarted = True
        self.testcase.assertEquals(rootelem["id"], "12345")
        self.testcase.assertEquals(rootelem["from"], "testharness")

class XmlStreamTest(unittest.TestCase):
    def setUp(self):
        self.errorOccurred = False
        self.streamStarted = False
        self.streamEnded = False
        self.outlist = []
        self.xmlstream = xmlstream.XmlStream(AuthStandin(self))
        self.xmlstream.transport = self
        self.xmlstream.transport.write = self.outlist.append

    # Auxilary methods 
    def loseConnection(self):
        self.xmlstream.connectionLost("no reason")
    
    def streamErrorEvent(self, errelem):
        self.errorOccurred = True
        self.assertEquals(errelem["id"], "123")

    def streamEndEvent(self, _):
        self.streamEnded = True
        
    def testBasicOp(self):
        xs = self.xmlstream
        xs.addObserver(xmlstream.STREAM_ERROR_EVENT,
                       self.streamErrorEvent)
        xs.addObserver(xmlstream.STREAM_END_EVENT,
                       self.streamEndEvent)

        # Go...
        xs.connectionMade()
        self.assertEquals(self.outlist[0], "<stream:stream xmlns='testns' xmlns:stream='http://etherx.jabber.org/streams' to='foob'>")
        
        xs.dataReceived("<stream:stream xmlns='testns' xmlns:stream='http://etherx.jabber.org/streams' from='testharness' id='12345'>")
        self.assertEquals(self.streamStarted, True)

        self.assertEquals(self.errorOccurred, False)
        self.assertEquals(self.streamEnded, False)
        xs.dataReceived("<stream:error id='123'/>")
        self.assertEquals(self.errorOccurred, True)
        self.assertEquals(self.streamEnded, True)


        
        
        
        
