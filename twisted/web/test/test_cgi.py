# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.web.twcgi}.
"""

import sys, os

from twisted.trial import unittest
from twisted.internet import reactor, interfaces, error
from twisted.python import util, failure
from twisted.web.http import NOT_FOUND, INTERNAL_SERVER_ERROR
from twisted.web import client, twcgi, server, resource
from twisted.web.test._util import _render
from twisted.web.test.test_web import DummyRequest

DUMMY_CGI = '''\
print "Header: OK"
print
print "cgi output"
'''

DUAL_HEADER_CGI = '''\
print "Header: spam"
print "Header: eggs"
print
print "cgi output"
'''

SPECIAL_HEADER_CGI = '''\
print "Server: monkeys"
print "Date: last year"
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

NO_DUPLICATE_CONTENT_TYPE_HEADER_CGI = '''\
print "content-type: text/cgi-duplicate-test"
print
print "cgi output"
'''

class PythonScript(twcgi.FilteredScript):
    filter = sys.executable
    filters = sys.executable,  # web2's version

class CGI(unittest.TestCase):
    """
    Tests for L{twcgi.FilteredScript}.
    """

    if not interfaces.IReactorProcess.providedBy(reactor):
        skip = "CGI tests require a functional reactor.spawnProcess()"

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


    def writeCGI(self, source):
        cgiFilename = os.path.abspath(self.mktemp())
        cgiFile = file(cgiFilename, 'wt')
        cgiFile.write(source)
        cgiFile.close()
        return cgiFilename


    def testCGI(self):
        cgiFilename = self.writeCGI(DUMMY_CGI)

        portnum = self.startServer(cgiFilename)
        d = client.getPage("http://localhost:%d/cgi" % portnum)
        d.addCallback(self._testCGI_1)
        return d


    def _testCGI_1(self, res):
        self.failUnlessEqual(res, "cgi output" + os.linesep)


    def test_protectedServerAndDate(self):
        """
        If the CGI script emits a I{Server} or I{Date} header, these are
        ignored.
        """
        cgiFilename = self.writeCGI(SPECIAL_HEADER_CGI)

        portnum = self.startServer(cgiFilename)
        url = "http://localhost:%d/cgi" % (portnum,)
        factory = client.HTTPClientFactory(url)
        reactor.connectTCP('localhost', portnum, factory)
        def checkResponse(ignored):
            self.assertNotIn('monkeys', factory.response_headers['server'])
            self.assertNotIn('last year', factory.response_headers['date'])
        factory.deferred.addCallback(checkResponse)
        return factory.deferred


    def test_noDuplicateContentTypeHeaders(self):
        """
        If the CGI script emits a I{content-type} header, make sure that the
        server doesn't add an additional (duplicate) one, as per ticket 4786.
        """
        cgiFilename = self.writeCGI(NO_DUPLICATE_CONTENT_TYPE_HEADER_CGI)

        portnum = self.startServer(cgiFilename)
        url = "http://localhost:%d/cgi" % (portnum,)
        factory = client.HTTPClientFactory(url)
        reactor.connectTCP('localhost', portnum, factory)
        def checkResponse(ignored):
            self.assertEquals(
                factory.response_headers['content-type'], ['text/cgi-duplicate-test'])
        factory.deferred.addCallback(checkResponse)
        return factory.deferred


    def test_duplicateHeaderCGI(self):
        """
        If a CGI script emits two instances of the same header, both are sent in
        the response.
        """
        cgiFilename = self.writeCGI(DUAL_HEADER_CGI)

        portnum = self.startServer(cgiFilename)
        url = "http://localhost:%d/cgi" % (portnum,)
        factory = client.HTTPClientFactory(url)
        reactor.connectTCP('localhost', portnum, factory)
        def checkResponse(ignored):
            self.assertEquals(
                factory.response_headers['header'], ['spam', 'eggs'])
        factory.deferred.addCallback(checkResponse)
        return factory.deferred


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



class CGIDirectoryTests(unittest.TestCase):
    """
    Tests for L{twcgi.CGIDirectory}.
    """
    def test_render(self):
        """
        L{twcgi.CGIDirectory.render} sets the HTTP response code to I{NOT
        FOUND}.
        """
        resource = twcgi.CGIDirectory(self.mktemp())
        request = DummyRequest([''])
        d = _render(resource, request)
        def cbRendered(ignored):
            self.assertEqual(request.responseCode, NOT_FOUND)
        d.addCallback(cbRendered)
        return d


    def test_notFoundChild(self):
        """
        L{twcgi.CGIDirectory.getChild} returns a resource which renders an
        response with the HTTP I{NOT FOUND} status code if the indicated child
        does not exist as an entry in the directory used to initialized the
        L{twcgi.CGIDirectory}.
        """
        path = self.mktemp()
        os.makedirs(path)
        resource = twcgi.CGIDirectory(path)
        request = DummyRequest(['foo'])
        child = resource.getChild("foo", request)
        d = _render(child, request)
        def cbRendered(ignored):
            self.assertEqual(request.responseCode, NOT_FOUND)
        d.addCallback(cbRendered)
        return d



class CGIProcessProtocolTests(unittest.TestCase):
    """
    Tests for L{twcgi.CGIProcessProtocol}.
    """
    def test_prematureEndOfHeaders(self):
        """
        If the process communicating with L{CGIProcessProtocol} ends before
        finishing writing out headers, the response has I{INTERNAL SERVER
        ERROR} as its status code.
        """
        request = DummyRequest([''])
        protocol = twcgi.CGIProcessProtocol(request)
        protocol.processEnded(failure.Failure(error.ProcessTerminated()))
        self.assertEqual(request.responseCode, INTERNAL_SERVER_ERROR)



class CGIDeprecationTests(unittest.TestCase):
    """
    Tests for deprecations in L{twisted.web.twcgi}.
    """

    def test_PHP3ScriptIsDeprecated(self):
        """
        L{twcgi.PHP3Script} is deprecated.
        """
        twcgi.PHP3Script

        warnings = self.flushWarnings([self.test_PHP3ScriptIsDeprecated])
        self.assertEquals(len(warnings), 1)
        self.assertEquals(warnings[0]['category'], DeprecationWarning)
        self.assertIn("PHP3Script is deprecated. "
                      "Use twisted.web.twcgi.FilteredScript instead.",
                      warnings[0]['message'])


    def test_PHPScriptIsDeprecated(self):
        """
        L{twcgi.PHPScript} is deprecated.
        """
        twcgi.PHPScript

        warnings = self.flushWarnings([self.test_PHPScriptIsDeprecated])
        self.assertEquals(len(warnings), 1)
        self.assertEquals(warnings[0]['category'], DeprecationWarning)
        self.assertIn("PHPScript is deprecated. "
                      "Use twisted.web.twcgi.FilteredScript instead.",
                      warnings[0]['message'])
