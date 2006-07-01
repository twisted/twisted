# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.

#
from twisted.web import client
from twisted.internet import reactor
import md5
from zope.interface import implements

class IChangeNotified:
    pass

class BaseChangeNotified:

    implements(IChangeNotified)

    def reportChange(self, old, new):
        pass

    def reportNoChange(self):
        pass

class ChangeChecker:

    working = 0
    call = None

    def __init__(self, notified, url, delay=60):
        self.notified = notified
        self.url = url
        self.md5 = None
        self.delay = delay

    def start(self):
        self.working = 1
        self._getPage()

    def stop(self):
        if self.call:
            self.call.cancel()
            self.call = None
        self.working = 0

    def _getPage(self):
        d = client.getPage(self.url)
        d.addErrback(self.noPage)
        d.addCallback(self.page)
        self.call = None

    def noPage(self, e):
        self.gotMD5(None)

    def page(self, p):
        if p is None:
            return self.gotMD5(None)
        m = md5.new()
        m.update(p)
        self.gotMD5(m.digest())

    def gotMD5(self, md5):
        if not self.working:
            return
        if md5 != self.md5:
            self.notified.reportChange(self.md5, md5)
            self.md5 = md5
        else:
            self.notified.reportNoChange()
        if not self.call:
            self.call = reactor.callLater(self.delay, self._getPage)


class ProxyChangeChecker(ChangeChecker):

    def __init__(self, proxyHost, proxyPort, notified, url, delay=60):
        self.proxyHost = proxyHost
        self.proxyPort = proxyPort
        ChangeChecker.__init__(self, notified, url, delay)

    def _getPage(self):
        factory = client.HTTPClientFactory(self.proxyHost, self.url)
        factory.headers = {'pragma': 'no-cache'}
        reactor.connectTCP(self.proxyHost, self.proxyPort, factory)
        d = factory.deferred
        d.addErrback(self.noPage)
        d.addCallback(self.page)
