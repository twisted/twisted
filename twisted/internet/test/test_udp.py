# Copyright (c) 2010 Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for implementations of L{IReactorUDP}.
"""

__metaclass__ = type

from zope.interface.verify import verifyObject

from twisted.internet.test.reactormixins import ReactorBuilder
from twisted.internet.interfaces import IListeningPort
from twisted.internet.protocol import DatagramProtocol
from twisted.internet.defer import maybeDeferred
from twisted.internet.udp import Port
from twisted.python import log


class UDPServerTestsBuilder(ReactorBuilder):
    """
    Builder defining tests relating to L{IReactorUDP.listenUDP}.
    """
    def test_interface(self):
        """
        L{IReactorUDP.listenUDP} returns an object providing L{IListeningPort}.
        """
        reactor = self.buildReactor()
        port = reactor.listenUDP(0, DatagramProtocol())
        self.assertTrue(verifyObject(IListeningPort, port))
    
    def getListeningPort(self, reactor):
        """
        Get a TCP port from a reactor
        """
        return reactor.listenUDP(0, DatagramProtocol())
    
    def getExpectedConnectionPortNumber(self, port):
        """
        Get the expected port number for the TCP port that experienced
        the connection event.
        """
        return port.getHost().port
    
    def test_connectionListeningLogMsg(self):
        """
        When a connection is made, an informative log dict should be logged
        (see L{getExpectedConnectionLostLogMsg}) containing: the event source,
        event type, protocol, and port number.
        """

        loggedDicts = []
        def logConnectionListeningMsg(eventDict):
            loggedDicts.append(eventDict)
        
        log.addObserver(logConnectionListeningMsg)
        reactor = self.buildReactor()
        p = self.getListeningPort(reactor)
        listenPort = self.getExpectedConnectionPortNumber(p)

        def stopReactor(*ignored):
            log.removeObserver(logConnectionListeningMsg)
            reactor.stop()

        reactor.callWhenRunning(stopReactor)
        reactor.run()
        
        dictHits = 0
        for eventDict in loggedDicts:
            if eventDict.has_key("portNumber") and \
               eventDict.has_key("eventSource") and \
               eventDict.has_key("protocol") and \
               eventDict.has_key("eventType") and \
               eventDict["portNumber"] == listenPort and \
               eventDict["eventType"] == "start" and \
               isinstance(eventDict["eventSource"], Port) and \
               isinstance(eventDict["protocol"], DatagramProtocol):
                dictHits = dictHits + 1
        
        self.assertTrue(dictHits > 0)

    def test_connectionLostLogMsg(self):
        """
        When a connection is made, an informative log dict should be logged
        (see L{getExpectedConnectionLostLogMsg}) containing: the event source,
        event type, protocol, and port number.
        """

        loggedDicts = []
        def logConnectionListeningMsg(eventDict):
            loggedDicts.append(eventDict)
        
        log.addObserver(logConnectionListeningMsg)
        reactor = self.buildReactor()
        p = self.getListeningPort(reactor)
        listenPort = self.getExpectedConnectionPortNumber(p)

        def stopReactor(*ignored):
            p.connectionLost()
            log.removeObserver(logConnectionListeningMsg)
            reactor.stop()

        reactor.callWhenRunning(stopReactor)
        reactor.run()
        
        dictHits = 0
        for eventDict in loggedDicts:
            if eventDict.has_key("portNumber") and \
               eventDict.has_key("eventSource") and \
               eventDict.has_key("protocol") and \
               eventDict.has_key("eventType") and \
               eventDict["portNumber"] == listenPort and \
               eventDict["eventType"] == "stop" and \
               isinstance(eventDict["eventSource"], Port) and \
               isinstance(eventDict["protocol"], DatagramProtocol):
                dictHits = dictHits + 1
        
        self.assertTrue(dictHits > 0)

globals().update(UDPServerTestsBuilder.makeTestCaseClasses())
