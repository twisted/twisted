#! /usr/bin/python

import sys, os

from twisted.trial import unittest
from twisted.internet import reactor, interfaces
from twisted.python import util
from twisted.web2 import static, twcgi, server, resource, channel, http, iweb

try:
    from twisted.web import client
except ImportError:
    # No twisted.web installed, and no web2 client yet.
    client = None

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
    p = None
    def startServer(self, cgi):
        root = resource.Resource()
        cgipath = util.sibpath(__file__, cgi)
        root.putChild("cgi", PythonScript(cgipath))
        site = server.Site(root)
        self.p = reactor.listenTCP(0, channel.HTTPFactory(site))
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
        self.failUnlessEqual(res, "cgi output%s" % os.linesep)


    def testReadEmptyInput(self):
        cgiFilename = os.path.abspath(self.mktemp())
        cgiFile = file(cgiFilename, 'wt')
        cgiFile.write(READINPUT_CGI)
        cgiFile.close()

        portnum = self.startServer(cgiFilename)
        d = client.getPage("http://localhost:%d/cgi" % portnum)
        d.addCallback(self._testReadEmptyInput_1)
        return d

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

    def _testReadInput_1(self, res):
        self.failUnlessEqual(res, "readinput ok%s" % os.linesep)


    def testRealAllInput(self):
        cgiFilename = os.path.abspath(self.mktemp())
        cgiFile = file(cgiFilename, 'wt')
        cgiFile.write(READALLINPUT_CGI)
        cgiFile.close()

        portnum = self.startServer(cgiFilename)
        d = client.getPage("http://localhost:%d/cgi" % portnum,
                           method="POST",
                           postdata="Here is your stdin")
        d.addCallback(self._testRealAllInput_1)
        return d

    def _testRealAllInput_1(self, res):
        self.failUnlessEqual(res, "readallinput ok%s" % os.linesep)

if not interfaces.IReactorProcess.providedBy(reactor):
    CGI.skip = "CGI tests require a functional reactor.spawnProcess()"

if not client:
    CGI.skip = "CGI tests require a twisted.web at the moment."

class CGIDirectoryTest(unittest.TestCase):
    def setUp(self):
        temp = self.mktemp()
        os.mkdir(temp)

        cgiFile = open(os.path.join(temp, 'dummy'), 'wt')
        cgiFile.write(DUMMY_CGI)
        cgiFile.close()

        os.mkdir(os.path.join(temp, 'directory'))
        
        self.root = twcgi.CGIDirectory(temp)

    def testNotFound(self):
        
        self.assertRaises(http.HTTPError,
                          self.root.locateChild, None, ('notHere',))

    def testCantRender(self):
        response = self.root.render(None)

        self.failUnless(iweb.IResponse.providedBy(response))
        self.assertEquals(response.code, 403)

    def testFoundScript(self):
        resource, segments = self.root.locateChild(None, ('dummy',))

        self.assertEquals(segments, ())

        self.failUnless(isinstance(resource, (twcgi.CGIScript,)))

    def testSubDirectory(self):
        resource, segments = self.root.locateChild(None, ('directory',
                                                          'paths',
                                                          'that',
                                                          'dont',
                                                          'matter'))

        self.failUnless(isinstance(resource, twcgi.CGIDirectory))

    def createScript(self, filename):
        cgiFile = open(filename, 'wt')
        cgiFile.write("#!%s\n\n%s" % (sys.executable,
                                      DUMMY_CGI))
        cgiFile.close()
        os.chmod(filename, 0700)

    def testScriptsExecute(self):
        cgiBinDir = os.path.abspath(self.mktemp())
        os.mkdir(cgiBinDir)
        root = twcgi.CGIDirectory(cgiBinDir)

        self.createScript(os.path.join(cgiBinDir, 'dummy'))

        cgiSubDir = os.path.join(cgiBinDir, 'sub')
        os.mkdir(cgiSubDir)

        self.createScript(os.path.join(cgiSubDir, 'dummy'))

        self.p = reactor.listenTCP(0, channel.HTTPFactory(server.Site(root)))
        portnum = self.p.getHost().port

        def _firstResponse(res):
            self.failUnlessEqual(res, "cgi output%s" % os.linesep)
            
            return client.getPage('http://localhost:%d/sub/dummy' % portnum)

        def _secondResponse(res):
            self.failUnlessEqual(res, "cgi output%s" % os.linesep)

        def _cleanup(res):
            d = self.p.stopListening()
            d.addCallback(lambda ign: res)
            return d

        d = client.getPage('http://localhost:%d/dummy' % portnum)

        d.addCallback(_firstResponse
        ).addCallback(_secondResponse
        ).addBoth(_cleanup)

        return d
