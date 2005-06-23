# -*- test-case-name: twisted.web2.test -*-

"""
    I contain the interfaces for several web related objects including IRequest
    and IResource.  I am based heavily on ideas from nevow.inevow
"""

from twisted.python import components
from zope.interface import Attribute, Interface, interface

# server.py interfaces
class IResource(Interface):
    """
        I am a web resource.
    """

    def locateChild(self, ctx, segments):
        """Locate another object which can be adapted to IResource.

        @return: A 2-tuple of (resource, remaining-path-segments),
                 or a deferred which will fire the above.
                 
                 Causes the object publishing machinery to continue on
                 with specified resource and segments, calling the
                 appropriate method on the specified resource.
                 
                 If you return (self, L{server.StopTraversal}), this
                 instructs web2 to immediately stop the lookup stage,
                 and switch to the rendering stage, leaving the
                 remaining path alone for your render function to
                 handle.
        """

    def renderHTTP(self, ctx):
        """Return an IResponse or a deferred which will fire an
        IResponse. This response will be written to the web browser
        which initiated the request.
        """

# Is there a better way to do this than this funky extra class?
class SpecialAdaptInterfaceClass(interface.InterfaceClass):
    # A special adapter for IResource to handle the extra step of adapting
    # from IOldNevowResource-providing resources.
    def __adapt__(self, other):
        result = interface.InterfaceClass.__adapt__(self, other)
        if result is not None:
            return result
        
        result = IOldNevowResource(other, None)
        if hasattr(result, "__class__"):
            components.fixClassImplements(result.__class__)
        if result is not None:
            return IResource(result)
IResource.__class__ = SpecialAdaptInterfaceClass

class IOldNevowResource(components.Interface):
    # Shared interface with inevow.IResource
    """
        I am a web resource.
    """

    def locateChild(self, ctx, segments):
        """Locate another object which can be adapted to IResource
        Return a tuple of resource, path segments
        """

    def renderHTTP(self, ctx):
        """Return a string or a deferred which will fire a string. This string
        will be written to the web browser which initiated this request.

        Unlike iweb.IResource, this expects the incoming data to have already been read
        and parsed into request.args and request.content, and expects to return a
        string instead of a response object.
        """

class ICanHandleException(components.Interface):
    # Shared interface with inevow.ICanHandleException
    def renderHTTP_exception(self, request, failure):
        """Render an exception to the given request object.
        """

    def renderInlineException(self, context, reason):
        """Return stan representing the exception, to be printed in the page,
        not replacing the page."""


# http.py interfaces
class IResponse(Interface):
    """I'm a response."""
    code = Attribute("The HTTP response code")
    headers = Attribute("A http_headers.Headers instance of headers to send")
    stream = Attribute("A stream.IByteStream of outgoing data, or else None.")

class IRequest(Interface):
    """I'm a request for a web resource
    """

    method = Attribute("The HTTP method from the request line, e.g. GET")
    uri = Attribute("The raw URI from the request line. May or may not include host.")
    clientproto = Attribute("Protocol from the request line, e.g. HTTP/1.1")
    
    headers = Attribute("A http_headers.Headers instance of incoming headers.")
    stream = Attribute("A stream.IByteStream of incoming data.")
    
    def writeResponse(response):
        """Write an IResponse object to the client"""
        
    chanRequest = Attribute("The ChannelRequest. I wonder if this is public really?")

