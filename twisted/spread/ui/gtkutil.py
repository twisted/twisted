
# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.


import gtk
import string

from twisted.spread import pb
from twisted import copyright
from twisted.python import reflect
from twisted.cred.credentials import UsernamePassword

normalFont = gtk.load_font("-adobe-courier-medium-r-normal-*-*-120-*-*-m-*-iso8859-1")
boldFont = gtk.load_font("-adobe-courier-bold-r-normal-*-*-120-*-*-m-*-iso8859-1")
errorFont = gtk.load_font("-adobe-courier-medium-o-normal-*-*-120-*-*-m-*-iso8859-1")


def selectAll(widget,event):
    widget.select_region(0,-1)

def cbutton(name, callback):
    b = gtk.GtkButton(name)
    b.connect('clicked', callback)
    return b

class ButtonBar:
    barButtons = None
    def getButtonList(self, prefix='button_', container=None):
        result = []
        buttons = self.barButtons or \
                  reflect.prefixedMethodNames(self.__class__, prefix)
        for b in buttons:
            bName = string.replace(b, '_', ' ')
            result.append(cbutton(bName, getattr(self,prefix+b)))
        if container:
            map(container.add, result)
        return result

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

    _resetTimeout = None

    def __init__(self, callback,
                 referenceable=None,
                 initialUser="guest", initialPassword="guest",
                 initialHostname="localhost",initialPortno=str(pb.portno),
                 initialService="", initialPerspective=""):
        gtk.GtkWindow.__init__(self,gtk.WINDOW_TOPLEVEL)
        version_label = gtk.GtkLabel("Twisted v%s" % copyright.version)
        self.pbReferenceable = referenceable
        self.pbCallback = callback
        # version_label.show()
        self.username = gtk.GtkEntry()
        self.password = gtk.GtkEntry()
        self.service = gtk.GtkEntry()
        self.perspective = gtk.GtkEntry()
        self.hostname = gtk.GtkEntry()
        self.port = gtk.GtkEntry()
        self.password.set_visibility(gtk.FALSE)

        self.username.set_text(initialUser)
        self.password.set_text(initialPassword)
        self.service.set_text(initialService)
        self.perspective.set_text(initialPerspective)
        self.hostname.set_text(initialHostname)
        self.port.set_text(str(initialPortno))

        userlbl=gtk.GtkLabel("Username:")
        passlbl=gtk.GtkLabel("Password:")
        servicelbl=gtk.GtkLabel("Service:")
        perspeclbl=gtk.GtkLabel("Perspective:")
        hostlbl=gtk.GtkLabel("Hostname:")
        portlbl=gtk.GtkLabel("Port #:")
        self.allLabels = [
            userlbl, passlbl, servicelbl, perspeclbl, hostlbl, portlbl
            ]
        self.logstat = gtk.GtkLabel("Protocol PB-%s" % pb.Broker.version)
        self.okbutton = cbutton("Log In", self.login)
        self.okbutton["can_default"] = 1
        self.okbutton["receives_default"] = 1

        okbtnbx = gtk.GtkHButtonBox()
        okbtnbx.add(self.okbutton)

        vbox = gtk.GtkVBox()
        vbox.add(version_label)
        table = gtk.GtkTable(2,6)
        row=0
        for label, entry in [(userlbl, self.username),
                             (passlbl, self.password),
                             (hostlbl, self.hostname),
                             (servicelbl, self.service),
                             (perspeclbl, self.perspective),
                             (portlbl, self.port)]:
            table.attach(label, 0, 1, row, row+1)
            table.attach(entry, 1, 2, row, row+1)
            row = row+1

        vbox.add(table)
        vbox.add(self.logstat)
        vbox.add(okbtnbx)
        self.add(vbox)
        self.username.grab_focus()
        self.okbutton.grab_default()
        for fld in self.username, self.password, self.hostname, self.service, self.perspective:
            fld.signal_connect('activate',self.login)
            fld.signal_connect('focus_in_event',selectAll)
        self.signal_connect('destroy',gtk.mainquit,None)

    def loginReset(self):
        print 'doing login reset'
        self.logstat.set_text("Idle.")
        self._resetTimeout = None
        return 0

    def loginReport(self, txt):
        print 'setting login report',repr(txt)
        self.logstat.set_text(txt)
        if not (self._resetTimeout is None):
            gtk.timeout_remove(self._resetTimeout)

        self._resetTimeout = gtk.timeout_add(59000, self.loginReset)

    def login(self, btn):
        host = self.hostname.get_text()
        port = self.port.get_text()
        service = self.service.get_text()
        perspective = self.perspective.get_text()
        # Maybe we're connecting to a unix socket, so don't make any
        # assumptions
        try:
            port = int(port)
        except:
            pass
        user = self.username.get_text()
        pswd = self.password.get_text()
        self.loginReport("connecting...")
        # putting this off to avoid a stupid bug in gtk where it won't redraw
        # if you input_add a connecting socket (!??)
        self.user_tx = user
        self.pswd_tx = pswd
        self.host_tx = host
        self.port_tx = port
        self.service_tx = service
        self.perspective_tx = perspective or user
        afterOneTimeout(10, self.__actuallyConnect)
    
    def __actuallyConnect(self):
        from twisted.application import internet

        f = pb.PBClientFactory()
        internet.TCPClient(self.host_tx, self.port_tx, f)
        creds = UsernamePassword(self.user_tx, self.pswd_tx)
        f.login(creds, self.pbReferenceable
            ).addCallbacks(self.pbCallback, self.couldNotConnect
            ).setTimeout(30
            )

    def couldNotConnect(self, msg):
        self.loginReport("couldn't connect: %s" % str(msg))


class _TimerOuter:
    def __init__(self, timeout, cmd, args):
        self.args = args
        self.cmd = cmd
        self.tid = gtk.timeout_add(timeout, self.doIt)

    def doIt(self):
        gtk.timeout_remove(self.tid)
        apply(self.cmd, self.args)

def afterOneTimeout(timeout, cmd, *args):
    _TimerOuter(timeout, cmd, args)
