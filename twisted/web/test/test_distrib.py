#! /usr/bin/python

from twisted.trial import unittest
from twisted.web import http, distrib, client, resource, static, server
from twisted.internet import reactor
from twisted.spread import pb
from twisted.python import log

class DistribTest(unittest.TestCase):
    port1 = None
    port2 = None

    def tearDown(self):
        if self.port1 is not None:
            d = self.port1.stopListening()
            d.addErrback(log.err)
            unittest.deferredResult(d)
        if self.port2 is not None:
            d = self.port2.stopListening()
            d.addErrback(log.err)
            unittest.deferredResult(d)
        http._logDateTimeStop()

    def testDistrib(self):
        # site1 is the publisher
        r1 = resource.Resource()
        r1.putChild("there", static.Data("root", "text/plain"))
        site1 = server.Site(r1)
        f1 = pb.PBServerFactory(distrib.ResourcePublisher(site1))
        self.port1 = reactor.listenTCP(0, f1)

        # site2 is the subscriber
        sub = distrib.ResourceSubscription("127.0.0.1",
                                           self.port1.getHost().port)
        r2 = resource.Resource()
        r2.putChild("here", sub)
        f2 = server.Site(r2)
        self.port2 = reactor.listenTCP(0, f2)

        # then we hit site2 with a client
        d = client.getPage("http://127.0.0.1:%d/here/there" % \
                           self.port2.getHost().port)
        res = unittest.deferredResult(d)
        self.failUnlessEqual(res, "root")
