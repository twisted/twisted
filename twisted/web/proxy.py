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
from twisted.protocols import http
from twisted.internet import tcp
from twisted.web import resource, server
import urlparse


class ProxyClient(http.HTTPClient):

    def __init__(self, command, rest, version, headers, data, father):
        self.father = father
        self.command = command
        self.rest = rest
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

    def handleResponse(self, buffer):
        self.father.transport.write(buffer)
        self.transport.loseConnection()
        self.father.transport.loseConnection()


class Proxy(http.HTTP):

    protocols = {'http': ProxyClient}
    ports = {'http': 80}

    def requestReceived(self, command, path, version, data):
        parsed = urlparse.urlparse(path)
        protocol = parsed[0]
        host = parsed[1]
        port = self.ports[protocol]
        if ':' in host:
            host, port = string.split(host, ':')
        rest = urlparse.urlunparse(('','')+parsed[2:])
        if not rest:
            rest = rest+'/'
        class_ = self.protocols[protocol]
        if not self.received.has_key('host'):
            self.received['host'] = host
        clientProtocol = class_(command, rest, version, self.received, data, 
                                self)
        client = tcp.Client(host, port, clientProtocol)


class ReverseProxy(http.HTTP):

    def requestReceived(self, command, path, version, data):
        self.received['host'] = self.factory.host
        clientProtocol = ProxyClient(command, path, version, self.received, 
                                     data, self)
        client = tcp.Client(self.factory.host, self.factory.port,
                            clientProtocol)


class ReverseProxyResource(resource.Resource):
    def __init__(self, host, port, path):
        resource.Resource.__init__(self)
        self.host = host
        self.port = port
        self.path = path

    def getChild(self, path, request):
        return ReverseProxyResource(self.host, self.port, self.path+'/'+path)

    def render(self, request):
        request.received['host'] = self.host
        clientProtocol = ProxyClient(request.method, self.path, 
                                     request.clientproto, 
                                     request.getAllHeaders(), request.content,
                                     request)
        client = tcp.Client(self.host, self.port, clientProtocol)
        return server.NOT_DONE_YET
