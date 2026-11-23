# -*- test-case-name: twisted.web.test -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Interface definitions for L{twisted.web}.

@var UNKNOWN_LENGTH: An opaque object which may be used as the value of
    L{IBodyProducer.length} to indicate that the length of the entity
    body is not known in advance.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Protocol as TypingProtocol, Sequence

from zope.interface import Attribute, Interface

from twisted.cred.credentials import IUsernameDigestHash
from twisted.internet.defer import Deferred
from twisted.internet.interfaces import (
    IAddress,
    IConsumer,
    IOpenSSLClientConnectionCreator,
    IProducer,
    IPushProducer,
    ITransport,
)
from twisted.web.http_headers import Headers

if TYPE_CHECKING:
    from twisted.web.template import Flattenable, Tag


class _IChannelRequest(Interface):
    """
    The interface that a L{ChannelDefinition} expects of its request.

    This is a separate interface from L{IMinimalRequest} even though they are
    present on the same object, since L{IMinimalRequest} is application-facing
    and this is channel-facing.

    This is private because it is a hodgepodge of different methods that demand
    too much specificity of the request, something extracted rather than
    intentionally designed.
    """

    requestHeaders = Attribute(
        "A L{http_headers.Headers} instance giving all received HTTP request "
        "headers."
    )

    responseHeaders = Attribute(
        "A L{http_headers.Headers} instance holding all HTTP response "
        "headers to be sent."
    )

    def connectionLost(reason):
        """
        The underlying connection has been lost.

        @param reason: A failure instance indicating the reason why
            the connection was lost.
        @type reason: L{twisted.python.failure.Failure}
        """

    def gotLength(length):
        """
        Called when L{HTTPChannel} has determined the length, if any,
        of the incoming request's body.

        @param length: The length of the request's body.
        @type length: L{int} if the request declares its body's length
            and L{None} if it does not.
        """

    def handleContentChunk(data):
        """
        Deliver a received chunk of body data to the request.  Note
        this does not imply chunked transfer encoding.

        @param data: The received chunk.
        @type data: L{bytes}
        """

    def parseCookies():
        """
        Parse the request's cookies out of received headers.
        """

    def requestReceived(command, path, version):
        """
        Called when the entire request, including its body, has been
        received.

        @param command: The request's HTTP command.
        @type command: L{bytes}

        @param path: The request's path.  Note: this is actually what
            RFC7320 calls the URI.
        @type path: L{bytes}

        @param version: The request's HTTP version.
        @type version: L{bytes}
        """

    def __eq__(other: object) -> bool:
        """
        Determines if two requests are the same object.

        @param other: Another object whose identity will be compared
            to this instance's.

        @return: L{True} when the two are the same object and L{False}
            when not.
        """

    def __ne__(other: object) -> bool:
        """
        Determines if two requests are not the same object.

        @param other: Another object whose identity will be compared
            to this instance's.

        @return: L{True} when the two are not the same object and
            L{False} when they are.
        """

    def __hash__():
        """
        Generate a hash value for the request.

        @return: The request's hash value.
        @rtype: L{int}
        """


