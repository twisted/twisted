# -*- test-case-name: twisted.test.test_webclient -*-

# Twisted, the Framework of Your Internet
# Copyright (C) 2001-2002 Matthew W. Lefkowitz
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
#

"""HTTP client."""

from twisted.protocols import http
from twisted.internet import defer, protocol, reactor
from twisted.python import failure
from twisted.web import error
import urlparse, os


class HTTPPageGetter(http.HTTPClient):

    quietLoss = 0
    
    failed = 0

    def connectionMade(self):
        method = getattr(self.factory, 'method', 'GET')
        self.sendCommand(method, self.factory.url)
        self.sendHeader('Host', self.factory.host)
        self.sendHeader('User-Agent', self.factory.agent)
        for cookie, cookval in self.factory.cookies.items():
            self.sendHeader('Cookie', '%s=%s' % (cookie, cookval))
        for (key, value) in self.factory.headers.items():
            self.sendHeader(key, value)
        self.endHeaders()
        self.headers = {}
        data = getattr(self.factory, 'postdata', None)
        if data is not None:
            self.transport.write(data)

    def handleHeader(self, key, value):
        key = key.lower()
        l = self.headers[key] = self.headers.get(key, [])
        l.append(value)

    def handleStatus(self, version, status, message):
        self.version, self.status, self.message = version, status, message

    def handleEndHeaders(self):
        self.factory.gotHeaders(self.headers)
        m = getattr(self, 'handleStatus_'+self.status, self.handleStatusDefault)
        m()

    def handleStatus_200(self):
        pass

    handleStatus_202 = lambda self: self.handleStatus_200()

    def handleStatusDefault(self):
        self.failed = 1

    def handleStatus_301(self):
        l = self.headers.get('location')
        if not l:
            self.handleStatusDefault()
        host, port, url = _parse(l[0], defaultPort=self.transport.addr[1])
        # if it's a relative redirect, e.g., /foo, then host==''
        if host:
            self.factory.host = host
        self.factory.port = port
        self.factory.url = url

        reactor.connectTCP(self.factory.host, self.factory.port, self.factory)
        self.quietLoss = 1
        self.transport.loseConnection()

    handleStatus_302 = lambda self: self.handleStatus_301()

    def connectionLost(self, reason):
        if not self.quietLoss:
            http.HTTPClient.connectionLost(self, reason)
            self.factory.noPage(reason)

    def handleResponse(self, response):
        if self.failed:
            self.factory.noPage(
                failure.Failure(
                    error.Error(
                        self.status, self.message, response)))
            self.transport.loseConnection()
        else:
            self.factory.page(response)

    def timeout(self):
        self.quietLoss = True
        self.transport.loseConnection()
        self.factory.noPage(defer.TimeoutError("Getting %s took longer than %s seconds." % (self.factory.url, self.factory.timeout)))


class HTTPPageDownloader(HTTPPageGetter):

    transmittingPage = 0

    def handleStatus_200(self, partialContent=0):
        HTTPPageGetter.handleStatus_200(self)
        self.transmittingPage = 1
        self.factory.pageStart(partialContent)

    def handleStatus_206(self):
        self.handleStatus_200(partialContent=1)
    
    def handleResponsePart(self, data):
        if self.transmittingPage:
            self.factory.pagePart(data)

    def handleResponseEnd(self):
        if self.transmittingPage:
            self.factory.pageEnd()
            self.transmittingPage = 0


class HTTPClientFactory(protocol.ClientFactory):
    """Download a given URL."""

    protocol = HTTPPageGetter

    def __init__(self, host, url, method='GET', postdata=None, headers=None, agent="Twisted PageGetter", timeout=0):
        self.timeout = timeout
        self.agent = agent
        self.url = url

        self.cookies = {}
        if headers is not None:
            self.headers = headers
        else:
            self.headers = {}
        if postdata is not None:
            self.headers.setdefault('Content-Length', len(postdata))
        self.postdata = postdata
        self.method = method
        if ':' in host:
            self.host, self.port = host.split(':')
            self.port = int(self.port)
        else:
            self.host = host
            self.port = 80

        self.waiting = 1
        self.deferred = defer.Deferred()

    def buildProtocol(self, addr):
        p = protocol.ClientFactory.buildProtocol(self, addr)
        if self.timeout:
            reactor.callLater(self.timeout, p.timeout)
        return p

    def gotHeaders(self, headers):
        if headers.has_key('set-cookie'):
            for cookie in headers['set-cookie']:
                cookparts = cookie.split(';')
                for cook in cookparts:
                    cook.lstrip()
                    k, v = cook.split('=')
                    self.cookies[k.lstrip()] = v.lstrip()

    def page(self, page):
        if self.waiting:
            self.waiting = 0
            self.deferred.callback(page)

    def noPage(self, reason):
        if self.waiting:
            self.waiting = 0
            self.deferred.errback(reason)

    def clientConnectionFailed(self, _, reason):
        if self.waiting:
            self.waiting = 0
            self.deferred.errback(reason)


class HTTPDownloader(HTTPClientFactory):
    """Download to a file."""
    
    protocol = HTTPPageDownloader
    value = None

    def __init__(self, host, url, fileName, method='GET', postdata=None, headers=None,
                 agent="Twisted client", supportPartial=0):
        if supportPartial and os.path.exists(fileName):
            fileLength = os.path.getsize(fileName)
            if fileLength:
                self.requestedPartial = fileLength
                if headers == None:
                    headers = {}
                headers["range"] = "bytes=%d-" % fileLength
        else:
            self.requestedPartial = 0
        HTTPClientFactory.__init__(self, host, url, method=method, postdata=postdata, headers=headers, agent=agent)
        self.fileName = fileName
        self.deferred = defer.Deferred()
        self.waiting = 1
        self.file = None

    def gotHeaders(self, headers):
        if self.requestedPartial:
            contentRange = headers.get("content-range", None)
            if not contentRange:
                # server doesn't support partial requests, oh well
                self.requestedPartial = 0 
                return
            start, end, realLength = http.parseContentRange(contentRange[0])
            if start != self.requestedPartial:
                # server is acting wierdly
                self.requestedPartial = 0
    
    def pageStart(self, partialContent):
        """Called on page download start.

        @param partialContent: tells us if the download is partial download we requested.
        """
        if partialContent and not self.requestedPartial:
            raise ValueError, "we shouldn't get partial content response if we didn't want it!"
        if self.waiting:
            self.waiting = 0
            if partialContent:
                self.file = open(self.fileName, 'rb+')
                self.file.seek(0, 2)
            else:
                self.file = open(self.fileName, 'wb')

    def pageEnd(self):
        if self.file:
            self.file.close()
        self.deferred.callback(self.value)

    def pagePart(self, data):
        if self.file:
            self.file.write(data)


def _parse(url, defaultPort=80):
    parsed = urlparse.urlparse(url)
    url = urlparse.urlunparse(('','')+parsed[2:])
    host, port = parsed[1], defaultPort
    if ':' in host:
        host, port = host.split(':')
        port = int(port)
    return host, port, url

def getPage(url, *args, **kwargs):
    '''download a web page

    Download a page. Return a deferred, which will
    callback with a page or errback with a description
    of the error.
    '''
    host, port, url = _parse(url)
    factory = HTTPClientFactory(host, url, *args, **kwargs)
    reactor.connectTCP(host, port, factory)
    return factory.deferred

def downloadPage(url, file, *args, **kwargs):
    host, port, url = _parse(url)
    factory = HTTPDownloader(host, url, file, *args, **kwargs)
    reactor.connectTCP(host, port, factory)
    return factory.deferred
