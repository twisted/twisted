
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

from __future__ import nested_scopes

from twisted.internet import gtk2reactor
gtk2reactor.install()

import gtk
from gtk import glade
from twisted import copyright
from twisted.internet import reactor, defer
from twisted.python import failure, log, util
from twisted.spread import pb
from twisted.cred.credentials import UsernamePassword
from twisted.internet import error as netError


class LoginDialog:
    def __init__(self, deferred):
        self.deferredResult = deferred

        gladefile = util.sibpath(__file__, "pbgtk2login.glade")
        self.glade = glade.XML(gladefile)

        self.glade.signal_autoconnect(self)

        self.setWidgetsFromGladefile()
        self._loginDialog.show()

    def setWidgetsFromGladefile(self):
        widgets = ("hostEntry", "portEntry", "userNameEntry", "passwordEntry",
                   "statusBar", "loginDialog")
        gw = self.glade.get_widget
        for widgetName in widgets:
            setattr(self, "_" + widgetName, gw(widgetName))

        self._statusContext = self._statusBar.get_context_id("Login dialog.")

    def on_loginDialog_response(self, widget, response):
        handlers = {gtk.RESPONSE_NONE: self.windowClosed,
                   gtk.RESPONSE_DELETE_EVENT: self.windowClosed,
                   gtk.RESPONSE_OK: self.doLogin,
                   gtk.RESPONSE_CANCEL: self.cancelled}
        handlers.get(response)()

    def on_loginDialog_close(self, widget, userdata=None):
        self.windowClosed()

    def cancelled(self):
        if not self.deferredResult.called:
            self.deferredResult.errback()
        self._loginDialog.destroy()

    def windowClosed(self, reason=None):
         if not self.deferredResult.called:
            self.deferredResult.errback()

    def doLogin(self):
        host = self._hostEntry.get_text()
        port = int(self._portEntry.get_text())
        userName = self._userNameEntry.get_text()
        password = self._passwordEntry.get_text()

        client_factory = pb.PBClientFactory()
        reactor.connectTCP(host, port, client_factory)
        creds = UsernamePassword(userName, password)
        client_factory.login(creds).addCallbacks(self._cbGotPerspective, self._ebFailedLogin)
        
        self.statusMsg("Contacting server...")

    def _cbGotPerspective(self, perspective):
        self.statusMsg("Connected to server.")
        self.deferredResult.callback(perspective)
        self._loginDialog.destroy()

    def _ebFailedLogin(self, reason):
        if isinstance(reason, failure.Failure):
            text = str(reason.value)
        else:
            text = str(reason)
            
        self.statusMsg(text)
        msg = gtk.MessageDialog(self._loginDialog,
                                gtk.DIALOG_DESTROY_WITH_PARENT,
                                gtk.MESSAGE_ERROR,
                                gtk.BUTTONS_CLOSE,
                                text)
        msg.show_all()
        msg.connect("response", lambda *a: msg.destroy())

    def statusMsg(self, text):
        self._statusBar.push(self._statusContext, text)


class EchoClient:
    def __init__(self, echoer):
        self.echoer = echoer
        w = gtk.Window(gtk.WINDOW_TOPLEVEL)
        vb = gtk.VBox(); b = gtk.Button("Echo:")
        self.entry = gtk.Entry(); self.outry = gtk.Entry()
        w.add(vb)
        map(vb.add, [b, self.entry, self.outry])
        b.connect('clicked', self.clicked)
        w.connect('destroy', gtk.mainquit)
        w.show_all()

    def clicked(self, b):
        txt = self.entry.get_text()
        self.entry.set_text("")
        self.echoer.callRemote('echo',txt).addCallback(self.outry.set_text)

d = defer.Deferred()
LoginDialog(d)
d.addCallbacks(EchoClient,
               gtk.mainquit)

reactor.run()