class IMinimalRequest(IConsumer):
    """
    The minimal interface required of an HTTP request implementation, for
    protocol-level concerns.

    @see: L{IRequest} for the expanded request interface which also includes
        resource-traversal-state concerns.

    @since: Twisted NEXT
    """

    method = Attribute("A L{bytes} giving the HTTP method that was used.")
    uri = Attribute(
        "A L{bytes} giving the full encoded URI which was requested (including"
        " query arguments)."
    )
    path = Attribute(
        "A L{bytes} giving the encoded query path of the request URI (not "
        "including query arguments)."
    )
    args = Attribute(
        "A mapping of decoded query argument names as L{bytes} to "
        "corresponding query argument values as L{list}s of L{bytes}.  "
        "For example, for a URI with C{foo=bar&foo=baz&quux=spam} "
        "for its query part, C{args} will be C{{b'foo': [b'bar', b'baz'], "
        "b'quux': [b'spam']}}."
    )

    requestHeaders = Attribute(
        "A L{http_headers.Headers} instance giving all received HTTP request "
        "headers."
    )

    content = Attribute(
        "A file-like object giving the request body.  This may be a file on "
        "disk, an L{io.BytesIO}, or some other type.  The implementation is "
        "free to decide on a per-request basis."
    )

    responseHeaders = Attribute(
        "A L{http_headers.Headers} instance holding all HTTP response "
        "headers to be sent."
    )

    def getHeader(key):
        """
        Get an HTTP request header.

        @type key: L{bytes} or L{str}
        @param key: The name of the header to get the value of.

        @rtype: L{bytes} or L{str} or L{None}
        @return: The value of the specified header, or L{None} if that header
            was not present in the request. The string type of the result
            matches the type of C{key}.
        """

    def getCookie(key):
        """
        Get a cookie that was sent from the network.

        @type key: L{bytes}
        @param key: The name of the cookie to get.

        @rtype: L{bytes} or L{None}
        @returns: The value of the specified cookie, or L{None} if that cookie
            was not present in the request.
        """

    def getAllHeaders():
        """
        Return dictionary mapping the names of all received headers to the last
        value received for each.

        Since this method does not return all header information,
        C{requestHeaders.getAllRawHeaders()} may be preferred.
        """

    def getRequestHostname():
        """
        Get the hostname that the HTTP client passed in to the request.

        This will either use the C{Host:} header (if it is available; which,
        for a spec-compliant request, it will be) or the IP address of the host
        we are listening on if the header is unavailable.

        @note: This is the I{host portion} of the requested resource, which
            means that:

                1. it might be an IPv4 or IPv6 address, not just a DNS host
                   name,

                2. there's no guarantee it's even a I{valid} host name or IP
                   address, since the C{Host:} header may be malformed,

                3. it does not include the port number.

        @returns: the requested hostname

        @rtype: L{bytes}
        """

    def getHost():
        """
        Get my originally requesting transport's host.

        @return: An L{IAddress<twisted.internet.interfaces.IAddress>}.
        """

    def getClientAddress():
        """
        Return the address of the client who submitted this request.

        The address may not be a network address.  Callers must check
        its type before using it.

        @since: 18.4

        @return: the client's address.
        @rtype: an L{IAddress} provider.
        """

    def getClientIP():
        """
        Return the IP address of the client who submitted this request.

        This method is B{deprecated}.  See L{getClientAddress} instead.

        @returns: the client IP address or L{None} if the request was submitted
            over a transport where IP addresses do not make sense.
        @rtype: L{str} or L{None}
        """

    def getUser():
        """
        Return the HTTP user sent with this request, if any.

        If no user was supplied, return the empty string.

        @returns: the HTTP user, if any
        @rtype: L{str}
        """

    def getPassword():
        """
        Return the HTTP password sent with this request, if any.

        If no password was supplied, return the empty string.

        @returns: the HTTP password, if any
        @rtype: L{str}
        """

    def isSecure():
        """
        Return True if this request is using a secure transport.

        Normally this method returns True if this request's HTTPChannel
        instance is using a transport that implements ISSLTransport.

        This will also return True if setHost() has been called
        with ssl=True.

        @returns: True if this request is secure
        @rtype: C{bool}
        """

    # Methods for outgoing response
    def finish():
        """
        Indicate that the response to this request is complete.
        """

    def write(data):
        """
        Write some data to the body of the response to this request.  Response
        headers are written the first time this method is called, after which
        new response headers may not be added.

        @param data: Bytes of the response body.
        @type data: L{bytes}
        """

    def addCookie(
        k,
        v,
        expires=None,
        domain=None,
        path=None,
        max_age=None,
        comment=None,
        secure=None,
    ):
        """
        Set an outgoing HTTP cookie.

        In general, you should consider using sessions instead of cookies, see
        L{twisted.web.server.Request.getSession} and the
        L{twisted.web.server.Session} class for details.
        """

    def setResponseCode(code, message=None):
        """
        Set the HTTP response code.

        @type code: L{int}
        @type message: L{bytes}
        """

    def setHeader(k, v):
        """
        Set an HTTP response header.  Overrides any previously set values for
        this header.

        @type k: L{bytes} or L{str}
        @param k: The name of the header for which to set the value.

        @type v: L{bytes} or L{str}
        @param v: The value to set for the named header. A L{str} will be
            UTF-8 encoded, which may not interoperable with other
            implementations. Avoid passing non-ASCII characters if possible.
        """

    def redirect(url):
        """
        Utility function that does a redirect.

        The request should have finish() called after this.
        """

    def setLastModified(when):
        """
        Set the C{Last-Modified} time for the response to this request.

        If I am called more than once, I ignore attempts to set Last-Modified
        earlier, only replacing the Last-Modified time if it is to a later
        value.

        If I am a conditional request, I may modify my response code to
        L{NOT_MODIFIED<http.NOT_MODIFIED>} if appropriate for the time given.

        @param when: The last time the resource being returned was modified, in
            seconds since the epoch.
        @type when: L{int} or L{float}

        @return: If I am a C{If-Modified-Since} conditional request and the time
            given is not newer than the condition, I return
            L{CACHED<http.CACHED>} to indicate that you should write no body.
            Otherwise, I return a false value.
        """

    def setETag(etag):
        """
        Set an C{entity tag} for the outgoing response.

        That's "entity tag" as in the HTTP/1.1 I{ETag} header, "used for
        comparing two or more entities from the same requested resource."

        If I am a conditional request, I may modify my response code to
        L{NOT_MODIFIED<http.NOT_MODIFIED>} or
        L{PRECONDITION_FAILED<http.PRECONDITION_FAILED>}, if appropriate for the
        tag given.

        @param etag: The entity tag for the resource being returned.
        @type etag: L{str}

        @return: If I am a C{If-None-Match} conditional request and the tag
            matches one in the request, I return L{CACHED<http.CACHED>} to
            indicate that you should write no body.  Otherwise, I return a
            false value.
        """

    def setHost(host, port, ssl=0):
        """
        Change the host and port the request thinks it's using.

        This method is useful for working with reverse HTTP proxies (e.g.  both
        Squid and Apache's mod_proxy can do this), when the address the HTTP
        client is using is different than the one we're listening on.

        For example, Apache may be listening on https://www.example.com, and
        then forwarding requests to http://localhost:8080, but we don't want
        HTML produced by Twisted to say 'http://localhost:8080', they should
        say 'https://www.example.com', so we do::

           request.setHost('www.example.com', 443, ssl=1)
        """

    def notifyFinish() -> Deferred[None]:
        """
        Notify when the response to this request has finished.

        @note: There are some caveats around the reliability of the delivery of
            this notification.

                1. If this L{Request}'s channel is paused, the notification
                   will not be delivered.  This can happen in one of two ways;
                   either you can call C{request.transport.pauseProducing}
                   yourself, or,

                2. In order to deliver this notification promptly when a client
                   disconnects, the reactor must continue reading from the
                   transport, so that it can tell when the underlying network
                   connection has gone away.  Twisted Web will only keep
                   reading up until a finite (small) maximum buffer size before
                   it gives up and pauses the transport itself.  If this
                   occurs, you will not discover that the connection has gone
                   away until a timeout fires or until the application attempts
                   to send some data via L{Request.write}.

                3. It is theoretically impossible to distinguish between
                   successfully I{sending} a response and the peer successfully
                   I{receiving} it.  There are several networking edge cases
                   where the L{Deferred}s returned by C{notifyFinish} will
                   indicate success, but the data will never be received.
                   There are also edge cases where the connection will appear
                   to fail, but in reality the response was delivered.  As a
                   result, the information provided by the result of the
                   L{Deferred}s returned by this method should be treated as a
                   guess; do not make critical decisions in your applications
                   based upon it.

        @return: A L{Deferred} which will be triggered when the request is
            finished -- with a L{None} value if the request finishes
            successfully or with an error if the request is interrupted by an
            error (for example, the client closing the connection prematurely).
        """


