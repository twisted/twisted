#
#  MyAppDelegate.py
#  cocoaDemo
#
#  Created by Bob Ippolito on Fri Jan 17 2003.
#  Copyright (c) 2003 __MyCompanyName__. All rights reserved.
#

# import needed classes/functions from Foundation
from Foundation import NSObject, NSLog, NSTimer, NSMutableString

# import Nib loading functionality from AppKit
from AppKit import NibClassBuilder
from AppKit.NibClassBuilder import AutoBaseClass

from twisted.internet import protocol
from twisted.internet import reactor
from twisted.protocols import http
import sys, urlparse

# create ObjC classes as defined in MainMenu.nib
NibClassBuilder.extractClasses("MainMenu")
class TwistzillaClient(http.HTTPClient):
    def __init__(self, delegate, urls):
        self.urls = urls
        self.delegate = delegate

    def connectionMade(self):
        self.sendCommand('GET', self.urls[2])
        self.sendHeader('Host', '%s:%d' % (self.urls[0], self.urls[1]))
        self.sendHeader('User-Agent', 'CocoaTwistzilla')
        self.endHeaders()

    def handleResponse(self, data):
        self.delegate.gotResponse_(data)

class MyAppDelegate(AutoBaseClass):
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
            file = '/'
        else:
            file = u[2]
        protocol.ClientCreator(reactor, TwistzillaClient, self, (host, port, file)).connectTCP(host, port)

    def iterate_(self, ig):
        reactor.iterate(0.05)

    def applicationDidFinishLaunching_(self, aNotification):
        """
        Invoked by NSApplication once the app is done launching and
        immediately before the first pass through the main event
        loop.
        """
        self.messageTextField.setStringValue_("http://www.twistedmatrix.com/")
        self.timer = NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
            0.1,
            self,
            'iterate:',
            self,
            1)
