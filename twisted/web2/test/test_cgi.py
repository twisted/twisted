import sys, os

from twisted.trial import unittest
from twisted.internet import reactor, interfaces, defer
from twisted.python import util
from twisted.python.runtime import platform
from twisted.web2 import twcgi, server, http, iweb
from twisted.web2 import stream
from twisted.web2.test.test_server import SimpleRequest

skipWindowsNopywin32 = None
if platform.isWindows():
    try:
        import win32process
    except ImportError:
        skipWindowsNopywin32 = ("On windows, spawnProcess is not available "
                                "in the absence of win32process.")

DUMMY_CGI = '''
print "Header: OK"
print
print "cgi output"
'''

READINPUT_CGI = '''
# this is an example of a correctly-written CGI script which reads a body
# from stdin, which only reads env['CONTENT_LENGTH'] bytes.

import os, sys

body_length = int(os.environ.get('CONTENT_LENGTH',0))
indata = sys.stdin.read(body_length)
print "Header: OK"
print
print "readinput ok"
'''

READALLINPUT_CGI = '''
# this is an example of the typical (incorrect) CGI script which expects
# the server to close stdin when the body of the request is complete.
# A correct CGI should only read env['CONTENT_LENGTH'] bytes.

import sys

indata = sys.stdin.read()
print "Header: OK"
print
print "readallinput ok"
'''

def readStreamToString(s):
    """
    Read all data from a stream into a string.

    @param s: a L{twisted.web2.stream.IByteStream} to read from.
    @return: a L{Deferred} results in a str
    """
    allData = []

    def gotData(data):
        allData.append(data)

    d = stream.readStream(s, gotData)
    d.addCallback(lambda ign: ''.join(allData))

    return d


class PythonScript(twcgi.FilteredScript):
    """
    A specialized FilteredScript that just runs its file in a python
    interpreter.
    """

    filters = (sys.executable,)  # web2's version


class CGITestBase(unittest.TestCase):
    """
    Base class for CGI using tests
    """
    def setUpResource(self, cgi):
        """
        Set up the cgi resource to be tested.

        @param cgi: A string containing a Python CGI script.
        @return: A L{PythonScript} instance
        """

        cgiFilename = os.path.abspath(self.mktemp())
        cgiFile = file(cgiFilename, 'wt')
        cgiFile.write(cgi)
        cgiFile.close()

        return PythonScript(cgiFilename)

    def getPage(self, request, resource):
        """
        Return the body of the given resource for the given request

        @param request: A L{SimpleRequest} instance to act on the resource
        @param resource: A L{IResource} to be rendered
        @return: A L{Deferred} that fires with the response body returned by
            resource for the request
        """

        d = defer.maybeDeferred(resource.renderHTTP, request)
        d.addCallback(lambda resp: readStreamToString(resp.stream))
        return d


class CGI(CGITestBase):
    """
    Test cases for basic twcgi.FilteredScript functionality
    """

    def test_CGI(self):
        """
        Test that the given DUMMY_CGI is executed and the expected output
        returned
        """

        request = SimpleRequest(None, 'GET', '/cgi')

        resource = self.setUpResource(DUMMY_CGI)

        d = self.getPage(request, resource)
        d.addCallback(self._testCGI_1)
        return d

    def _testCGI_1(self, res):
        self.failUnlessEqual(res, "cgi output%s" % os.linesep)

    def testReadEmptyInput(self):
        """
        Test that the CGI can successfully read from an empty input stream
        """

        request = SimpleRequest(None, 'GET', '/cgi')

        resource = self.setUpResource(READINPUT_CGI)

        d = self.getPage(request, resource)
        d.addCallback(self._testReadEmptyInput_1)
        return d

    def _testReadEmptyInput_1(self, res):
        self.failUnlessEqual(res, "readinput ok%s" % os.linesep)

    def test_readInput(self):
        """
        Test that we can successfully read an input stream with data
        """
        request = SimpleRequest(None, "POST", "/cgi",
                                content="Here is your stdin")

        resource = self.setUpResource(READINPUT_CGI)
        d = self.getPage(request, resource)
        d.addCallback(self._testReadInput_1)
        return d

    def _testReadInput_1(self, res):
        self.failUnlessEqual(res, "readinput ok%s" % os.linesep)

    def test_readAllInput(self):
        """
        Test that we can all input can be read regardless of CONTENT_LENGTH
        """

        request = SimpleRequest(None, "POST", "/cgi",
                                content="Here is your stdin")

        resource = self.setUpResource(READALLINPUT_CGI)

        d = self.getPage(request, resource)

        d.addCallback(self._testReadAllInput_1)
        return d

    def _testReadAllInput_1(self, res):
        self.failUnlessEqual(res, "readallinput ok%s" % os.linesep)


