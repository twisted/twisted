# -*- test-case-name: twisted.web2.test -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
I contain the interfaces for several web related objects including IRequest
and IResource.  I am based heavily on ideas from C{nevow.inevow}.
"""

from zope.interface import Attribute, Interface, interface

# server.py interfaces
class IResource(Interface):
    """
    An HTTP resource.

    I serve 2 main purposes: one is to provide a standard representation for
    what HTTP specification calls an 'entity', and the other is to provide an
    mechanism for mapping URLs to content.
    """

    def locateChild(req, segments):
        """
        Locate another object which can be adapted to IResource.

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

    def renderHTTP(req):
        """
        Return an IResponse or a deferred which will fire an
        IResponse. This response will be written to the web browser
        which initiated the request.
        """

# Is there a better way to do this than this funky extra class?
_default = object()
class SpecialAdaptInterfaceClass(interface.InterfaceClass):
    # A special adapter for IResource to handle the extra step of adapting
    # from IOldNevowResource-providing resources.
    def __call__(self, other, alternate=_default):
        result = super(SpecialAdaptInterfaceClass, self).__call__(other, alternate)
        if result is not alternate:
            return result
        
        result = IOldNevowResource(other, alternate)
        if result is not alternate:
            result = IResource(result)
            return result
        if alternate is not _default:
            return alternate
        raise TypeError('Could not adapt', other, self)
IResource.__class__ = SpecialAdaptInterfaceClass

class IOldNevowResource(Interface):
    # Shared interface with inevow.IResource
    """
    I am a web resource.
    """

    def locateChild(ctx, segments):
        """
        Locate another object which can be adapted to IResource
        Return a tuple of resource, path segments
        """

    def renderHTTP(ctx):
        """
        Return a string or a deferred which will fire a string. This string
        will be written to the web browser which initiated this request.

        Unlike iweb.IResource, this expects the incoming data to have already been read
        and parsed into request.args and request.content, and expects to return a
        string instead of a response object.
        """

class ICanHandleException(Interface):
    
    # Shared interface with inevow.ICanHandleException
    def renderHTTP_exception(request, failure):
        """
        Render an exception to the given request object.
        """

    def renderInlineException(request, reason):
        """
        Return stan representing the exception, to be printed in the page,
        not replacing the page."""


# http.py interfaces
class IResponse(Interface):
    """
    I'm a response.
    """
    code = Attribute("The HTTP response code")
    headers = Attribute("A http_headers.Headers instance of headers to send")
    stream = Attribute("A stream.IByteStream of outgoing data, or else None.")

class IRequest(Interface):
    """
    I'm a request for a web resource.
    """

    method = Attribute("The HTTP method from the request line, e.g. GET")
    uri = Attribute("The raw URI from the request line. May or may not include host.")
    clientproto = Attribute("Protocol from the request line, e.g. HTTP/1.1")
    
    headers = Attribute("A http_headers.Headers instance of incoming headers.")
    stream = Attribute("A stream.IByteStream of incoming data.")
    
    def writeResponse(response):
        """
        Write an IResponse object to the client.
        """
        
    chanRequest = Attribute("The ChannelRequest. I wonder if this is public really?")


from twisted.web.iweb import IRequest as IOldRequest


class IChanRequestCallbacks(Interface):
    """
    The bits that are required of a Request for interfacing with a
    IChanRequest object
    """

    def __init__(chanRequest, command, path, version, contentLength, inHeaders):
        """
        Create a new Request object.
        
        @param chanRequest: the IChanRequest object creating this request
        @param command: the HTTP command e.g. GET
        @param path: the HTTP path e.g. /foo/bar.html
        @param version: the parsed HTTP version e.g. (1,1)
        @param contentLength: how much data to expect, or None if unknown
        @param inHeaders: the request headers"""

    def process():
        """
        Process the request. Called as soon as it's possibly reasonable
        to return a response. L{handleContentComplete} may or may not
        have been called already.
        """
        
    def handleContentChunk(data):
        """
        Called when a piece of incoming data has been received.
        """
        
    def handleContentComplete():
        """
        Called when the incoming data stream is finished.
        """
        
    def connectionLost(reason):
        """
        Called if the connection was lost.
        """
        
    
class IChanRequest(Interface):
    
    def writeIntermediateResponse(code, headers=None):
        """
        Write a non-terminating response.
        
        Intermediate responses cannot contain data.
        If the channel does not support intermediate responses, do nothing.
        
        @param code: The response code. Should be in the 1xx range.
        @type code: int
        @param headers: the headers to send in the response
        @type headers: C{twisted.web.http_headers.Headers}
        """
    
    def writeHeaders(code, headers):
        """
        Write a final response.

        @param code: The response code. Should not be in the 1xx range.
        @type code: int
        @param headers: the headers to send in the response. They will
            be augmented with any connection-oriented headers as
            necessary for the protocol.
        @type headers: C{twisted.web.http_headers.Headers}
        """
        
    def write(data):
        """
        Write some data.

        @param data: the data bytes
        @type data: str
        """
    
    def finish():
        """
        Finish the request, and clean up the connection if necessary.
        """
    
    def abortConnection():
        """
        Forcibly abort the connection without cleanly closing.
        
        Use if, for example, you can't write all the data you promised.
        """

    def registerProducer(producer, streaming):
        """
        Register a producer with the standard API.
        """
    
    def unregisterProducer():
        """
        Unregister a producer.
        """

    def getHostInfo():
        """
        Returns a tuple of (address, socket user connected to,
        boolean, was it secure).  Note that this should not necessarily
        always return the actual local socket information from
        twisted. E.g. in a CGI, it should use the variables coming
        from the invoking script.
        """

    def getRemoteHost():
        """
        Returns an address of the remote host.

        Like L{getHostInfo}, this information may come from the real
        socket, or may come from additional information, depending on
        the transport.
        """

    persistent = Attribute("""Whether this request supports HTTP connection persistence. May be set to False. Should not be set to other values.""")


class ISite(Interface):
    pass

__all__ = ['ICanHandleException', 'IChanRequest', 'IChanRequestCallbacks', 'IOldNevowResource', 'IOldRequest', 'IRequest', 'IResource', 'IResponse', 'ISite']
