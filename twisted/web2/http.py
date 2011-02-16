# -*- test-case-name: twisted.web2.test.test_http -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""HyperText Transfer Protocol implementation.

The second coming.

Maintainer: James Y Knight

"""
#        import traceback; log.msg(''.join(traceback.format_stack()))

# system imports
import socket
import time
import cgi

# twisted imports
from twisted.internet import interfaces, error
from twisted.python import log, components
from zope.interface import implements

# sibling imports
from twisted.web2 import responsecode
from twisted.web2 import http_headers
from twisted.web2 import iweb
from twisted.web2 import stream
from twisted.web2.stream import IByteStream

defaultPortForScheme = {'http': 80, 'https':443, 'ftp':21}

def splitHostPort(scheme, hostport):
    """Split the host in "host:port" format into host and port fields. 
    If port was not specified, use the default for the given scheme, if
    known. Returns a tuple of (hostname, portnumber)."""
    
    # Split hostport into host and port
    hostport = hostport.split(':', 1)
    try:
        if len(hostport) == 2:
            return hostport[0], int(hostport[1])
    except ValueError:
        pass
    return hostport[0], defaultPortForScheme.get(scheme, 0)


def parseVersion(strversion):
    """Parse version strings of the form Protocol '/' Major '.' Minor. E.g. 'HTTP/1.1'.
    Returns (protocol, major, minor).
    Will raise ValueError on bad syntax."""

    proto, strversion = strversion.split('/')
    major, minor = strversion.split('.')
    major, minor = int(major), int(minor)
    if major < 0 or minor < 0:
        raise ValueError("negative number")
    return (proto.lower(), major, minor)


class HTTPError(Exception):
    def __init__(self, codeOrResponse):
        """An Exception for propagating HTTP Error Responses.

        @param codeOrResponse: The numeric HTTP code or a complete http.Response
            object.
        @type codeOrResponse: C{int} or L{http.Response}
        """
        Exception.__init__(self)
        self.response = iweb.IResponse(codeOrResponse)

    def __repr__(self):
        return "<%s %s>" % (self.__class__.__name__, self.response)


class Response(object):
    """An object representing an HTTP Response to be sent to the client.
    """
    implements(iweb.IResponse)
    
    code = responsecode.OK
    headers = None
    stream = None
    
    def __init__(self, code=None, headers=None, stream=None):
        """
        @param code: The HTTP status code for this Response
        @type code: C{int}
        
        @param headers: Headers to be sent to the client.
        @type headers: C{dict}, L{twisted.web2.http_headers.Headers}, or 
            C{None}
        
        @param stream: Content body to send to the HTTP client
        @type stream: L{twisted.web2.stream.IByteStream}
        """

        if code is not None:
            self.code = int(code)

        if headers is not None:
            if isinstance(headers, dict):
                headers = http_headers.Headers(headers)
            self.headers=headers
        else:
            self.headers = http_headers.Headers()

        if stream is not None:
            self.stream = IByteStream(stream)

    def __repr__(self):
        if self.stream is None:
            streamlen = None
        else:
            streamlen = self.stream.length

        return "<%s.%s code=%d, streamlen=%s>" % (self.__module__, self.__class__.__name__, self.code, streamlen)


class StatusResponse (Response):
    """
    A L{Response} object which simply contains a status code and a description of
    what happened.
    """
    def __init__(self, code, description, title=None):
        """
        @param code: a response code in L{responsecode.RESPONSES}.
        @param description: a string description.
        @param title: the message title.  If not specified or C{None}, defaults
            to C{responsecode.RESPONSES[code]}.
        """
        if title is None:
            title = cgi.escape(responsecode.RESPONSES[code])

        output = "".join((
            "<html>",
            "<head>",
            "<title>%s</title>" % (title,),
            "</head>",
            "<body>",
            "<h1>%s</h1>" % (title,),
            "<p>%s</p>" % (cgi.escape(description),),
            "</body>",
            "</html>",
        ))

        if type(output) == unicode:
            output = output.encode("utf-8")
            mime_params = {"charset": "utf-8"}
        else:
            mime_params = {}

        super(StatusResponse, self).__init__(code=code, stream=output)

        self.headers.setHeader("content-type", http_headers.MimeType("text", "html", mime_params))

        self.description = description

    def __repr__(self):
        return "<%s %s %s>" % (self.__class__.__name__, self.code, self.description)


class RedirectResponse (StatusResponse):
    """
    A L{Response} object that contains a redirect to another network location.
    """
    def __init__(self, location):
        """
        @param location: the URI to redirect to.
        """
        super(RedirectResponse, self).__init__(
            responsecode.MOVED_PERMANENTLY,
            "Document moved to %s." % (location,)
        )

        self.headers.setHeader("location", location)

        
def NotModifiedResponse(oldResponse=None):
    if oldResponse is not None:
        headers=http_headers.Headers()
        for header in (
            # Required from sec 10.3.5:
            'date', 'etag', 'content-location', 'expires',
            'cache-control', 'vary',
            # Others:
            'server', 'proxy-authenticate', 'www-authenticate', 'warning'):
            value = oldResponse.headers.getRawHeaders(header)
            if value is not None:
                headers.setRawHeaders(header, value)
    else:
        headers = None
    return Response(code=responsecode.NOT_MODIFIED, headers=headers)
    

def checkPreconditions(request, response=None, entityExists=True, etag=None, lastModified=None):
    """Check to see if this request passes the conditional checks specified
    by the client. May raise an HTTPError with result codes L{NOT_MODIFIED}
    or L{PRECONDITION_FAILED}, as appropriate.

    This function is called automatically as an output filter for GET and
    HEAD requests. With GET/HEAD, it is not important for the precondition
    check to occur before doing the action, as the method is non-destructive.

    However, if you are implementing other request methods, like PUT
    for your resource, you will need to call this after determining
    the etag and last-modified time of the existing resource but
    before actually doing the requested action. In that case, 

    This examines the appropriate request headers for conditionals,
    (If-Modified-Since, If-Unmodified-Since, If-Match, If-None-Match,
    or If-Range), compares with the etag and last and
    and then sets the response code as necessary.

    @param response: This should be provided for GET/HEAD methods. If
             it is specified, the etag and lastModified arguments will
             be retrieved automatically from the response headers and
             shouldn't be separately specified. Not providing the
             response with a GET request may cause the emitted
             "Not Modified" responses to be non-conformant.
             
    @param entityExists: Set to False if the entity in question doesn't
             yet exist. Necessary for PUT support with 'If-None-Match: *'.
             
    @param etag: The etag of the resource to check against, or None.
    
    @param lastModified: The last modified date of the resource to check
              against, or None.
              
    @raise: HTTPError: Raised when the preconditions fail, in order to
             abort processing and emit an error page.

    """
    if response:
        assert etag is None and lastModified is None
        # if the code is some sort of error code, don't do anything
        if not ((response.code >= 200 and response.code <= 299)
                or response.code == responsecode.PRECONDITION_FAILED):
            return False
        etag = response.headers.getHeader("etag")
        lastModified = response.headers.getHeader("last-modified")
    
    def matchETag(tags, allowWeak):
        if entityExists and '*' in tags:
            return True
        if etag is None:
            return False
        return ((allowWeak or not etag.weak) and
                ([etagmatch for etagmatch in tags if etag.match(etagmatch, strongCompare=not allowWeak)]))

    # First check if-match/if-unmodified-since
    # If either one fails, we return PRECONDITION_FAILED
    match = request.headers.getHeader("if-match")
    if match:
        if not matchETag(match, False):
            raise HTTPError(StatusResponse(responsecode.PRECONDITION_FAILED, "Requested resource does not have a matching ETag."))

    unmod_since = request.headers.getHeader("if-unmodified-since")
    if unmod_since:
        if not lastModified or lastModified > unmod_since:
            raise HTTPError(StatusResponse(responsecode.PRECONDITION_FAILED, "Requested resource has changed."))

    # Now check if-none-match/if-modified-since.
    # This bit is tricky, because of the requirements when both IMS and INM
    # are present. In that case, you can't return a failure code
    # unless *both* checks think it failed.
    # Also, if the INM check succeeds, ignore IMS, because INM is treated
    # as more reliable.

    # I hope I got the logic right here...the RFC is quite poorly written
    # in this area. Someone might want to verify the testcase against
    # RFC wording.

    # If IMS header is later than current time, ignore it.
    notModified = None
    ims = request.headers.getHeader('if-modified-since')
    if ims:
        notModified = (ims < time.time() and lastModified and lastModified <= ims)

    inm = request.headers.getHeader("if-none-match")
    if inm:
        if request.method in ("HEAD", "GET"):
            # If it's a range request, don't allow a weak ETag, as that
            # would break. 
            canBeWeak = not request.headers.hasHeader('Range')
            if notModified != False and matchETag(inm, canBeWeak):
                raise HTTPError(NotModifiedResponse(response))
        else:
            if notModified != False and matchETag(inm, False):
                raise HTTPError(StatusResponse(responsecode.PRECONDITION_FAILED, "Requested resource has a matching ETag."))
    else:
        if notModified == True:
            if request.method in ("HEAD", "GET"):
                raise HTTPError(NotModifiedResponse(response))
            else:
                # S14.25 doesn't actually say what to do for a failing IMS on
                # non-GET methods. But Precondition Failed makes sense to me.
                raise HTTPError(StatusResponse(responsecode.PRECONDITION_FAILED, "Requested resource has not changed."))

def checkIfRange(request, response):
    """Checks for the If-Range header, and if it exists, checks if the
    test passes. Returns true if the server should return partial data."""

    ifrange = request.headers.getHeader("if-range")

    if ifrange is None:
        return True
    if isinstance(ifrange, http_headers.ETag):
        return ifrange.match(response.headers.getHeader("etag"), strongCompare=True)
    else:
        return ifrange == response.headers.getHeader("last-modified")


class _NotifyingProducerStream(stream.ProducerStream):
    doStartReading = None

    def __init__(self, length=None, doStartReading=None):
        stream.ProducerStream.__init__(self, length=length)
        self.doStartReading = doStartReading
    
    def read(self):
        if self.doStartReading is not None:
            doStartReading = self.doStartReading
            self.doStartReading = None
            doStartReading()
            
        return stream.ProducerStream.read(self)

    def write(self, data):
        self.doStartReading = None
        stream.ProducerStream.write(self, data)

    def finish(self):
        self.doStartReading = None
        stream.ProducerStream.finish(self)


# response codes that must have empty bodies
NO_BODY_CODES = (responsecode.NO_CONTENT, responsecode.NOT_MODIFIED)

class Request(object):
    """A HTTP request.

    Subclasses should override the process() method to determine how
    the request will be processed.
    
    @ivar method: The HTTP method that was used.
    @ivar uri: The full URI that was requested (includes arguments).
    @ivar headers: All received headers
    @ivar clientproto: client HTTP version
    @ivar stream: incoming data stream.
    """
    
    implements(iweb.IRequest, interfaces.IConsumer)
    
    known_expects = ('100-continue',)
    
    def __init__(self, chanRequest, command, path, version, contentLength, headers):
        """
        @param chanRequest: the channel request we're associated with.
        """
        self.chanRequest = chanRequest
        self.method = command
        self.uri = path
        self.clientproto = version
        
        self.headers = headers
        
        if '100-continue' in self.headers.getHeader('expect', ()):
            doStartReading = self._sendContinue
        else:
            doStartReading = None
        self.stream = _NotifyingProducerStream(contentLength, doStartReading)
        self.stream.registerProducer(self.chanRequest, True)
        
    def checkExpect(self):
        """Ensure there are no expectations that cannot be met.
        Checks Expect header against self.known_expects."""
        expects = self.headers.getHeader('expect', ())
        for expect in expects:
            if expect not in self.known_expects:
                raise HTTPError(responsecode.EXPECTATION_FAILED)
    
    def process(self):
        """Called by channel to let you process the request.
        
        Can be overridden by a subclass to do something useful."""
        pass
    
    def handleContentChunk(self, data):
        """Callback from channel when a piece of data has been received.
        Puts the data in .stream"""
        self.stream.write(data)
    
    def handleContentComplete(self):
        """Callback from channel when all data has been received. """
        self.stream.unregisterProducer()
        self.stream.finish()
        
    def connectionLost(self, reason):
        """connection was lost"""
        pass

    def __repr__(self):
        return '<%s %s %s>'% (self.method, self.uri, self.clientproto)

    def _sendContinue(self):
        self.chanRequest.writeIntermediateResponse(responsecode.CONTINUE)

    def _finished(self, x):
        """We are finished writing data."""
        self.chanRequest.finish()

    def _error(self, reason):
        if reason.check(error.ConnectionLost):
            log.msg("Request error: " + reason.getErrorMessage())
        else:
            log.err(reason)
            # Only bother with cleanup on errors other than lost connection.
            self.chanRequest.abortConnection()
        
    def writeResponse(self, response):
        """
        Write a response.
        """
        if self.stream.doStartReading is not None:
            # Expect: 100-continue was requested, but 100 response has not been
            # sent, and there's a possibility that data is still waiting to be
            # sent.
            # 
            # Ideally this means the remote side will not send any data.
            # However, because of compatibility requirements, it might timeout,
            # and decide to do so anyways at the same time we're sending back 
            # this response. Thus, the read state is unknown after this.
            # We must close the connection.
            self.chanRequest.channel.setReadPersistent(False)
            # Nothing more will be read
            self.chanRequest.allContentReceived()

        if response.code != responsecode.NOT_MODIFIED:
            # Not modified response is *special* and doesn't get a content-length.
            if response.stream is None:
                response.headers.setHeader('content-length', 0)
            elif response.stream.length is not None:
                response.headers.setHeader('content-length', response.stream.length)
        self.chanRequest.writeHeaders(response.code, response.headers)
        
        # if this is a "HEAD" request, or a special response code,
        # don't return any data.
        if self.method == "HEAD" or response.code in NO_BODY_CODES:
            if response.stream is not None:
                response.stream.close()
            self._finished(None)
            return
            
        d = stream.StreamProducer(response.stream).beginProducing(self.chanRequest)
        d.addCallback(self._finished).addErrback(self._error)

    
from twisted.web2 import compat
components.registerAdapter(compat.makeOldRequestAdapter, iweb.IRequest, iweb.IOldRequest)
components.registerAdapter(compat.OldNevowResourceAdapter, iweb.IOldNevowResource, iweb.IResource)
components.registerAdapter(Response, int, iweb.IResponse)

try:
    # If twisted.web is installed, add an adapter for it
    from twisted.web import resource
except:
    pass
else:
    components.registerAdapter(compat.OldResourceAdapter, resource.IResource, iweb.IOldNevowResource)

__all__ = ['HTTPError', 'NotModifiedResponse', 'Request', 'Response', 'checkIfRange', 'checkPreconditions', 'defaultPortForScheme', 'parseVersion', 'splitHostPort']

