# Twisted, the Framework of Your Internet
# Copyright (C) 2001 Matthew W. Lefkowitz
# 
# This library is free software; you can redistribute it and/or
# modify it under the terms of version 2.1 of the GNU Lesser General Public
# License as published by the Free Software Foundation.
# 
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
# 
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

"""Simplistic HTTP proxy support.

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

# twisted imports
from twisted.protocols import http
from twisted.internet import reactor, protocol
from twisted.web import resource, server

# system imports
import urlparse


class ProxyClient(http.HTTPClient):
    """Used by ProxyClientFactory to implement a simple web proxy."""

    def __init__(self, command, rest, version, headers, data, father):
        self.father = father
        self.command = command
        self.rest = rest
        if headers.has_key("proxy-connection"):
            del headers["proxy-connection"]
        headers["connection"] = "close"
        self.headers = headers
        self.data = data

    def connectionMade(self):
        self.sendCommand(self.command, self.rest)
        for header, value in self.headers.items():
            self.sendHeader(header, value)
        self.endHeaders()
        self.transport.write(self.data)

    def handleStatus(self, version, code, message):
        self.father.transport.write("%s %s %s\r\n" % (version, code, message))

    def handleHeader(self, key, value):
        self.father.transport.write("%s: %s\r\n" % (key, value))

    def handleEndHeaders(self):
        self.father.transport.write("\r\n")
    
    def handleResponsePart(self, buffer):
        self.father.transport.write(buffer)

    def handleResponseEnd(self):
        self.transport.loseConnection()
        self.father.channel.transport.loseConnection()


class ProxyClientFactory(protocol.ClientFactory):
    """Used by ProxyRequest to implement a simple web proxy."""

    def __init__(self, command, rest, version, headers, data, father):
        self.father = father
        self.command = command
        self.rest = rest
        self.headers = headers
        self.data = data
        self.version = version


    def buildProtocol(self, addr):
        return ProxyClient(self.command, self.rest, self.version,
                           self.headers, self.data, self.father)


    def clientConnectionFailed(self, connector, reason):
        self.father.transport.write("HTTP/1.0 501 Gateway error\r\n")
        self.father.transport.write("Content-Type: text/html\r\n")
        self.father.transport.write("\r\n")
        self.father.transport.write('''<H1>Could not connect</H1>''')



class ProxyRequest(http.Request):
    """Used by Proxy to implement a simple web proxy."""

    protocols = {'http': ProxyClientFactory}
    ports = {'http': 80}

    def process(self):
        parsed = urlparse.urlparse(self.uri)
        protocol = parsed[0]
        host = parsed[1]
        port = self.ports[protocol]
        if ':' in host:
            host, port = host.split(':')
            port = int(port)
        rest = urlparse.urlunparse(('','')+parsed[2:])
        if not rest:
            rest = rest+'/'
        class_ = self.protocols[protocol]
        headers = self.getAllHeaders().copy()
        if not headers.has_key('host'):
            headers['host'] = host
        self.content.seek(0, 0)
        s = self.content.read()
        clientFactory = class_(self.method, rest, self.clientproto, headers,
                               s, self)
        reactor.connectTCP(host, port, clientFactory)


class Proxy(http.HTTPChannel):
    """This class implements a simple web proxy.

    Since it inherits from twisted.protocols.http.HTTPChannel, to use it you
    should do something like this::

        from twisted.protocols import http
        f = http.HTTPFactory()
        f.protocol = Proxy

    Make the HTTPFactory a listener on a port as per usual, and you have
    a fully-functioning web proxy!
    """

    requestFactory = ProxyRequest


class ReverseProxyRequest(http.Request):
    """Used by ReverseProxy to implement a simple reverse proxy."""

    def process(self):
        self.received_headers['host'] = self.factory.host
        clientFactory = ProxyClientFactory(self.method, self.uri,
                                            self.clientproto,
                                            self.getAllHeaders(), 
                                            self.content.read(), self)
        reactor.connectTCP(self.factory.host, self.factory.port,
                           clientFactory)

class ReverseProxy(http.HTTPChannel):
    """Implements a simple reverse proxy.

    For details of usage, see the file examples/proxy.py"""

    requestFactory = ReverseProxyRequest


class ReverseProxyResource(resource.Resource):
    """Resource that renders the results gotten from another server

    Put this resource in the tree to cause everything below it to be relayed
    to a different server.
    """

    def __init__(self, host, port, path):
        resource.Resource.__init__(self)
        self.host = host
        self.port = port
        self.path = path

    def getChild(self, path, request):
        return ReverseProxyResource(self.host, self.port, self.path+'/'+path)

    def render(self, request):
        request.received_headers['host'] = self.host
        request.content.seek(0, 0)
        qs = urlparse.urlparse(request.uri)[4]
        if qs:
            rest = self.path + '?' + qs
        else:
            rest = self.path
        clientFactory = ProxyClientFactory(request.method, rest, 
                                     request.clientproto, 
                                     request.getAllHeaders(),
                                     request.content.read(),
                                     request)
        reactor.connectTCP(self.host, self.port, clientFactory)
        return server.NOT_DONE_YET
