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
from twisted.protocols import http
from twisted.internet import defer, protocol, reactor
from twisted.python import failure
import urlparse

class HTTPPageGetter(http.HTTPClient):

    def connectionMade(self):
        self.sendCommand('GET', self.factory.url)
        self.sendHeader('Host', self.factory.host)
        self.sendHeader('User-Agent', self.factory.agent)
        self.endHeaders()

    def handleStatus(self, version, status, message):
        if status != '200':
            self.factory.noPage(failure.Failure(ValueError(status, message)))
            self.transport.loseConnection()

    def connectionLost(self, reason):
        http.HTTPClient.connectionLost(self, reason)
        self.factory.noPage(reason)

    def handleResponse(self, response):
        self.factory.page(response)


class HTTPPageDownloader(HTTPPageGetter):

    def handleEndHeaders(self):
        self.factory.pageStart()

    def handleResponsePart(self, data):
        self.factory.pagePart(data)

    def handleResponseEnd(self):
        self.factory.pageEnd()


class HTTPClientFactory(protocol.ClientFactory):

    protocol = HTTPPageGetter

    def __init__(self, host, url, agent="Twisted PageGetter"):
        self.host=host
        self.url=url
        self.agent=agent
        self.waiting = 1
        self.deferred = defer.Deferred()

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

    protocol = HTTPPageDownloader

    def __init__(self, host, url, fileName, agent="Twisted client"):
        self.host = host
        self.url = url
        self.fileName = fileName
        self.agent = agent
        self.deferred = defer.Deferred()
        self.waiting = 1
        self.file = None

    def pageStart(self):
        if self.waiting:
            self.waiting = 0
            self.file = open(self.fileName, 'w')

    def pageEnd(self):
        if self.file:
            self.file.close()
        self.deferred.callback(None)

    def pagePart(self, data):
        if self.file:
            self.file.write(data)

    
def _parse(url):
    parsed = urlparse.urlparse(url)
    url = urlparse.urlunparse(('','')+parsed[2:])
    host, port = parsed[1], 80
    if ':' in host:
        host, port = host.split(':')
        port = int(port)
    return host, port, url

def getPage(url):
    '''download a web page

    Download a page. Return a deferred, which will
    callback with a page or errback with a description
    of the error.
    '''
    host, port, url = _parse(url)
    factory = HTTPClientFactory(host, url)
    reactor.connectTCP(host, port, factory)
    return factory.deferred

def downloadPage(url, file):
    host, port, url = _parse(url)
    factory = HTTPDownloader(host, url, file)
    reactor.connectTCP(host, port, factory)
    return factory.deferred

if __name__ == '__main__':
    d = getPage('http://moshez.org/links.html')
    def printValue(value):
        print value
        reactor.stop()
    def printError(error):
        print "an error occured"
        reactor.stop()
    d.addCallbacks(callback=printValue, errback=printError)
    reactor.run()
