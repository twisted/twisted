
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

import gtk

from twisted.spread import pb
from twisted.internet import tcp
from twisted import copyright


normalFont = gtk.load_font("-adobe-courier-medium-r-normal-*-*-120-*-*-m-*-iso8859-1")
boldFont = gtk.load_font("-adobe-courier-bold-r-normal-*-*-120-*-*-m-*-iso8859-1")
errorFont = gtk.load_font("-adobe-courier-medium-o-normal-*-*-120-*-*-m-*-iso8859-1")



def cbutton(name, callback):
    b = gtk.GtkButton(name)
    b.connect('clicked', callback)
    return b

def scrollify(widget):
    #widget.set_word_wrap(gtk.TRUE)
    scrl=gtk.GtkScrolledWindow()
    scrl.add(widget)
    scrl.set_policy(gtk.POLICY_NEVER, gtk.POLICY_ALWAYS)
    # scrl.set_update_policy(gtk.POLICY_AUTOMATIC)
    return scrl

def defocusify(widget):
    widget.unset_flags(gtk.CAN_FOCUS)

class GetString(gtk.GtkWindow):
    def __init__(self, im, desc):
        gtk.GtkWindow.__init__(self, gtk.WINDOW_TOPLEVEL)
        self.set_title(desc)
        self.im = im
        button = cbutton(desc, self.clicked)
        self.entry = gtk.GtkEntry()
        self.entry.connect('activate', self.clicked)
        hb = gtk.GtkHBox()
        hb.add(self.entry)
        hb.add(button)
        self.add(hb)
        self.show_all()

    def clicked(self, btn):
        raise NotImplementedError


class Login(gtk.GtkWindow):
    def __init__(self, callback,
                 referenced = None,
                 initialUser = "guest",
                 initialPassword = "guest",
                 initialHostname = "localhost",
                 initialService  = "",
                 initialPortno   = pb.portno):
        gtk.GtkWindow.__init__(self,gtk.WINDOW_TOPLEVEL)
        version_label = gtk.GtkLabel("Twisted v%s" % copyright.version)
        self.pbReferenced = referenced
        self.pbCallback = callback
        # version_label.show()
        self.username = gtk.GtkEntry()
        self.password = gtk.GtkEntry()
        self.service  = gtk.GtkEntry()
        self.hostname = gtk.GtkEntry()
        self.port     = gtk.GtkEntry()
        self.password.set_visibility(gtk.FALSE)

        self.username.set_text(initialUser)
        self.password.set_text(initialPassword)
        self.service.set_text(initialService)
        self.hostname.set_text(initialHostname)
        self.port.set_text(str(initialPortno))

        userlbl=gtk.GtkLabel("Username:")
        passlbl=gtk.GtkLabel("Password:")
        servicelbl=gtk.GtkLabel("Service:")
        hostlbl=gtk.GtkLabel("Hostname:")
        portlbl=gtk.GtkLabel("Port #:")
        
        self.logstat  = gtk.GtkLabel("Protocol PB-%s" % pb.Broker.version)
        self.okbutton = cbutton("Log In", self.login)

        okbtnbx = gtk.GtkHButtonBox()
        okbtnbx.add(self.okbutton)
        
        vbox = gtk.GtkVBox()
        vbox.add(version_label)
        table = gtk.GtkTable(2,5)
        z=0
        for i in [[userlbl,self.username],
                  [passlbl,self.password],
                  [hostlbl,self.hostname],
                  [servicelbl,self.service],
                  [portlbl,self.port]]:
            table.attach(i[0],0,1,z,z+1)
            table.attach(i[1],1,2,z,z+1)
            z = z+1

        vbox.add(table)
        vbox.add(self.logstat)
        vbox.add(okbtnbx)
        self.add(vbox)

        self.signal_connect('destroy',gtk.mainquit,None)

    def loginReset(self):
        self.logstat.set_text("Idle.")
        
    def loginReport(self, txt):
        self.logstat.set_text(txt)
        gtk.timeout_add(30000, self.loginReset)

    def login(self, btn):
        host = self.hostname.get_text()
        port = self.port.get_text()
        service = self.service.get_text()
        # Maybe we're connecting to a unix socket, so don't make any
        # assumptions
        try:
            port = int(port)
        except:
            pass
        user = self.username.get_text()
        pswd = self.password.get_text()
        b = pb.Broker()
        self.broker = b
        b.requestIdentity(user, pswd,
                          callback   = self.gotIdentity,
                          errback    = self.couldNotConnect)
        b.notifyOnDisconnect(self.disconnected)
        tcp.Client(host, port, b)

    def gotIdentity(self, identity):
        identity.attach(self.service.get_text(), self.pbReferenced, pbcallback=self.pbCallback)

    def couldNotConnect(self, msg):
        print 'couldNotConnect', msg
        self.loginReport("could not connect.")

    def disconnected(self):
        print 'disconnected'
        self.loginReport("disconnected from server.")