class IOldRequest(components.Interface):
    # Shared interface with inevow.ICurrentSegments
    """An old HTTP request.

    Subclasses should override the process() method to determine how
    the request will be processed.
    
    @ivar method: The HTTP method that was used.
    @ivar uri: The full URI that was requested (includes arguments).
    @ivar path: The path only (arguments not included).
    @ivar args: All of the arguments, including URL and POST arguments.
    @type args: A mapping of strings (the argument names) to lists of values.
                i.e., ?foo=bar&foo=baz&quux=spam results in
                {'foo': ['bar', 'baz'], 'quux': ['spam']}.
    @ivar received_headers: All received headers
    """
    # Methods for received request
    def getHeader(self, key):
        """Get a header that was sent from the network.
        """
        
    def getCookie(self, key):
        """Get a cookie that was sent from the network.
        """    


    def getAllHeaders(self):
        """Return dictionary of all headers the request received."""

    def getRequestHostname(self):
        """Get the hostname that the user passed in to the request.

        This will either use the Host: header (if it is available) or the
        host we are listening on if the header is unavailable.
        """

    def getHost(self):
        """Get my originally requesting transport's host.

        Don't rely on the 'transport' attribute, since Request objects may be
        copied remotely.  For information on this method's return value, see
        twisted.internet.tcp.Port.
        """
        
    def getClientIP(self):
        pass
    def getClient(self):
        pass
    def getUser(self):
        pass
    def getPassword(self):
        pass
    def isSecure(self):
        pass

    def getSession(self, sessionInterface = None):
        pass
    
    def URLPath(self):
        pass

    def prePathURL(self):
        pass

    def rememberRootURL(self):
        """
        Remember the currently-processed part of the URL for later
        recalling.
        """
        
    def getRootURL(self):
        """
        Get a previously-remembered URL.
        """
        
    # Methods for outgoing request
    def finish(self):
        """We are finished writing data."""

    def write(self, data):
        """
        Write some data as a result of an HTTP request.  The first
        time this is called, it writes out response data.
        """

    def addCookie(self, k, v, expires=None, domain=None, path=None, max_age=None, comment=None, secure=None):
        """Set an outgoing HTTP cookie.

        In general, you should consider using sessions instead of cookies, see
        twisted.web.server.Request.getSession and the
        twisted.web.server.Session class for details.
        """

    def setResponseCode(self, code, message=None):
        """Set the HTTP response code.
        """

    def setHeader(self, k, v):
        """Set an outgoing HTTP header.
        """

    def redirect(self, url):
        """Utility function that does a redirect.

        The request should have finish() called after this.
        """

    def setLastModified(self, when):
        """Set the X{Last-Modified} time for the response to this request.

        If I am called more than once, I ignore attempts to set
        Last-Modified earlier, only replacing the Last-Modified time
        if it is to a later value.

        If I am a conditional request, I may modify my response code
        to L{NOT_MODIFIED} if appropriate for the time given.

        @param when: The last time the resource being returned was
            modified, in seconds since the epoch.
        @type when: number
        @return: If I am a X{If-Modified-Since} conditional request and
            the time given is not newer than the condition, I return
            L{http.CACHED<CACHED>} to indicate that you should write no
            body.  Otherwise, I return a false value.
        """

    def setETag(self, etag):
        """Set an X{entity tag} for the outgoing response.

        That's \"entity tag\" as in the HTTP/1.1 X{ETag} header, \"used
        for comparing two or more entities from the same requested
        resource.\"

        If I am a conditional request, I may modify my response code
        to L{NOT_MODIFIED} or L{PRECONDITION_FAILED}, if appropriate
        for the tag given.

        @param etag: The entity tag for the resource being returned.
        @type etag: string
        @return: If I am a X{If-None-Match} conditional request and
            the tag matches one in the request, I return
            L{http.CACHED<CACHED>} to indicate that you should write
            no body.  Otherwise, I return a false value.
        """

    def setHost(self, host, port, ssl=0):
        """Change the host and port the request thinks it's using.

        This method is useful for working with reverse HTTP proxies (e.g.
        both Squid and Apache's mod_proxy can do this), when the address
        the HTTP client is using is different than the one we're listening on.

        For example, Apache may be listening on https://www.example.com, and then
        forwarding requests to http://localhost:8080, but we don't want HTML produced
        by Twisted to say 'http://localhost:8080', they should say 'https://www.example.com',
        so we do::

           request.setHost('www.example.com', 443, ssl=1)

        This method is experimental.
        """

class IChanRequestCallbacks(Interface):
    """The bits that are required of a Request for interfacing with a
    IChanRequest object"""

    def __init__(chanRequest, command, path, version, in_headers):
        """Create a new Request object.
        @param chanRequest: the IChanRequest object creating this request
        @param command: the HTTP command e.g. GET
        @param path: the HTTP path e.g. /foo/bar.html
        @param version: the parsed HTTP version e.g. (1,1)"""

    def handleContentChunk(data):
        """Called when a piece of incoming data has been received."""
        
    def handleContentComplete():
        """Called when the incoming data stream is finished."""
        
    def connectionLost(reason):
        """Called if the connection was lost."""
        
    
class IChanRequest(Interface):
    def writeIntermediateResponse(code, headers=None):
        """Write a non-terminating response.
        
        Intermediate responses cannot contain data.
        If the channel does not support intermediate responses, do nothing.
        
        @ivar code: The response code. Should be in the 1xx range.
        @type code: int
        @ivar headers: the headers to send in the response
        @type headers: C{twisted.web.http_headers.Headers}
        """
        pass
    
    def writeHeaders(code, headers):
        """Write a final response.

        @param code: The response code. Should not be in the 1xx range.
        @type code: int
        @param headers: the headers to send in the response. They will be augmented
            with any connection-oriented headers as necessary for the protocol.
        @type headers: C{twisted.web.http_headers.Headers}
        """
        pass
        
    def write(data):
        """Write some data.

        @param data: the data bytes
        @type data: str
        """
        pass
    
    def finish():
        """Finish the request, and clean up the connection if necessary.
        """
        pass
    
    def abortConnection():
        """Forcibly abort the connection without cleanly closing.
        Use if, for example, you can't write all the data you promised.
        """
        pass

    def registerProducer(producer, streaming):
        """Register a producer with the standard API."""
        pass
    
    def unregisterProducer():
        """Unregister a producer."""
        pass

    def getHostInfo():
        """Returns a tuple of (address, socket user connected to,
        boolean, was it secure).  Note that this should not necsessarily
        always return the actual local socket information from
        twisted. E.g. in a CGI, it should use the variables coming
        from the invoking script.
        """

    def getRemoteHost():
        """Returns an address of the remote host.

        Like getHostInfo, this information may come from the real
        socket, or may come from additional information, depending on
        the transport.
        """
        

    persistent = Attribute("""Whether this request supports HTTP connection persistence. May be set to False. Should not be set to other values.""")

__all__ = ['ICanHandleException', 'IChanRequest', 'IChanRequestCallbacks', 'IOldNevowResource', 'IOldRequest', 'IRequest', 'IResource', 'IResponse']
