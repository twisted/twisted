# -*- test-case-name: twisted.web2.test.test_cgi -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.


"""
I hold resource classes and helper classes that deal with CGI scripts.

Things which are still not working properly:

  - CGIScript.render doesn't set REMOTE_ADDR or REMOTE_HOST in the
    environment

"""

# System Imports
import os
import sys
import urllib

# Twisted Imports
from twisted.internet import defer, protocol, reactor
from twisted.python import log, filepath

# Sibling Imports
from twisted.web2 import http
from twisted.web2 import resource
from twisted.web2 import responsecode
from twisted.web2 import server
from twisted.web2 import stream


headerNameTranslation = ''.join([c.isalnum() and c.upper() or '_' for c in map(chr, range(256))])

def createCGIEnvironment(request):
    # See http://hoohoo.ncsa.uiuc.edu/cgi/env.html for CGI interface spec
    # http://cgi-spec.golux.com/draft-coar-cgi-v11-03-clean.html for a better one
    remotehost = request.remoteAddr

    python_path = os.pathsep.join(sys.path)

    env = dict(os.environ)
    # MUST provide:
    if request.stream.length:
        env["CONTENT_LENGTH"] = str(request.stream.length)

    ctype = request.headers.getRawHeaders('content-type')
    if ctype:
        env["CONTENT_TYPE"] = ctype[0]

    env["GATEWAY_INTERFACE"] = "CGI/1.1"

    if request.postpath:
        # Should we raise an exception if this contains "/" chars?
        env["PATH_INFO"] = '/' + '/'.join(request.postpath)
    # MUST always be present, even if no query
    env["QUERY_STRING"] = request.querystring

    env["REMOTE_ADDR"] = remotehost.host
    env["REQUEST_METHOD"] = request.method
    # Should we raise an exception if this contains "/" chars?
    if request.prepath:
        env["SCRIPT_NAME"] = '/' + '/'.join(request.prepath)
    else:
        env["SCRIPT_NAME"] = ''

    env["SERVER_NAME"] = request.host
    env["SERVER_PORT"] = str(request.port)

    env["SERVER_PROTOCOL"] = "HTTP/%i.%i" % request.clientproto
    env["SERVER_SOFTWARE"] = server.VERSION

    # SHOULD provide
    # env["AUTH_TYPE"] # FIXME: add this
    # env["REMOTE_HOST"] # possibly dns resolve?

    # MAY provide
    # env["PATH_TRANSLATED"] # Completely worthless
    # env["REMOTE_IDENT"] # Completely worthless
    # env["REMOTE_USER"] # FIXME: add this

    # Unofficial, but useful and expected by applications nonetheless
    env["REMOTE_PORT"] = str(remotehost.port)
    env["REQUEST_SCHEME"] = request.scheme
    env["REQUEST_URI"] = request.uri
    env["HTTPS"] = ("off", "on")[request.scheme=="https"]
    env["SERVER_PORT_SECURE"] = ("0", "1")[request.scheme=="https"]

    # Propagate HTTP headers
    for title, header in request.headers.getAllRawHeaders():
        envname = title.translate(headerNameTranslation)
        # Don't send headers we already sent otherwise, and don't
        # send authorization headers, because that's a security
        # issue.
        if title not in ('content-type', 'content-length',
                         'authorization', 'proxy-authorization'):
            envname = "HTTP_" + envname
        env[envname] = ','.join(header)

    for k,v in env.items():
        if type(k) is not str:
            print "is not string:",k
        if type(v) is not str:
            print k, "is not string:",v
    return env

def runCGI(request, filename, filterscript=None):
    # Make sure that we don't have an unknown content-length
    if request.stream.length is None:
        return http.Response(responsecode.LENGTH_REQUIRED)
    env = createCGIEnvironment(request)
    env['SCRIPT_FILENAME'] = filename
    if '=' in request.querystring:
        qargs = []
    else:
        qargs = [urllib.unquote(x) for x in request.querystring.split('+')]

    if filterscript is None:
        filterscript = filename
        qargs = [filename] + qargs
    else:
        qargs = [filterscript, filename] + qargs
    d = defer.Deferred()
    proc = CGIProcessProtocol(request, d)
    reactor.spawnProcess(proc, filterscript, qargs, env, os.path.dirname(filename))
    return d

class CGIScript(resource.LeafResource):
    """I represent a CGI script.

    My implementation is complex due to the fact that it requires asynchronous
    IPC with an external process with an unpleasant protocol.
    """

    def __init__(self, filename):
        """Initialize, with the name of a CGI script file.
        """
        self.filename = filename
        resource.LeafResource.__init__(self)

    def render(self, request):
        """Do various things to conform to the CGI specification.

        I will set up the usual slew of environment variables, then spin off a
        process.
        """
        return runCGI(request, self.filename)

    def http_POST(self, request):
        return self.render(request)



class FilteredScript(CGIScript):
    """
    I am a special version of a CGI script, that uses a specific executable
    (or, the first existing executable in a list of executables).

    This is useful for interfacing with other scripting languages that adhere
    to the CGI standard (cf. PHPScript).  My 'filters' attribute specifies what
    executables to try to run, and my 'filename' init parameter describes which script
    to pass to the first argument of that script.
    """

    filters = '/usr/bin/cat',

    def __init__(self, filename, filters=None):
        if filters is not None:
            self.filters = filters
        CGIScript.__init__(self, filename)


    def render(self, request):
        for filterscript in self.filters:
            if os.path.exists(filterscript):
                return runCGI(request, self.filename, filterscript)
            else:
                log.err(self.__class__.__name__ + ' could not find any of: ' + ', '.join(self.filters))
                return http.Response(responsecode.INTERNAL_SERVER_ERROR)