class IRequest(IMinimalRequest):
    """
    The expanded request interface used by L{twisted.web.server} that includes
    elements for resource hierarchy traversal and session management.

    @since: Twisted 9.0
    """

    prepath = Attribute(
        "The URL path segments which have been processed during resource "
        "traversal, as a list of L{bytes}."
    )

    postpath = Attribute(
        "The URL path segments which have not (yet) been processed "
        "during resource traversal, as a list of L{bytes}."
    )

    def URLPath():
        """
        @return: A L{URLPath<twisted.python.urlpath.URLPath>} instance
            which identifies the URL for which this request is.
        """

    def getRootURL():
        """
        Get a previously-remembered URL.

        @return: An absolute URL.
        @rtype: L{bytes}
        """

    def getSession(sessionInterface=None):
        """
        Look up the session associated with this request or create a new one if
        there is not one.

        @return: The L{Session} instance identified by the session cookie in
            the request, or the C{sessionInterface} component of that session
            if C{sessionInterface} is specified.
        """

    def rememberRootURL():
        """
        Remember the currently-processed part of the URL for later
        recalling.
        """

    def prePathURL():
        """
        At any time during resource traversal or resource rendering,
        returns an absolute URL to the most nested resource which has
        yet been reached.

        @see: {twisted.web.server.Request.prepath}

        @return: An absolute URL.
        @rtype: L{bytes}
        """


