"""
    I contain the interfaces for several web related objects including IRequest
    and IResource.  I am based heavily on ideas from nevow.inevow
"""

from twisted.python import components
from zope.interface import Attribute

# server.py interfaces
class IResource(components.Interface):
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
        """

class ICanHandleException(components.Interface):
    # Shared interface with inevow.ICanHandleException
    def renderHTTP_exception(self, request, failure):
        """Render an exception to the given request object.
        """

    def renderInlineException(self, context, reason):
        """Return stan representing the exception, to be printed in the page,
        not replacing the page."""

class IRemainingSegments(components.Interface):
    # Shared interface with inevow.IRemainingSegments
    """During the URL traversal process, requesting this from the context
    will result in a tuple of the segments remaining to be processed.
    
    Equivalent to request.postpath in twisted.web
    """


class ICurrentSegments(components.Interface):
    # Shared interface with inevow.ICurrentSegments
    """Requesting this from the context will result in a tuple of path segments
    which have been consumed to reach the current Page instance during
    the URL traversal process.

    Equivalent to request.prepath in twisted.web
    """



# http.py interfaces
class IResponse(components.Interface):
    code = Attribute("The HTTP response code")
    headers = Attribute("A http_headers.Headers instance of headers to send")
    stream = Attribute("A stream.IStream")

class IRequest(components.Interface):
    """I'm a request for a web resource
    First draft of public interface.
    """

    def acceptData(self):
        pass
    def finish(self):
        pass
    def write(self, data):
        pass
    
    def checkPreconditions(self, entityExists=True):
        pass
    def checkIfRange(self):
        pass

    def registerProducer(self, producer, streaming):
        pass
    def unregisterProducer(self):
        pass
    
    chanRequest = Attribute("")
    method = Attribute("")
    uri = Attribute("")
    clientproto = Attribute("")
    in_headers = Attribute("")
    
    startedWriting = Attribute("")
    out_headers = Attribute("")
    sentLength = Attribute("")

class IOldRequest(components.Interface):
    """I'm an old request, completely unspecified. :("""

class IChanRequestCallbacks(components.Interface):
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
        
    
class IChanRequest(components.Interface):
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
    
    persistent = Attribute("""Whether this request supports HTTP connection persistence. May be set to False. Should not be set to other values.""")

