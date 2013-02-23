# -*- test-case-name: twisted.web.test.test_proxy -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Simplistic HTTP proxy support.

This comes in two main variants - the Proxy and the ReverseProxy.

When a Proxy is in use, a browser trying to connect to a server (say,
www.yahoo.com) will be intercepted by the Proxy, and the proxy will covertly
connect to the server, and return the result.

When a ReverseProxy is in use, the client connects directly to the ReverseProxy
(say, www.yahoo.com) which farms off the request to one of a pool of servers,
and returns the result.

Normally, a Proxy is used on the client end of an Internet connection, while a
ReverseProxy is used on the server end.
"""

import urlparse
from urllib import quote as urlquote

from twisted.internet import reactor
from twisted.internet.protocol import ClientFactory
from twisted.web.resource import Resource
from twisted.web.server import NOT_DONE_YET
from twisted.web.http import HTTPClient, Request, HTTPChannel



class ProxyClient(HTTPClient):
    """
    Used by L{ProxyClientFactory} to implement a simple web proxy.

    @ivar _finished: A flag which indicates whether or not the original request
        has been finished yet.
    """
    _finished = False

    def __init__(self, command, rest, version, headers, data, father):
        """
        Usually created when L{ProxyClientFactory.buildProtocol} is called.
        The arguments passed to this constructor are the same as the ones
        passed to the L{ProxyClientFactory} constructor.

        @type command: C{str}
        @param command: HTTP Command (GET, POST, HEAD, etc)
        
        @type rest: C{str}
        @param rest: Rest of url other than host, ex. C{example.com/test.html}
            where C{/test.html} is the rest.
                     
        @type version: C{str}
        @param version: HTTP Version (HTTP/1.1, HTTP/1.0)
        
        @type headers: C{dict}
        @param headers: The headers that were specified in the request to
            (or through) the proxy server.
         
        @type data: C{str}
        @param data: Data sent to (or through) the server for example with a
            POST request.
               
        @type father: L{ProxyRequest}
        @param father: The server request first passed to the
            L{ProxyClientFactory} and then the L{ProxyClient} when
            C{buildProtocol} is called.
        """
        self.father = father
        self.command = command
        self.rest = rest
        if "proxy-connection" in headers:
            del headers["proxy-connection"]
        headers["connection"] = "close"
        headers.pop('keep-alive', None)
        self.headers = headers
        self.data = data


    def connectionMade(self):
        self.sendCommand(self.command, self.rest)
        for header, value in self.headers.items():
            self.sendHeader(header, value)
        self.endHeaders()
        self.transport.write(self.data)


    def handleStatus(self, version, code, message):
        """
        Handles the status sent from the remote server back to the client.
        Passes it onto the proxy server and then back to the user.

        @param version: HTTP Version (HTTP/1.1. HTTP/1.0)
        @type version: C{str}

        @param code: HTTP status code (200, 404, 403, etc)
        @type code: C{int}

        @param message: Message sent with the status.
        @type message: C{str}
        """
        self.father.setResponseCode(int(code), message)


    def handleHeader(self, key, value):
        """
        Handles a header sent from the remote server back to the client.

        Passes the header back to the proxy server and then back to the user.

        @type key: C{str}
        @param key: An HTTP header field name.

        @type value: C{str}
        @param value: An HTTP header field value.
        """

        # t.web.server.Request sets default values for these headers in its
        # 'process' method. When these headers are received from the remote
        # server, they ought to override the defaults, rather than append to
        # them.
        if key.lower() in ['server', 'date', 'content-type']:
            self.father.responseHeaders.setRawHeaders(key, [value])
        else:
            self.father.responseHeaders.addRawHeader(key, value)


    def handleResponsePart(self, buffer):
        """
        Handles some data received by the client.
        Writes the data back to the proxy server.
        
        @type buffer: C(str)
        @param buffer: The data that was received from the remote server.
        """
        self.father.write(buffer)


    def handleResponseEnd(self):
        """
        Handles the end of the connection to the remote server.

        Finish the original request, indicating that the response has been
        completely written to it, and disconnect the outgoing transport.
        """
        if not self._finished:
            self._finished = True
            self.father.finish()
            self.transport.loseConnection()



class ProxyClientFactory(ClientFactory):
    """
    Used by L{ProxyRequest} to implement a simple web proxy.
    """

    protocol = ProxyClient


    def __init__(self, command, rest, version, headers, data, father):
        """
        @type command: C{str}
        @param command: HTTP Command (GET, POST, HEAD, etc)
        
        @type rest: C{str}
        @param rest: Rest of url other than host, ex. C{example.com/test.html}
            C{/test.html} is the rest.
                     
        @type version: C{str}
        @param version: HTTP Version (HTTP/1.1, HTTP/1.0)
        
        @type headers: C{dict}
        @param headers: The headers that were specified in the request to
            (or through) the proxy server
         
        @type data: C{str}
        @param data: Data sent to (or through) the server for example with a
           POST requst
               
        @type father: L{ProxyRequest}
        @param father: The server request first passed to the
            L{ProxyClientFactory} and then the L{ProxyClient} when
            C{buildProtocol} is called.
        
        """
        self.father = father
        self.command = command
        self.rest = rest
        self.headers = headers
        self.data = data
        self.version = version


    def buildProtocol(self, addr):
        """
        Builds L{ProxyClient} and returns the protocol.
        """
        return self.protocol(self.command, self.rest, self.version,
                             self.headers, self.data, self.father)


    def clientConnectionFailed(self, connector, reason):
        """
        Report a connection failure in a response to the incoming request as
        an error.
        """
        self.father.setResponseCode(501, "Gateway error")
        self.father.responseHeaders.addRawHeader("Content-Type", "text/html")
        self.father.write("<H1>Could not connect</H1>")
        self.father.finish()



class ProxyRequest(Request):
    """
    Used by L{Proxy} to implement a simple web proxy.

    @ivar reactor: The reactor used to create connections.
    @type reactor: Object providing L{twisted.internet.interfaces.IReactorTCP}
    """

    protocols = {'http': ProxyClientFactory}
    ports = {'http': 80}

    def __init__(self, channel, queued, reactor=reactor):
        """
        Implements the proxy server's request handler.
        
        @type channel: L{Proxy}
        @param channel: Used as connection between your client and the proxy
            server.
        
        @type queued: C{bool}
        @param queued: Is the request queued or can we write to the transport
            now?
        
        @type reactor: L{twisted.internet.reactor}
        @param reactor: Needed here to connect the L{Proxy} client end to the
            remote server.
        """
        Request.__init__(self, channel, queued)
        self.reactor = reactor


    def process(self):
        """
        Called to process the request from your client.

        This method parses the url (to see what the proxy needs to go fetch) and 
        then connects to that url (just like if your program connect to example.com
        except the proxy server does it not your client directly) using the class 
        specified in protocols. 

        Overide if you want to control things such as headers and method sent to
        the remote server (for example if you want any GET request to change to a
        HEAD request)
        """
        parsed = urlparse.urlparse(self.uri)
        protocol = parsed[0]
        host = parsed[1]
        port = self.ports[protocol]
        if ':' in host:
            host, port = host.split(':')
            port = int(port)
        rest = urlparse.urlunparse(('', '') + parsed[2:])
        if not rest:
            rest = rest + '/'
        class_ = self.protocols[protocol]
        headers = self.getAllHeaders().copy()
        if 'host' not in headers:
            headers['host'] = host
        self.content.seek(0, 0)
        s = self.content.read()
        clientFactory = class_(self.method, rest, self.clientproto, headers,
                               s, self)
        self.reactor.connectTCP(host, port, clientFactory)



class Proxy(HTTPChannel):
    """
    This class implements a simple web proxy.

    Since it inherits from L{twisted.protocols.http.HTTPChannel}, to use it you
    should do something like this::

        from twisted.web import http
        f = http.HTTPFactory()
        f.protocol = Proxy

    Make the HTTPFactory a listener on a port as per usual, and you have
    a fully-functioning web proxy!

    The HTTP channel that your client and the proxy server communicate over.
    Subclasses HTTPChannel and just changes what request factory to use so
    instead of using one that say servers files you use C(ProxyRequest) to then
    connect to a remote host and serve that instead of boring files.

    """

    requestFactory = ProxyRequest



class ReverseProxyRequest(Request):
    """
    Used by L{ReverseProxy} to implement a simple reverse proxy.

    @ivar proxyClientFactoryClass: a proxy client factory class, used to create
        new connections.
    @type proxyClientFactoryClass: L{ClientFactory}

    @ivar reactor: The reactor used to create connections.
    @type reactor: Object providing L{twisted.internet.interfaces.IReactorTCP}
    """

    proxyClientFactoryClass = ProxyClientFactory

    def __init__(self, channel, queued, reactor=reactor):
        Request.__init__(self, channel, queued)
        self.reactor = reactor


    def process(self):
        """
        Handle this request by connecting to the proxied server and forwarding
        it there, then forwarding the response back as the response to this
        request.
        """
        self.received_headers['host'] = self.factory.host
        clientFactory = self.proxyClientFactoryClass(
            self.method, self.uri, self.clientproto, self.getAllHeaders(),
            self.content.read(), self)
        self.reactor.connectTCP(self.factory.host, self.factory.port,
                                clientFactory)



class ReverseProxy(HTTPChannel):
    """
    Implements a simple reverse proxy.

    For details of usage, see the file examples/proxy.py.
    """

    requestFactory = ReverseProxyRequest



class ReverseProxyResource(Resource):
    """
    Resource that renders the results gotten from another server

    Put this resource in the tree to cause everything below it to be relayed
    to a different server.

    @ivar proxyClientFactoryClass: a proxy client factory class, used to create
        new connections.
    @type proxyClientFactoryClass: L{ClientFactory}

    @ivar reactor: the reactor used to create connections.
    @type reactor: object providing L{twisted.internet.interfaces.IReactorTCP}
    """

    proxyClientFactoryClass = ProxyClientFactory


    def __init__(self, host, port, path, reactor=reactor):
        """
        @param host: the host of the web server to proxy.
        @type host: C{str}

        @param port: the port of the web server to proxy.
        @type port: C{port}

        @param path: the base path to fetch data from. Note that you shouldn't
            put any trailing slashes in it, it will be added automatically in
            request. For example, if you put B{/foo}, a request on B{/bar} will
            be proxied to B{/foo/bar}.  Any required encoding of special
            characters (such as " " or "/") should have been done already.

        @type path: C{str}
        """
        Resource.__init__(self)
        self.host = host
        self.port = port
        self.path = path
        self.reactor = reactor


    def getChild(self, path, request):
        """
        Create and return a proxy resource with the same proxy configuration
        as this one, except that its path also contains the segment given by
        C{path} at the end.
        """
        return ReverseProxyResource(
            self.host, self.port, self.path + '/' + urlquote(path, safe=""),
            self.reactor)


    def render(self, request):
        """
        Render a request by forwarding it to the proxied server.
        """
        # RFC 2616 tells us that we can omit the port if it's the default port,
        # but we have to provide it otherwise
        if self.port == 80:
            host = self.host
        else:
            host = "%s:%d" % (self.host, self.port)
        request.received_headers['host'] = host
        request.content.seek(0, 0)
        qs = urlparse.urlparse(request.uri)[4]
        if qs:
            rest = self.path + '?' + qs
        else:
            rest = self.path
        clientFactory = self.proxyClientFactoryClass(
            request.method, rest, request.clientproto,
            request.getAllHeaders(), request.content.read(), request)
        self.reactor.connectTCP(self.host, self.port, clientFactory)
        return NOT_DONE_YET

