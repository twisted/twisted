# Twisted, the Framework of Your Internet
# Copyright (C) 2003 Matthew W. Lefkowitz
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

# import needed classes/functions from Foundation
# import Nib loading functionality from AppKit
from PyObjCTools import NibClassBuilder, AppHelper

import twisted.internet.cfreactor
reactor = twisted.internet.cfreactor.install()

from twisted.internet import protocol
from twisted.protocols import http
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
        reactor.run(installSignalHandlers=False)

if __name__ == '__main__':
    from twisted.python import log
    log.startLogging(sys.stdout)
    AppHelper.runEventLoop()
