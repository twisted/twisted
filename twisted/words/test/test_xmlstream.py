# Copyright (c) 2001-2005 Twisted Matrix Laboratories.
# See LICENSE for details.

from twisted.trial import unittest
from twisted.words.xish import xmlstream

class XmlStreamTest(unittest.TestCase):
    def setUp(self):
        self.errorOccurred = False
        self.streamStarted = False
        self.streamEnded = False
        self.outlist = []
        self.xmlstream = xmlstream.XmlStream()
        self.xmlstream.transport = self
        self.xmlstream.transport.write = self.outlist.append

    # Auxilary methods 
    def loseConnection(self):
        self.xmlstream.connectionLost("no reason")
    
    def streamStartEvent(self, rootelem):
        self.streamStarted = True

    def streamErrorEvent(self, errelem):
        self.errorOccurred = True

    def streamEndEvent(self, _):
        self.streamEnded = True
        
    def testBasicOp(self):
        xs = self.xmlstream
        xs.addObserver(xmlstream.STREAM_START_EVENT,
                       self.streamStartEvent)
        xs.addObserver(xmlstream.STREAM_ERROR_EVENT,
                       self.streamErrorEvent)
        xs.addObserver(xmlstream.STREAM_END_EVENT,
                       self.streamEndEvent)

        # Go...
        xs.connectionMade()
        xs.send("<root>")
        self.assertEquals(self.outlist[0], "<root>")
        
        xs.dataReceived("<root>")
        self.assertEquals(self.streamStarted, True)

        self.assertEquals(self.errorOccurred, False)
        self.assertEquals(self.streamEnded, False)
        xs.dataReceived("<child><unclosed></child>")
        self.assertEquals(self.errorOccurred, True)
        self.assertEquals(self.streamEnded, True)