class PHP3Script(FilteredScript):
    """I am a FilteredScript that uses the default PHP3 command on most systems.
    """

    filters = '/usr/bin/php3',


class PHPScript(FilteredScript):
    """I am a FilteredScript that uses the PHP command on most systems.
    Sometimes, php wants the path to itself as argv[0]. This is that time.
    """

    filters = '/usr/bin/php4-cgi', '/usr/bin/php4'


class CGIProcessProtocol(protocol.ProcessProtocol):
    handling_headers = 1
    headers_written = 0
    headertext = ''
    errortext = ''

    def resumeProducing(self):
        self.transport.resumeProducing()

    def pauseProducing(self):
        self.transport.pauseProducing()

    def stopProducing(self):
        self.transport.loseConnection()

    def __init__(self, request, deferred):
        self.request = request
        self.deferred = deferred
        self.stream = stream.ProducerStream()
        self.response = http.Response(stream=self.stream)

    def connectionMade(self):
        # Send input data over to the CGI script.
        def _failedProducing(reason):
            # If you really care.
            #log.err(reason)
            pass
        def _finishedProducing(result):
            self.transport.closeChildFD(0)
        s = stream.StreamProducer(self.request.stream)
        producingDeferred = s.beginProducing(self.transport)
        producingDeferred.addCallback(_finishedProducing)
        producingDeferred.addErrback(_failedProducing)

    def errReceived(self, error):
        self.errortext = self.errortext + error

    def outReceived(self, output):
        """
        Handle a chunk of input
        """
        # First, make sure that the headers from the script are sorted
        # out (we'll want to do some parsing on these later.)
        if self.handling_headers:
            fullText = self.headertext + output
            header_endings = []
            for delimiter in '\n\n','\r\n\r\n','\r\r', '\n\r\n':
                headerend = fullText.find(delimiter)
                if headerend != -1:
                    header_endings.append((headerend, delimiter))
            # Have we noticed the end of our headers in this chunk?
            if header_endings:
                header_endings.sort()
                headerend, delimiter = header_endings[0]
                # This is a final version of the header text.
                self.headertext = fullText[:headerend]
                linebreak = delimiter[:len(delimiter)/2]
                # Write all our headers to self.response
                for header in self.headertext.split(linebreak):
                    self._addResponseHeader(header)
                output = fullText[headerend+len(delimiter):]
                self.handling_headers = 0
                # Trigger our callback with a response
                self._sendResponse()
            # If we haven't hit the end of our headers yet, then
            # everything we've seen so far is _still_ headers
            if self.handling_headers:
                self.headertext = fullText
        # If we've stopped handling headers at this point, write
        # whatever output we've got.
        if not self.handling_headers:
            self.stream.write(output)

    def _addResponseHeader(self, header):
        """
        Save a header until we're ready to write our Response.
        """
        breakpoint = header.find(': ')
        if breakpoint == -1:
            log.msg('ignoring malformed CGI header: %s' % header)
        else:
            name = header.lower()[:breakpoint]
            text = header[breakpoint+2:]
            if name == 'status':
                try:
                     # "123 <description>" sometimes happens.
                    self.response.code = int(text.split(' ', 1)[0])
                except:
                    log.msg("malformed status header: %s" % header)
            else:
                self.response.headers.addRawHeader(name, text)

    def processEnded(self, reason):
        if reason.value.exitCode != 0:
            log.msg("CGI %s exited with exit code %s" %
                    (self.request.uri, reason.value.exitCode))
        if self.errortext:
            log.msg("Errors from CGI %s: %s" % (self.request.uri, self.errortext))
        if self.handling_headers:
            log.msg("Premature end of headers in %s: %s" % (self.request.uri, self.headertext))
            self.response = http.Response(responsecode.INTERNAL_SERVER_ERROR)
            self._sendResponse()
        self.stream.finish()

    def _sendResponse(self):
        """
        Call our deferred (from CGIScript.render) with a response.
        """
        # Fix up location stuff
        loc = self.response.headers.getHeader('location')
        if loc and self.response.code == responsecode.OK:
            if loc[0] == '/':
                # FIXME: Do internal redirect
                raise RuntimeError("Sorry, internal redirects not implemented yet.")
            else:
                # NOTE: if a script wants to output its own redirect body,
                # it must specify Status: 302 itself.
                self.response.code = 302
                self.response.stream = None

        self.deferred.callback(self.response)


class CGIDirectory(resource.Resource, filepath.FilePath):
    """A directory that serves only CGI scripts (to infinite depth)
    and does not support directory listings.

    @param pathname: A path to the directory that you wish to serve
                     CGI scripts from, for example /var/www/cgi-bin/
    @type pathname: str
    """

    addSlash = True

    def __init__(self, pathname):
        resource.Resource.__init__(self)
        filepath.FilePath.__init__(self, pathname)

    def locateChild(self, request, segments):
        fnp = self.child(segments[0])
        if not fnp.exists():
            raise http.HTTPError(responsecode.NOT_FOUND)
        elif fnp.isdir():
            return CGIDirectory(fnp.path), segments[1:]
        else:
            return CGIScript(fnp.path), segments[1:]
        return None, ()

    def render(self, request):
        errormsg = 'CGI directories do not support directory listing'
        return http.Response(responsecode.FORBIDDEN)


__all__ = ['createCGIEnvironment', 'CGIDirectory', 'CGIScript', 'FilteredScript', 'PHP3Script', 'PHPScript']
