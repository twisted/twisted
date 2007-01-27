import sys, os

from twisted.trial import unittest
from twisted.internet import reactor, interfaces
from twisted.python import util
from twisted.web import static, twcgi, server, resource
from twisted.web import client

DUMMY_CGI = '''\
print "Header: OK"
print
print "cgi output"
'''

READINPUT_CGI = '''\
# this is an example of a correctly-written CGI script which reads a body
# from stdin, which only reads env['CONTENT_LENGTH'] bytes.

import os, sys

body_length = int(os.environ.get('CONTENT_LENGTH',0))
indata = sys.stdin.read(body_length)
print "Header: OK"
print
print "readinput ok"
'''

READALLINPUT_CGI = '''\
# this is an example of the typical (incorrect) CGI script which expects
# the server to close stdin when the body of the request is complete.
# A correct CGI should only read env['CONTENT_LENGTH'] bytes.

import sys

indata = sys.stdin.read()
print "Header: OK"
print
print "readallinput ok"
'''

class PythonScript(twcgi.FilteredScript):
    filter = sys.executable
    filters = sys.executable,  # web2's version

class CGI(unittest.TestCase):
    def startServer(self, cgi):
        root = resource.Resource()
        cgipath = util.sibpath(__file__, cgi)
        root.putChild("cgi", PythonScript(cgipath))
        site = server.Site(root)
        self.p = reactor.listenTCP(0, site)
        return self.p.getHost().port

    def tearDown(self):
        if self.p:
            return self.p.stopListening()


    def testCGI(self):
        cgiFilename = os.path.abspath(self.mktemp())
        cgiFile = file(cgiFilename, 'wt')
        cgiFile.write(DUMMY_CGI)
        cgiFile.close()

        portnum = self.startServer(cgiFilename)
        d = client.getPage("http://localhost:%d/cgi" % portnum)
        d.addCallback(self._testCGI_1)
        return d
    def _testCGI_1(self, res):
        self.failUnlessEqual(res, "cgi output" + os.linesep)


    def testReadEmptyInput(self):
        cgiFilename = os.path.abspath(self.mktemp())
        cgiFile = file(cgiFilename, 'wt')
        cgiFile.write(READINPUT_CGI)
        cgiFile.close()

        portnum = self.startServer(cgiFilename)
        d = client.getPage("http://localhost:%d/cgi" % portnum)
        d.addCallback(self._testReadEmptyInput_1)
        return d
    testReadEmptyInput.timeout = 5
    def _testReadEmptyInput_1(self, res):
        self.failUnlessEqual(res, "readinput ok%s" % os.linesep)

    def testReadInput(self):
        cgiFilename = os.path.abspath(self.mktemp())
        cgiFile = file(cgiFilename, 'wt')
        cgiFile.write(READINPUT_CGI)
        cgiFile.close()

        portnum = self.startServer(cgiFilename)
        d = client.getPage("http://localhost:%d/cgi" % portnum,
                           method="POST",
                           postdata="Here is your stdin")
        d.addCallback(self._testReadInput_1)
        return d
    testReadInput.timeout = 5
    def _testReadInput_1(self, res):
        self.failUnlessEqual(res, "readinput ok%s" % os.linesep)


    def testReadAllInput(self):
        cgiFilename = os.path.abspath(self.mktemp())
        cgiFile = file(cgiFilename, 'wt')
        cgiFile.write(READALLINPUT_CGI)
        cgiFile.close()

        portnum = self.startServer(cgiFilename)
        d = client.getPage("http://localhost:%d/cgi" % portnum,
                           method="POST",
                           postdata="Here is your stdin")
        d.addCallback(self._testReadAllInput_1)
        return d
    testReadAllInput.timeout = 5
    def _testReadAllInput_1(self, res):
        self.failUnlessEqual(res, "readallinput ok%s" % os.linesep)

if not interfaces.IReactorProcess.providedBy(reactor):
    CGI.skip = "CGI tests require a functional reactor.spawnProcess()"
