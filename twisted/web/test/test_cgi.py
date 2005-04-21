#! /usr/bin/python

import sys, os

from twisted.trial import unittest
from twisted.internet import reactor, interfaces
from twisted.python import util
from twisted.web import static, twcgi, server, resource, client

DUMMY_CGI = '''\
print "Header: OK"
print
print "cgi output"
'''

READINPUT_CGI = '''\
# this is an example of the typical (incorrect) CGI script which expects
# the server to close stdin when the body of the request is complete.
# A correct CGI should only read env['CONTENT_LENGTH'] bytes.

import sys

indata = sys.stdin.read()
print "Header: OK"
print
print "readinput ok"
'''

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
        cgiFilename = os.path.abspath(self.mktemp())
        cgiFile = file(cgiFilename, 'wt')
        cgiFile.write('#!' + sys.executable + '\n')
        cgiFile.write(DUMMY_CGI)
        cgiFile.close()
        
        os.chmod(cgiFilename, 0550)

        portnum = self.startServer(cgiFilename)
        d = client.getPage("http://localhost:%d/cgi" % portnum)
        d.addCallback(self._testCGI_1)
        return d
    def _testCGI_1(self, res):
        self.failUnlessEqual(res, "cgi output\n")

    def testReadInput(self):
        cgiFilename = os.path.abspath(self.mktemp())
        cgiFile = file(cgiFilename, 'wt')
        cgiFile.write('#!' + sys.executable + '\n')
        cgiFile.write(READINPUT_CGI)
        cgiFile.close()

        os.chmod(cgiFilename, 0550)

        portnum = self.startServer(cgiFilename)
        d = client.getPage("http://localhost:%d/cgi" % portnum)
        d.addCallback(self._testReadInput_1)
        return d
    testReadInput.timeout = 5
    def _testReadInput_1(self, res):
        self.failUnlessEqual(res, "readinput ok\n")

if not interfaces.IReactorProcess.providedBy(reactor):
    CGI.skip = "CGI tests require a functional reactor.spawnProcess()"
