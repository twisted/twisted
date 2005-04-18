#! /usr/bin/python

from twisted.trial import unittest
from twisted.internet import reactor, interfaces
from twisted.python import util
from twisted.web import static, twcgi, server, resource, client

class CGI(unittest.TestCase):
    def startServer(self, cgi):
        root = resource.Resource()
        cgipath = util.sibpath(__file__, cgi)
        root.putChild("cgi", twcgi.CGIScript(cgipath))
        site = server.Site(root)
        self.p = reactor.listenTCP(0, site)
        return self.p.getHost().port

    def tearDown(self):
        if self.p:
            return self.p.stopListening()

    def testCGI(self):
        portnum = self.startServer("cgi_dummy.py")
        d = client.getPage("http://localhost:%d/cgi" % portnum)
        d.addCallback(self._testCGI_1)
        return d
    def _testCGI_1(self, res):
        self.failUnlessEqual(res, "cgi output\n")

    def testReadInput(self):
        portnum = self.startServer("cgi_readinput.py")
        d = client.getPage("http://localhost:%d/cgi" % portnum)
        d.addCallback(self._testReadInput_1)
        return d
    testReadInput.timeout = 5
    def _testReadInput_1(self, res):
        self.failUnlessEqual(res, "readinput ok\n")

if not interfaces.IReactorProcess.providedBy(reactor):
    CGI.skip = "CGI tests require a functional reactor.spawnProcess()"