if not interfaces.IReactorProcess.providedBy(reactor):
    CGI.skip = "CGI tests require a functional reactor.spawnProcess()"


class CGIDirectoryTest(CGITestBase):
    """
    Test cases for twisted.web2.twcgi.CGIDirectory
    """

    def setUp(self):
        temp = self.mktemp()
        os.mkdir(temp)

        cgiFile = open(os.path.join(temp, 'dummy'), 'wt')
        cgiFile.write(DUMMY_CGI)
        cgiFile.close()

        os.mkdir(os.path.join(temp, 'directory'))

        self.root = twcgi.CGIDirectory(temp)

    def test_notFound(self):
        """
        Correctly handle non-existant children by returning a 404
        """
        self.assertRaises(http.HTTPError,
                          self.root.locateChild, None, ('notHere',))

    def test_cantRender(self):
        """
        We do not support directory listing of CGIDirectories
        So our render method should always return a 403
        """

        response = self.root.render(None)

        self.failUnless(iweb.IResponse.providedBy(response))
        self.assertEquals(response.code, 403)

    def test_foundScript(self):
        """
        We should get twcgi.CGISCript instances when we locate
        a CGI
        """

        resource, segments = self.root.locateChild(None, ('dummy',))

        self.assertEquals(segments, ())

        self.failUnless(isinstance(resource, (twcgi.CGIScript,)))

    def test_subDirectory(self):
        """
        When a subdirectory is request we should get another CGIDirectory
        """

        resource, segments = self.root.locateChild(None, ('directory',
                                                          'paths',
                                                          'that',
                                                          'dont',
                                                          'matter'))

        self.failUnless(isinstance(resource, twcgi.CGIDirectory))

    def createScript(self, filename):
        """
        Write a dummy cgi script
        @param filename: a str destination for the cgi
        """

        cgiFile = open(filename, 'wt')
        cgiFile.write("#!%s\n\n%s" % (sys.executable,
                                      DUMMY_CGI))
        cgiFile.close()
        os.chmod(filename, 0700)

    def test_scriptsExecute(self):
        """
        Verify that CGI scripts within a CGIDirectory can actually be executed
        """

        cgiBinDir = os.path.abspath(self.mktemp())
        os.mkdir(cgiBinDir)

        root = twcgi.CGIDirectory(cgiBinDir)

        self.createScript(os.path.join(cgiBinDir, 'dummy'))

        cgiSubDir = os.path.join(cgiBinDir, 'sub')
        os.mkdir(cgiSubDir)

        self.createScript(os.path.join(cgiSubDir, 'dummy'))

        site = server.Site(root)

        request = SimpleRequest(site, "GET", "/dummy")

        d = request.locateResource('/dummy')

        def _firstResponse(res):
            self.failUnlessEqual(res, "cgi output%s" % os.linesep)

        def _firstRequest(resource):
            d1 = self.getPage(request, resource)
            d1.addCallback(_firstResponse)

            return d1

        d.addCallback(_firstRequest)

        def _secondResponse(res):
            self.failUnlessEqual(res, "cgi output%s" % os.linesep)

        def _secondRequest(ign):
            request = SimpleRequest(site, "GET", '/sub/dummy')

            d2 = request.locateResource('/sub/dummy')

            d2.addCallback(lambda resource: self.getPage(request, resource))
            d2.addCallback(_secondResponse)

            return d2

        d.addCallback(_secondRequest)

        return d
    test_scriptsExecute.skip = skipWindowsNopywin32
