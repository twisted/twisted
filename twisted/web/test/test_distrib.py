# Copyright (c) 2008 Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.web.distrib}.
"""

from twisted.trial import unittest
from twisted.web import http, distrib, client, resource, static, server
from twisted.internet import reactor, defer
from twisted.spread import pb
from twisted.python import log

class MySite(server.Site):
    def stopFactory(self):
        if hasattr(self, "logFile"):
            if self.logFile != log.logfile:
                self.logFile.close()
            del self.logFile


class PBServerFactory(pb.PBServerFactory):
    def buildProtocol(self, addr):
        self.proto = pb.PBServerFactory.buildProtocol(self, addr)
        return self.proto


class DistribTest(unittest.TestCase):
    port1 = None
    port2 = None
    sub = None

    def tearDown(self):
        dl = [defer.Deferred(), defer.Deferred()]
        self.f1.proto.notifyOnDisconnect(lambda: dl[0].callback(None))
        if self.sub is not None:
            self.sub.publisher.broker.notifyOnDisconnect(
                lambda: dl[1].callback(None))
            self.sub.publisher.broker.transport.loseConnection()
        http._logDateTimeStop()
        if self.port1 is not None:
            dl.append(self.port1.stopListening())
        if self.port2 is not None:
            dl.append(self.port2.stopListening())
        return defer.gatherResults(dl)

    def testDistrib(self):
        # site1 is the publisher
        r1 = resource.Resource()
        r1.putChild("there", static.Data("root", "text/plain"))
        site1 = server.Site(r1)
        self.f1 = PBServerFactory(distrib.ResourcePublisher(site1))
        self.port1 = reactor.listenTCP(0, self.f1)
        self.sub = distrib.ResourceSubscription("127.0.0.1",
                                                self.port1.getHost().port)
        r2 = resource.Resource()
        r2.putChild("here", self.sub)
        f2 = MySite(r2)
        self.port2 = reactor.listenTCP(0, f2)
        d = client.getPage("http://127.0.0.1:%d/here/there" % \
                           self.port2.getHost().port)
        d.addCallback(self.failUnlessEqual, 'root')
        return d

