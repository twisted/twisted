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
import htmllib, formatter, os, urlparse
from twisted.internet import app, reactor
from twisted.web import client

class DummyParser:

    anchorlist = []

    def feed(self, s):
        pass


class HTTPDownloader(client.HTTPDownloader):

    expectedLength = 0
    soFar = 0
    parser = DummyParser()

    def gotHeaders(self, headers):
        type = headers.get('content-type', [''])[0]
        if type.lower().startswith('text/html'):
            self.parser = htmllib.HTMLParser(formatter.NullFormatter())
        length = headers.get('content-length', [''])[0]
        if length:
            self.expectedLength = int(length)

    def pagePart(self, s):
        client.HTTPDownloader.pagePart(self, s)
        self.parser.feed(s)
        self.soFar += len(s)

    def pageEnd(self):
        self.value = self.parser.anchorlist
        client.HTTPDownloader.pageEnd(self)



class SpiderSender(app.ApplicationService):

    maxDownloaders = 10
    maxDepth = 5
    fileTemplate = os.path.join('%s', '%s')

    def __init__(self, *args, **kw):
        app.ApplicationService.__init__(self, *args, **kw)
        self.downloaders = {}
        self.queue = []

    def __getstate__(self):
        d = self.__dict__.copy()
        d['downloaders'] = {}
        return d

    def startService(self):
        app.ApplicationService.startService(self)
        self.tryDownload()

    def stopService(self):
        app.ApplicationService.stopService(self)
        for transport in self.downloaders.values():
            transport.disconnect()

    def addTargets(self, targets):
        for target in targets:
            self.queue.append((target, 0))
        self.tryDownload()

    def tryDownload(self):
        if not self.serviceRunning:
            return 
        while self.queue and (len(self.downloaders) < self.maxDownloaders):
            self.download()

    def download(self):
        uri, depth = self.queue.pop(0)
        host, port, url = client._parse(uri)
        fname = self.fileTemplate % (host, url)
        dir = os.path.dirname(fname)
        if not os.path.isdir(dir):
            os.makedirs(dir)
        if not os.path.basename(fname):
            fname = os.path.join(fname, 'index.html')
        f = HTTPDownloader(host, url, fname)
        f.deferred.addCallbacks(callback=self.downloadFinished,
                                callbackArgs=(uri, depth),
                                errback=self.downloadFailed,
                                errbackArgs=(uri,))
        self.downloaders[uri] = reactor.connectTCP(host, port, f)
        self.notifyDownloadStart(uri)

    def notifyDownloadStart(self, uri):
        pass

    def notifyDownloadEnd(self, uri):
        pass

    def downloadFinished(self, anchors, uri, depth):
        self.notifyDownloadEnd(uri)
        del self.downloaders[uri]
        if depth >= self.maxDepth > 0:
            return 
        for anchor in anchors:
            anchor = urlparse.urljoin(uri, anchor)
            self.queue.append((anchor, (depth + 1)))
        self.tryDownload()

    def downloadFailed(self, reasons, uri):
        self.notifyDownloadEnd(uri)
        del self.downloaders[uri]
        self.tryDownload()