class IAccessLogFormatter(Interface):
    """
    An object which can represent an HTTP request as a line of text for
    inclusion in an access log file.
    """

    def __call__(timestamp, request):
        """
        Generate a line for the access log.

        @param timestamp: The time at which the request was completed in the
            standard format for access logs.
        @type timestamp: L{unicode}

        @param request: The request object about which to log.
        @type request: L{twisted.web.server.Request}

        @return: One line describing the request without a trailing newline.
        @rtype: L{unicode}
        """


class ICredentialFactory(Interface):
    """
    A credential factory defines a way to generate a particular kind of
    authentication challenge and a way to interpret the responses to these
    challenges.  It creates
    L{ICredentials<twisted.cred.credentials.ICredentials>} providers from
    responses.  These objects will be used with L{twisted.cred} to authenticate
    an authorize requests.
    """

    scheme = Attribute(
        "A L{str} giving the name of the authentication scheme with which "
        "this factory is associated.  For example, C{'basic'} or C{'digest'}."
    )

    def getChallenge(request):
        """
        Generate a new challenge to be sent to a client.

        @type request: L{twisted.web.http.Request}
        @param request: The request the response to which this challenge will
            be included.

        @rtype: L{dict}
        @return: A mapping from L{str} challenge fields to associated L{str}
            values.
        """

    def decode(response, request):
        """
        Create a credentials object from the given response.

        @type response: L{str}
        @param response: scheme specific response string

        @type request: L{twisted.web.http.Request}
        @param request: The request being processed (from which the response
            was taken).

        @raise twisted.cred.error.LoginFailed: If the response is invalid.

        @rtype: L{twisted.cred.credentials.ICredentials} provider
        @return: The credentials represented by the given response.
        """


class IBodyProducer(IPushProducer):
    """
    Objects which provide L{IBodyProducer} write bytes to an object which
    provides L{IConsumer<twisted.internet.interfaces.IConsumer>} by calling its
    C{write} method repeatedly.

    L{IBodyProducer} providers may start producing as soon as they have an
    L{IConsumer<twisted.internet.interfaces.IConsumer>} provider.  That is, they
    should not wait for a C{resumeProducing} call to begin writing data.

    L{IConsumer.unregisterProducer<twisted.internet.interfaces.IConsumer.unregisterProducer>}
    must not be called.  Instead, the
    L{Deferred<twisted.internet.defer.Deferred>} returned from C{startProducing}
    must be fired when all bytes have been written.

    L{IConsumer.write<twisted.internet.interfaces.IConsumer.write>} may
    synchronously invoke any of C{pauseProducing}, C{resumeProducing}, or
    C{stopProducing}.  These methods must be implemented with this in mind.

    @since: 9.0
    """

    # Despite the restrictions above and the additional requirements of
    # stopProducing documented below, this interface still needs to be an
    # IPushProducer subclass.  Providers of it will be passed to IConsumer
    # providers which only know about IPushProducer and IPullProducer, not
    # about this interface.  This interface needs to remain close enough to one
    # of those interfaces for consumers to work with it.

    length = Attribute(
        """
        C{length} is a L{int} indicating how many bytes in total this
        L{IBodyProducer} will write to the consumer or L{UNKNOWN_LENGTH}
        if this is not known in advance.
        """
    )

    def startProducing(consumer):
        """
        Start producing to the given
        L{IConsumer<twisted.internet.interfaces.IConsumer>} provider.

        @return: A L{Deferred<twisted.internet.defer.Deferred>} which stops
            production of data when L{Deferred.cancel} is called, and which
            fires with L{None} when all bytes have been produced or with a
            L{Failure<twisted.python.failure.Failure>} if there is any problem
            before all bytes have been produced.
        """

    def stopProducing():
        """
        In addition to the standard behavior of
        L{IProducer.stopProducing<twisted.internet.interfaces.IProducer.stopProducing>}
        (stop producing data), make sure the
        L{Deferred<twisted.internet.defer.Deferred>} returned by
        C{startProducing} is never fired.
        """


