# -*- test-case-name: twisted.web.test.test_cgi -*-
# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.


"""I hold resource classes and helper classes that deal with CGI scripts.
"""

# System Imports
import string
import os
import sys
import urllib

# Twisted Imports
from twisted.web import http
from twisted.internet import reactor, protocol
from twisted.spread import pb
from twisted.python import log, filepath

# Sibling Imports
import server
import error
import html
import resource
import static
from server import NOT_DONE_YET

class CGIDirectory(resource.Resource, filepath.FilePath):
    def __init__(self, pathname):
        resource.Resource.__init__(self)
        filepath.FilePath.__init__(self, pathname)

    def getChild(self, path, request):
        fnp = self.child(path)
        if not fnp.exists():
            return static.File.childNotFound
        elif fnp.isdir():
            return CGIDirectory(fnp.path)
        else:
            return CGIScript(fnp.path)
        return error.NoResource()

    def render(self, request):
        return error.NoResource("CGI directories do not support directory listing.").render(request)

class CGIScript(resource.Resource):
    """I represent a CGI script.

    My implementation is complex due to the fact that it requires asynchronous
    IPC with an external process with an unpleasant protocol.
    """
    isLeaf = 1
    def __init__(self, filename, registry=None):
        """Initialize, with the name of a CGI script file.
        """
        self.filename = filename

    def render(self, request):
        """Do various things to conform to the CGI specification.

        I will set up the usual slew of environment variables, then spin off a
        process.
        """
        script_name = "/"+string.join(request.prepath, '/')
        python_path = string.join(sys.path, os.pathsep)
        serverName = string.split(request.getRequestHostname(), ':')[0]
        env = {"SERVER_SOFTWARE":   server.version,
               "SERVER_NAME":       serverName,
               "GATEWAY_INTERFACE": "CGI/1.1",
               "SERVER_PROTOCOL":   request.clientproto,
               "SERVER_PORT":       str(request.getHost().port),
               "REQUEST_METHOD":    request.method,
               "SCRIPT_NAME":       script_name, # XXX
               "SCRIPT_FILENAME":   self.filename,
               "REQUEST_URI":       request.uri,
        }

        client = request.getClient()
        if client is not None:
            env['REMOTE_HOST'] = client
        ip = request.getClientIP()
        if ip is not None:
            env['REMOTE_ADDR'] = ip
        pp = request.postpath
        if pp:
            env["PATH_INFO"] = "/"+string.join(pp, '/')

        if hasattr(request, "content"):
            # request.content is either a StringIO or a TemporaryFile, and
            # the file pointer is sitting at the beginning (seek(0,0))
            request.content.seek(0,2)
            length = request.content.tell()
            request.content.seek(0,0)
            env['CONTENT_LENGTH'] = str(length)

        qindex = string.find(request.uri, '?')
        if qindex != -1:
            qs = env['QUERY_STRING'] = request.uri[qindex+1:]
            if '=' in qs:
                qargs = []
            else:
                qargs = [urllib.unquote(x) for x in qs.split('+')]
        else:
            env['QUERY_STRING'] = ''
            qargs = []

        # Propogate HTTP headers
        for title, header in request.getAllHeaders().items():
            envname = string.upper(string.replace(title, '-', '_'))
            if title not in ('content-type', 'content-length'):
                envname = "HTTP_" + envname
            env[envname] = header
        # Propogate our environment
        for key, value in os.environ.items():
            if not env.has_key(key):
                env[key] = value
        # And they're off!
        self.runProcess(env, request, qargs)
        return NOT_DONE_YET

    def runProcess(self, env, request, qargs=[]):
        p = CGIProcessProtocol(request)
        reactor.spawnProcess(p, self.filename, [self.filename]+qargs, env, os.path.dirname(self.filename))


