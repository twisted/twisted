# -*- test-case-name: twisted.web.test.test_cgi -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.


"""
I hold resource classes and helper classes that deal with CGI scripts.
"""

# System Imports
import os
import urllib

# Twisted Imports
from twisted.web import http
from twisted.internet import protocol
from twisted.spread import pb
from twisted.python import log, filepath
from twisted.web import resource, server, static


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
        return resource.NoResource()

    def render(self, request):
        notFound = resource.NoResource(
            "CGI directories do not support directory listing.")
        return notFound.render(request)



class CGIScript(resource.Resource):
    """
    L{CGIScript} is a resource which runs child processes according to the CGI
    specification.

    The implementation is complex due to the fact that it requires asynchronous
    IPC with an external process with an unpleasant protocol.
    """
    isLeaf = 1
    def __init__(self, filename, registry=None, reactor=None):
        """
        Initialize, with the name of a CGI script file.
        """
        self.filename = filename
        if reactor is None:
            # This installs a default reactor, if None was installed before.
            # We do a late import here, so that importing the current module
            # won't directly trigger installing a default reactor.
            from twisted.internet import reactor
        self._reactor = reactor


    def render(self, request):
        """
        Do various things to conform to the CGI specification.

        I will set up the usual slew of environment variables, then spin off a
        process.

        @type request: L{twisted.web.http.Request}
        @param request: An HTTP request.
        """
        script_name = "/" + "/".join(request.prepath)
        serverName = request.getRequestHostname().split(':')[0]
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

        ip = request.getClientIP()
        if ip is not None:
            env['REMOTE_ADDR'] = ip
        pp = request.postpath
        if pp:
            env["PATH_INFO"] = "/" + "/".join(pp)

        if hasattr(request, "content"):
            # request.content is either a StringIO or a TemporaryFile, and
            # the file pointer is sitting at the beginning (seek(0,0))
            request.content.seek(0,2)
            length = request.content.tell()
            request.content.seek(0,0)
            env['CONTENT_LENGTH'] = str(length)

        try:
            qindex = request.uri.index('?')
        except ValueError:
            env['QUERY_STRING'] = ''
            qargs = []
        else:
            qs = env['QUERY_STRING'] = request.uri[qindex+1:]
            if '=' in qs:
                qargs = []
            else:
                qargs = [urllib.unquote(x) for x in qs.split('+')]

        # Propagate HTTP headers
        for title, header in request.getAllHeaders().items():
            envname = title.replace('-', '_').upper()
            if title not in ('content-type', 'content-length', 'proxy'):
                envname = "HTTP_" + envname
            env[envname] = header
        # Propagate our environment
        for key, value in os.environ.items():
            if key not in env:
                env[key] = value
        # And they're off!
        self.runProcess(env, request, qargs)
        return server.NOT_DONE_YET


    def runProcess(self, env, request, qargs=[]):
        """
        Run the cgi script.

        @type env: A C{dict} of C{str}, or L{None}
        @param env: The environment variables to pass to the process that will
            get spawned. See
            L{twisted.internet.interfaces.IReactorProcess.spawnProcess} for more
            information about environments and process creation.

        @type request: L{twisted.web.http.Request}
        @param request: An HTTP request.

        @type qargs: A C{list} of C{str}
        @param qargs: The command line arguments to pass to the process that
            will get spawned.
        """
        p = CGIProcessProtocol(request)
        self._reactor.spawnProcess(p, self.filename, [self.filename] + qargs,
                                   env, os.path.dirname(self.filename))



class FilteredScript(CGIScript):
    """
    I am a special version of a CGI script, that uses a specific executable.

    This is useful for interfacing with other scripting languages that adhere to
    the CGI standard. My C{filter} attribute specifies what executable to run,
    and my C{filename} init parameter describes which script to pass to the
    first argument of that script.

    To customize me for a particular location of a CGI interpreter, override
    C{filter}.

    @type filter: C{str}
    @ivar filter: The absolute path to the executable.
    """

    filter = '/usr/bin/cat'


    def runProcess(self, env, request, qargs=[]):
        """
        Run a script through the C{filter} executable.

        @type env: A C{dict} of C{str}, or L{None}
        @param env: The environment variables to pass to the process that will
            get spawned. See
            L{twisted.internet.interfaces.IReactorProcess.spawnProcess} for more
            information about environments and process creation.

        @type request: L{twisted.web.http.Request}
        @param request: An HTTP request.

        @type qargs: A C{list} of C{str}
        @param qargs: The command line arguments to pass to the process that
            will get spawned.
        """
        p = CGIProcessProtocol(request)
        self._reactor.spawnProcess(p, self.filter,
                                   [self.filter, self.filename] + qargs, env,
                                   os.path.dirname(self.filename))



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
                headerend = text.find(delimiter)
                if headerend != -1:
                    headerEnds.append((headerend, delimiter))
            if headerEnds:
                # The script is entirely in control of response headers; disable the
                # default Content-Type value normally provided by
                # twisted.web.server.Request.
                self.request.defaultContentType = None

                headerEnds.sort()
                headerend, delimiter = headerEnds[0]
                self.headertext = text[:headerend]
                # This is a final version of the header text.
                linebreak = delimiter[:len(delimiter)//2]
                headers = self.headertext.split(linebreak)
                for header in headers:
                    br = header.find(': ')
                    if br == -1:
                        log.msg(
                            format='ignoring malformed CGI header: %(header)r',
                            header=header)
                    else:
                        headerName = header[:br].lower()
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
                            # Don't allow the application to control these required headers.
                            if headerName.lower() not in ('server', 'date'):
                                self.request.responseHeaders.addRawHeader(headerName, headerText)
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
                resource.ErrorPage(http.INTERNAL_SERVER_ERROR,
                                   "CGI Script Error",
                                   "Premature end of script headers.").render(self.request))
        self.request.unregisterProducer()
        self.request.finish()
