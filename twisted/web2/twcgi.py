##### FIXME: this file probably doesn't work.

# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.


"""I hold resource classes and helper classes that deal with CGI scripts.

Things which are still not working properly:

  - CGIScript.render doesn't set REMOTE_ADDR or REMOTE_HOST in the
    environment

"""

# System Imports
import string
import os
import sys
import urllib

# Twisted Imports
from twisted.internet import defer, protocol, reactor
from twisted.spread import pb
from twisted.python import log, filepath

# Sibling Imports
import error
import http
import iweb
import resource
import responsecode
import server
import static
import stream


def createCGIEnvironment(ctx, request=None):
    if request is None:
        request = iweb.IRequest(ctx)
    
    script_name = "/" + string.join(request.prepath, '/')
    python_path = string.join(sys.path, os.pathsep)
    server_name = request.getHost().split(':')[0]
    server_port = (request.getHost().split(':')+[''])[1]

    # See http://hoohoo.ncsa.uiuc.edu/cgi/env.html for CGI interface spec
    env = os.environ.copy()
    env.update({
        "SERVER_SOFTWARE":   server.VERSION,
        "SERVER_NAME":       server_name,
        "SERVER_PORT":       server_port,
        "GATEWAY_INTERFACE": "CGI/1.1",
        "SERVER_PROTOCOL":   "HTTP/%i.%i" % request.clientproto,
        "REQUEST_METHOD":    request.method,
        "PATH_INFO":         '', # Will get filled in later
        "PATH_TRANSLATED":   '', # For our purposes, equiv. to PATH_INFO
        "SCRIPT_NAME":       script_name,
        "QUERY_STRING":      '', # Will get filled in later
        "REMOTE_HOST":       '', # TODO
        "REMOTE_ADDR":       '', # TODO
        "REQUEST_URI":       request.uri,
        "CONTENT_TYPE":      '', # TODO
        "CONTENT_LENGTH":    str(request.stream.length),
        # Anything below here is not part of the CGI specification.
        "REQUEST_SCHEME":    request.scheme,
        })
    
    # Add PATH_INFO from the remaining segments in the context
    postpath = iweb.IRemainingSegments(ctx)
    if postpath:
        env["PATH_TRANSLATED"] = env["PATH_INFO"] = "/" + '/'.join(postpath)

    ## This doesn't work in compat.py right now, either.
    #client = request.getClient()
    #if client is not None:
    #    env['REMOTE_HOST'] = client
    #ip = request.getClientIP()
    #if ip is not None:
    #    env['REMOTE_ADDR'] = ip

    qindex = request.uri.find('?')
    if qindex != -1:
        qs = env['QUERY_STRING'] = request.uri[qindex+1:]
        if '=' in qs:
            qargs = []
        else:
            qargs = [urllib.unquote(x) for x in qs.split('+')]
    else:
        env['QUERY_STRING'] = ''
        qargs = []

    # Propagate HTTP headers
    for title, header in request.headers.getAllRawHeaders():
        envname = title.replace('-', '_').upper()
        if title not in ('content-type', 'content-length'):
            envname = "HTTP_" + envname
        env[envname] = ','.join(header)
            
    return env


class CGIScript(resource.LeafResource):
    """I represent a CGI script.

    My implementation is complex due to the fact that it requires asynchronous
    IPC with an external process with an unpleasant protocol.
    """
    
    def __init__(self, filename, registry=None):
        """Initialize, with the name of a CGI script file.
        """
        self.filename = filename
        resource.LeafResource.__init__(self)

    def render(self, ctx):
        """Do various things to conform to the CGI specification.

        I will set up the usual slew of environment variables, then spin off a
        process.
        """
        request = iweb.IRequest(ctx)
        # Make sure that we don't have an unknown content-length
        if request.stream.length is None:
            return http.Response(responsecode.LENGTH_REQUIRED)
        env = createCGIEnvironment(ctx, request=request)
        env['SCRIPT_FILENAME'] = self.filename
        return self.runProcess(env, request, qargs)

    def http_POST(self, ctx):
        return self.render(ctx)

    def runProcess(self, env, request, qargs=[]):
        d = defer.Deferred()
        p = CGIProcessProtocol(request, d)
        reactor.spawnProcess(p, self.filename, [self.filename]+qargs, env, os.path.dirname(self.filename))
        return d


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

    def runProcess(self, env, request, qargs=[]):
        d = defer.Deferred()
        proc = CGIProcessProtocol(request, d)
        for filterscript in self.filters:
            if os.path.exists(filterscript):
                reactor.spawnProcess(proc, filterscript, [filterscript, self.filename]+qargs, env, os.path.dirname(self.filename))
                break
        else:
            log.err(self.__class__.__name__ + ' could not find any of: ' + ', '.join(self.filters))
            return http.Response(responsecode.INTERNAL_SERVER_ERROR)
        return d


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

    # Remotely relay producer interface.

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
        producingDeferred = s.beginProducing(self.transport.pipes[0])
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
            if name == 'location':
                self.response.code = responsecode.FOUND
            if name == 'status':
                try:
                    statusNum = int(text[:3]) # "123 <description>" sometimes happens.
                except:
                    log.msg("malformed status header: %s" % header)
                else:
                    self.response.code = statusNum
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
        self.deferred.callback(self.response)


class CGIDirectory(resource.Resource, filepath.FilePath):
    addSlash = True
    
    def __init__(self, pathname):
        resource.Resource.__init__(self)
        filepath.FilePath.__init__(self, pathname)

    def locateChild(self, ctx, segments):
        fnp = self.child(segments[0])
        if not fnp.exists():
            print fnp.path, 'does not exist'
            return static.File.childNotFound, ()
        elif fnp.isdir():
            return CGIDirectory(fnp.path), segments[1:]
        else:
            return CGIScript(fnp.path), segments[1:]
        return None, ()

    def render(self, ctx):
        errormsg = 'CGI directories do not support directory listing'
        return http.Response(responsecode.FORBIDDEN)

