import gtk

from twisted.spread import pb
from twisted.internet import tcp
from twisted import copyright


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


class Login(gtk.GtkWindow):
    def __init__(self, callback,
                 referenced = None,
                 initialUser = "glyph",
                 initialPassword = "glyph",
                 initialHostname = "localhost",
                 initialService  = "words",
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
        b.requestPerspective(service, user, pswd,
                             referenced = self.pbReferenced,
                             callback   = self.pbCallback,
                             errback    = self.couldNotConnect)
        b.notifyOnDisconnect(self.disconnected)
        tcp.Client(host, port, b)

    def couldNotConnect(self):
        self.loginReport("could not connect.")

    def disconnected(self):
        self.loginReport("disconnected from server.")
