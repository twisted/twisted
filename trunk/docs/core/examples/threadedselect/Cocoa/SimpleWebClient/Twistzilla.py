# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.


# import needed classes/functions from Cocoa
from Foundation import *
from AppKit import *

# import Nib loading functionality from AppKit
from PyObjCTools import NibClassBuilder, AppHelper

from twisted.internet import _threadedselect
_threadedselect.install()

from twisted.internet import reactor, protocol
from twisted.web import http
from twisted.python import log
import sys, urlparse

# create ObjC classes as defined in MainMenu.nib
NibClassBuilder.extractClasses("MainMenu")
class TwistzillaClient(http.HTTPClient):
    def __init__(self, delegate, urls):
        self.urls = urls
        self.delegate = delegate

    def connectionMade(self):
        self.sendCommand('GET', str(self.urls[2]))
        self.sendHeader('Host', '%s:%d' % (self.urls[0], self.urls[1]))
        self.sendHeader('User-Agent', 'CocoaTwistzilla')
        self.endHeaders()

    def handleResponse(self, data):
        self.delegate.gotResponse_(data)

class MyAppDelegate(NibClassBuilder.AutoBaseClass):
    def gotResponse_(self, html):
        s = self.resultTextField.textStorage()
        s.replaceCharactersInRange_withString_((0, s.length()), html)
        self.progressIndicator.stopAnimation_(self)
    
    def doTwistzillaFetch_(self, sender):
        s = self.resultTextField.textStorage()
        s.deleteCharactersInRange_((0, s.length()))
        self.progressIndicator.startAnimation_(self)
        u = urlparse.urlparse(self.messageTextField.stringValue())
        pos = u[1].find(':')
        if pos == -1:
            host, port = u[1], 80
        else:
            host, port = u[1][:pos], int(u[1][pos+1:])
        if u[2] == '':
            fname = '/'
        else:
            fname = u[2]
        host = host.encode('utf8')
        fname = fname.encode('utf8')
        protocol.ClientCreator(reactor, TwistzillaClient, self, (host, port, fname)).connectTCP(host, port).addErrback(lambda f:self.gotResponse_(f.getBriefTraceback()))

    def applicationDidFinishLaunching_(self, aNotification):
        """
        Invoked by NSApplication once the app is done launching and
        immediately before the first pass through the main event
        loop.
        """
        self.messageTextField.setStringValue_("http://www.twistedmatrix.com/")
        reactor.interleave(AppHelper.callAfter)

    def applicationShouldTerminate_(self, sender):
        if reactor.running:
            reactor.addSystemEventTrigger(
                'after', 'shutdown', AppHelper.stopEventLoop)
            reactor.stop()
            return False
        return True
    
if __name__ == '__main__':
    log.startLogging(sys.stdout)
    AppHelper.runEventLoop()