class IRenderable(Interface):
    """
    An L{IRenderable} is an object that may be rendered by the
    L{twisted.web.template} templating system.
    """

    def lookupRenderMethod(
        name: str,
    ) -> Callable[[IRequest | None, Tag], Flattenable]:
        """
        Look up and return the render method associated with the given name.

        @param name: The value of a render directive encountered in the
            document returned by a call to L{IRenderable.render}.

        @return: A two-argument callable which will be invoked with the request
            being responded to and the tag object on which the render directive
            was encountered.
        """

    def render(request: IRequest | None) -> Flattenable:
        """
        Get the document for this L{IRenderable}.

        @param request: The request in response to which this method is being
            invoked.

        @return: An object which can be flattened.
        """


class ITemplateLoader(Interface):
    """
    A loader for templates; something usable as a value for
    L{twisted.web.template.Element}'s C{loader} attribute.
    """

    def load() -> list[Flattenable]:
        """
        Load a template suitable for rendering.

        @return: a L{list} of flattenable objects, such as byte and unicode
            strings, L{twisted.web.template.Element}s and L{IRenderable} providers.
        """


class IResponse(Interface):
    """
    An object representing an HTTP response received from an HTTP server.

    @since: 11.1
    """

    version = Attribute(
        "A three-tuple describing the protocol and protocol version "
        "of the response.  The first element is of type L{str}, the second "
        "and third are of type L{int}.  For example, C{(b'HTTP', 1, 1)}."
    )

    code = Attribute("The HTTP status code of this response, as a L{int}.")

    phrase = Attribute("The HTTP reason phrase of this response, as a L{str}.")

    headers = Attribute("The HTTP response L{Headers} of this response.")

    length = Attribute(
        "The L{int} number of bytes expected to be in the body of this "
        "response or L{UNKNOWN_LENGTH} if the server did not indicate how "
        "many bytes to expect.  For I{HEAD} responses, this will be 0; if "
        "the response includes a I{Content-Length} header, it will be "
        "available in C{headers}."
    )

    request = Attribute("The L{IClientRequest} that resulted in this response.")

    previousResponse = Attribute(
        "The previous L{IResponse} from a redirect, or L{None} if there was no "
        "previous response. This can be used to walk the response or request "
        "history for redirections."
    )

    def deliverBody(protocol):
        """
        Register an L{IProtocol<twisted.internet.interfaces.IProtocol>} provider
        to receive the response body.

        The protocol will be connected to a transport which provides
        L{IPushProducer}.  The protocol's C{connectionLost} method will be
        called with:

            - L{ResponseDone}, which indicates that all bytes from the response
              have been successfully delivered.

            - L{PotentialDataLoss}, which indicates that it cannot be determined
              if the entire response body has been delivered.  This only occurs
              when making requests to HTTP servers which do not set
              I{Content-Length} or a I{Transfer-Encoding} in the response.

            - L{ResponseFailed}, which indicates that some bytes from the response
              were lost.  The C{reasons} attribute of the exception may provide
              more specific indications as to why.
        """

    def setPreviousResponse(response):
        """
        Set the reference to the previous L{IResponse}.

        The value of the previous response can be read via
        L{IResponse.previousResponse}.
        """


class _IRequestEncoder(Interface):
    """
    An object encoding data passed to L{IRequest.write}, for example for
    compression purpose.

    @since: 12.3
    """

    def encode(data):
        """
        Encode the data given and return the result.

        @param data: The content to encode.
        @type data: L{str}

        @return: The encoded data.
        @rtype: L{str}
        """

    def finish():
        """
        Callback called when the request is closing.

        @return: If necessary, the pending data accumulated from previous
            C{encode} calls.
        @rtype: L{str}
        """


class _IRequestEncoderFactory(Interface):
    """
    A factory for returing L{_IRequestEncoder} instances.

    @since: 12.3
    """

    def encoderForRequest(request):
        """
        If applicable, returns a L{_IRequestEncoder} instance which will encode
        the request.
        """


class IClientRequest(Interface):
    """
    An object representing an HTTP request to make to an HTTP server.

    @since: 13.1
    """

    method = Attribute(
        "The HTTP method for this request, as L{bytes}. For example: "
        "C{b'GET'}, C{b'HEAD'}, C{b'POST'}, etc."
    )

    absoluteURI = Attribute(
        "The absolute URI of the requested resource, as L{bytes}; or L{None} "
        "if the absolute URI cannot be determined."
    )

    headers = Attribute(
        "Headers to be sent to the server, as "
        "a L{twisted.web.http_headers.Headers} instance."
    )


