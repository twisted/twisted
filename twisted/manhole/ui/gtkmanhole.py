import gtk, sys

from twisted.words.ui import gtkim
from twisted.spread.ui import gtkutil
from twisted.internet import ingtkernet
from twisted.spread import pb
ingtkernet.install()

class Interaction(gtk.GtkWindow):
    def __init__(self):
        gtk.GtkWindow.__init__(self, gtk.WINDOW_TOPLEVEL)
        self.set_title("Manhole Interaction")

        vb = gtk.GtkVBox()
        vp = gtk.GtkVPaned()

        self.output = gtk.GtkText()
        gtkim.defocusify(self.output)
        vp.add1(gtkim.scrolltxt(self.output))

        self.input = gtk.GtkText()
        self.input.set_editable(gtk.TRUE)
        vp.add2(gtkim.scrolltxt(self.input))

        self.send = gtkim.cbutton("Send", self.sendMessage)
        vb.pack_start(vp, 1,1,0)
        vb.pack_start(self.send, 0,0,0)

        self.add(vb)
        self.signal_connect('destroy', sys.exit, None)

    def messageReceived(self, message):
        t = self.output
        t.set_point(t.get_length())
        t.freeze()
        t.insert_defaults('\n'+message)
        a = t.get_vadjustment()
        t.thaw()
        a.set_value(a.upper - a.page_size)
        self.input.grab_focus()

    def sendMessage(self, unused_data=None):
        self.perspective.do(self.input.get_chars(0,-1), pbcallback=self.messageReceived)

    def connected(self, perspective):
        self.name = lw.username.get_text()
        lw.hide()
        self.perspective = perspective
        self.show_all()

def main():
    global lw
    i = Interaction()
    lw = gtkutil.Login(i.connected, initialUser="admin",
                       initialPassword="admin", initialService="manhole")
    lw.show_all()
    gtk.mainloop()

if __name__=='__main__':main()
