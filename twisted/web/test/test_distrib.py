#! /usr/bin/python

import sys

from twisted.trial import unittest, util
from twisted.web import http, distrib, client, resource, static, server
from twisted.internet import reactor, base
from twisted.spread import pb
from twisted.python import log, util as tputil

class MySite(server.Site):
    def stopFactory(self):
        if hasattr(self, "logFile"):
            if self.logFile != log.logfile:
                self.logFile.close()
            del self.logFile

class DistribTest(unittest.TestCase):
    port1 = None
    port2 = None

    def setUp(self):
        base.DelayedCall.debug = True

    def tearDown(self):
        http._logDateTimeStop()
        if self.port1 is not None:
            d = self.port1.stopListening()
            unittest.wait(d)
        if self.port2 is not None:
            d = self.port2.stopListening()
            unittest.wait(d)

    def testDistrib(self):
        # site1 is the publisher
        r1 = resource.Resource()
        r1.putChild("there", static.Data("root", "text/plain"))
        site1 = server.Site(r1)
        f1 = pb.PBServerFactory(distrib.ResourcePublisher(site1))
        self.port1 = reactor.listenTCP(0, f1)

        util.spinUntil(lambda :self.port1.connected)

        # site2 is the subscriber
        sub = distrib.ResourceSubscription("127.0.0.1",
                                           self.port1.getHost().port)
        r2 = resource.Resource()
        r2.putChild("here", sub)
        f2 = MySite(r2)
        self.port2 = reactor.listenTCP(0, f2)

        util.spinUntil(lambda :self.port2.connected)

        # then we hit site2 with a client
        d = client.getPage("http://127.0.0.1:%d/here/there" % \
                           self.port2.getHost().port)
        res = util.wait(d, timeout=1.0)
        self.failUnlessEqual(res, "root")

        # A bit of a hack: force the pb client to disconnect, for cleanup
        # purposes.
        sub.publisher.broker.transport.loseConnection()