class FilteredScript(CGIScript):
    """I am a special version of a CGI script, that uses a specific executable.

    This is useful for interfacing with other scripting languages that adhere
    to the CGI standard (cf. PHPScript).  My 'filter' attribute specifies what
    executable to run, and my 'filename' init parameter describes which script
    to pass to the first argument of that script.
    """

    filter = '/usr/bin/cat'

    def runProcess(self, env, request, qargs=[]):
        p = CGIProcessProtocol(request)
        reactor.spawnProcess(p, self.filter, [self.filter, self.filename]+qargs, env, os.path.dirname(self.filename))


class PHP3Script(FilteredScript):
    """I am a FilteredScript that uses the default PHP3 command on most systems.
    """

    filter = '/usr/bin/php3'


class PHPScript(FilteredScript):
    """I am a FilteredScript that uses the PHP command on most systems.
    Sometimes, php wants the path to itself as argv[0]. This is that time.
    """

    filter = '/usr/bin/php4'


class CGIProcessProtocol(protocol.ProcessProtocol, pb.Viewable):
    handling_headers = 1
    headers_written = 0
    headertext = ''
    errortext = ''

    # Remotely relay producer interface.

    def view_resumeProducing(self, issuer):
        self.resumeProducing()

    def view_pauseProducing(self, issuer):
        self.pauseProducing()

    def view_stopProducing(self, issuer):
        self.stopProducing()

    def resumeProducing(self):
        self.transport.resumeProducing()

    def pauseProducing(self):
        self.transport.pauseProducing()

    def stopProducing(self):
        self.transport.loseConnection()

    def __init__(self, request):
        self.request = request

    def connectionMade(self):
        self.request.registerProducer(self, 1)
        self.request.content.seek(0, 0)
        content = self.request.content.read()
        if content:
            self.transport.write(content)
        self.transport.closeStdin()

    def errReceived(self, error):
        self.errortext = self.errortext + error

    def outReceived(self, output):
        """
        Handle a chunk of input
        """
        # First, make sure that the headers from the script are sorted
        # out (we'll want to do some parsing on these later.)
        if self.handling_headers:
            text = self.headertext + output
            headerEnds = []
            for delimiter in '\n\n','\r\n\r\n','\r\r', '\n\r\n':
                headerend = string.find(text,delimiter)
                if headerend != -1:
                    headerEnds.append((headerend, delimiter))
            if headerEnds:
                headerEnds.sort()
                headerend, delimiter = headerEnds[0]
                self.headertext = text[:headerend]
                # This is a final version of the header text.
                linebreak = delimiter[:len(delimiter)/2]
                headers = string.split(self.headertext, linebreak)
                for header in headers:
                    br = string.find(header,': ')
                    if br == -1:
                        log.msg( 'ignoring malformed CGI header: %s' % header )
                    else:
                        headerName = string.lower(header[:br])
                        headerText = header[br+2:]
                        if headerName == 'location':
                            self.request.setResponseCode(http.FOUND)
                        if headerName == 'status':
                            try:
                                statusNum = int(headerText[:3]) #"XXX <description>" sometimes happens.
                            except:
                                log.msg( "malformed status header" )
                            else:
                                self.request.setResponseCode(statusNum)
                        else:
                            self.request.setHeader(headerName,headerText)
                output = text[headerend+len(delimiter):]
                self.handling_headers = 0
            if self.handling_headers:
                self.headertext = text
        if not self.handling_headers:
            self.request.write(output)

    def processEnded(self, reason):
        if reason.value.exitCode != 0:
            log.msg("CGI %s exited with exit code %s" %
                    (self.request.uri, reason.value.exitCode))
        if self.errortext:
            log.msg("Errors from CGI %s: %s" % (self.request.uri, self.errortext))
        if self.handling_headers:
            log.msg("Premature end of headers in %s: %s" % (self.request.uri, self.headertext))
            self.request.write(
                error.ErrorPage(http.INTERNAL_SERVER_ERROR,
                                "CGI Script Error",
                                "Premature end of script headers.").render(self.request))
        self.request.unregisterProducer()
        self.request.finish()