class IAgent(Interface):
    """
    An agent makes HTTP requests.

    The way in which requests are issued is left up to each implementation.
    Some may issue them directly to the server indicated by the net location
    portion of the request URL.  Others may use a proxy specified by system
    configuration.

    Processing of responses is also left very widely specified.  An
    implementation may perform no special handling of responses, or it may
    implement redirect following or content negotiation, it may implement a
    cookie store or automatically respond to authentication challenges.  It may
    implement many other unforeseen behaviors as well.

    It is also intended that L{IAgent} implementations be composable.  An
    implementation which provides cookie handling features should re-use an
    implementation that provides connection pooling and this combination could
    be used by an implementation which adds content negotiation functionality.
    Some implementations will be completely self-contained, such as those which
    actually perform the network operations to send and receive requests, but
    most or all other implementations should implement a small number of new
    features (perhaps one new feature) and delegate the rest of the
    request/response machinery to another implementation.

    This allows for great flexibility in the behavior an L{IAgent} will
    provide.  For example, an L{IAgent} with web browser-like behavior could be
    obtained by combining a number of (hypothetical) implementations::

        baseAgent = Agent(reactor)
        decode = ContentDecoderAgent(baseAgent, [(b"gzip", GzipDecoder())])
        cookie = CookieAgent(decode, diskStore.cookie)
        authenticate = AuthenticateAgent(
            cookie, [diskStore.credentials, GtkAuthInterface()])
        cache = CacheAgent(authenticate, diskStore.cache)
        redirect = BrowserLikeRedirectAgent(cache, limit=10)

        doSomeRequests(cache)
    """

    if not TYPE_CHECKING:  # pragma: no branch

        def __init__(self) -> None:  # type:ignore
            """
            IAgent does not have any particular requirement upon its
            constructor.
            """
            # This is a workaround for pydoctor bug
            # https://github.com/twisted/pydoctor/issues/940

        del __init__

    def request(
        method: bytes,
        uri: bytes,
        headers: Headers | None = None,
        bodyProducer: IBodyProducer | None = None,
    ) -> Deferred[IResponse]:
        """
        Request the resource at the given location.

        @param method: The request method to use, such as C{b"GET"}, C{b"HEAD"},
            C{b"PUT"}, C{b"POST"}, etc.

        @param uri: The location of the resource to request.  This should be an
            absolute URI but some implementations may support relative URIs
            (with absolute or relative paths).  I{HTTP} and I{HTTPS} are the
            schemes most likely to be supported but others may be as well.

        @param headers: The headers to send with the request (or L{None} to
            send no extra headers).  An implementation may add its own headers
            to this (for example for client identification or content
            negotiation).

        @param bodyProducer: An object which can generate bytes to make up the
            body of this request (for example, the properly encoded contents of
            a file for a file upload).  Or, L{None} if the request is to have
            no body.

        @return: A L{Deferred} that fires with an L{IResponse} provider when
            the header of the response has been received (regardless of the
            response status code) or with a L{Failure} if there is any problem
            which prevents that response from being received (including
            problems that prevent the request from being sent).
        """


class IPolicyForHTTPS(Interface):
    """
    An L{IPolicyForHTTPS} provides a policy for verifying the certificates of
    HTTPS connections, in the form of a L{client connection creator
    <twisted.internet.interfaces.IOpenSSLClientConnectionCreator>} per network
    location.

    @since: 14.0
    """

    def creatorForNetloc(hostname: bytes, port: int) -> IOpenSSLClientConnectionCreator:
        """
        Create a L{client connection creator
        <twisted.internet.interfaces.IOpenSSLClientConnectionCreator>}
        appropriate for the given URL "netloc"; i.e. hostname and port number
        pair.

        @param hostname: The name of the requested remote host.

        @param port: The number of the requested remote port.

        @return: A client connection creator expressing the security
            requirements for the given remote host.
        """


class IAgentEndpointFactory(Interface):
    """
    An L{IAgentEndpointFactory} provides a way of constructing an endpoint
    used for outgoing Agent requests. This is useful in the case of needing to
    proxy outgoing connections, or to otherwise vary the transport used.

    @since: 15.0
    """

    def endpointForURI(uri):
        """
        Construct and return an L{IStreamClientEndpoint} for the outgoing
        request's connection.

        @param uri: The URI of the request.
        @type uri: L{twisted.web.client.URI}

        @return: An endpoint which will have its C{connect} method called to
            issue the request.
        @rtype: an L{IStreamClientEndpoint} provider

        @raises twisted.internet.error.SchemeNotSupported: If the given
            URI's scheme cannot be handled by this factory.
        """


class ChannelDefinition(TypingProtocol):
    """
    An HTTP channel is the transport for an individual HTTP request, which
    might be an HTTP/1.1 TCP connection, or an HTTP/2 stream.  This protocol
    defines the methods which Twisted's HTTP implementation will expect of a
    channel.

    @note: Some of the methods on this protocol are private, and thus any
        implementations outside of Twisted may stop working as those methods
        change.
    """

    @property
    def transport(self) -> ITransport | None:
        """
        The underlying transport, or nothing.

        @note: In HTTP/2 this is always C{None}; it is exposed for
            compatibility and should be removed in a future version.
        """

    def requestDone(self, request: _IChannelRequest) -> None:
        """¬
        The request has completed and should no longer own the channel.
        """

    def _respondToBadRequestAndDisconnect(self) -> None:
        """
        Immediately issue an HTTP 400 response and disconnect the underlying
        transport.
        """

    def registerProducer(self, producer: IProducer, streaming: bool) -> None:
        """
        Allow registering a producer with the underlying transport for
        flow-control purposes, the same as L{twisted.internet.interfaced.IConsumer}.
        """

    def unregisterProducer(self) -> None:
        """
        Unregister the current producer from the underlying transport.
        """

    def write(self, data: bytes) -> None:
        """
        Write some data to the body of the response.
        """

    def writeSequence(self, data: Sequence[bytes]) -> None:
        """
        Write a sequence of data to the body of the response.
        """

    def writeHeaders(
        self, version: bytes, code: bytes, reason: bytes, headers: Headers
    ) -> None:
        """
        The headers are fully constructed; write them to the transport.

        @param version: The HTTP version in use.

        @param code: The HTTP status code to write, already encoded as bytes.

        @param reason: The HTTP reason phrase to write.

        @param headers: The headers to write to the transport.
        """

    def loseConnection(self) -> None:
        """
        Drop the connection to the underlying transport.
        """

    def getPeer(self) -> IAddress:
        """
        Get the address of the remote peer of the underlying transport.
        """

    def getHost(self) -> IAddress:
        """
        Get the address of the local host of the underlying transport.
        """

    def isSecure(self) -> bool:
        """
        Is this channel currently secured using transport-layer security?
        """


class _LegacyQueuedRequestFactory(TypingProtocol):
    """
    A callable that produces a request object from a given channel, while
    taking a now-unused 'queued' parameter.
    """

    def __call__(self, channel: ChannelDefinition, queued: bool) -> _IChannelRequest:
        """
        Create an L{IRequest} that is operating on the given channel.  There
        must only be one L{IRequest} object processing at any given time on a
        channel.

        @param channel: The channel for the request.

        @return: A request object.
        """


class INonQueuedRequestFactory(Interface):
    """
    A factory of L{IRequest} objects that does not take the now-unused
    ``queued`` parameter from legacy versions of Twisted.
    """

    def __call__(channel: ChannelDefinition) -> _IChannelRequest:
        """
        @see: L{RequestFactory}

        @param channel: The channel for the request.

        @return: A request object.
        """


_SomeRequestFactory = INonQueuedRequestFactory | _LegacyQueuedRequestFactory


def _invokeSomeRequestFactory(
    some: _SomeRequestFactory, channel: ChannelDefinition
) -> _IChannelRequest:
    """
    Manage legacy compatibility with queued versus non-queued request factory,
    by invoking the given callable with the right number of arguments.
    """
    if INonQueuedRequestFactory.providedBy(some):
        return some(channel)
    else:
        return some(channel, False)


UNKNOWN_LENGTH = "twisted.web.iweb.UNKNOWN_LENGTH"

__all__ = [
    "IUsernameDigestHash",
    "ICredentialFactory",
    "IRequest",
    "IBodyProducer",
    "IRenderable",
    "IResponse",
    "_IRequestEncoder",
    "_IRequestEncoderFactory",
    "IClientRequest",
    "UNKNOWN_LENGTH",
]
