import gtk, sys

from twisted.words.ui import gtkim
from twisted.spread.ui import gtkutil
from twisted.internet import ingtkernet
from twisted.spread import pb
ingtkernet.install()

normalFont = gtk.load_font("-adobe-courier-medium-r-normal-*-*-120-*-*-m-*-iso8859-1")
font = normalFont
boldFont = gtk.load_font("-adobe-courier-bold-r-normal-*-*-120-*-*-m-*-iso8859-1")
errorFont = gtk.load_font("-adobe-courier-medium-o-normal-*-*-120-*-*-m-*-iso8859-1")

class Interaction(gtk.GtkWindow):
    def __init__(self):
        gtk.GtkWindow.__init__(self, gtk.WINDOW_TOPLEVEL)
        self.set_title("Manhole Interaction")

        vb = gtk.GtkVBox()
        vp = gtk.GtkVPaned()

        self.output = gtk.GtkText()
        gtkim.defocusify(self.output)
        vp.pack1(gtkim.scrolltxt(self.output), gtk.TRUE, gtk.FALSE)

        self.input = gtk.GtkText()
        self.input.set_editable(gtk.TRUE)
        self.input.connect("key_press_event", self.processKey)
        vp.pack2(gtkim.scrolltxt(self.input), gtk.FALSE, gtk.TRUE)
        vb.pack_start(vp, 1,1,0)

        self.add(vb)
        self.signal_connect('destroy', sys.exit, None)

    def processKey(self, entry, event):
        if event.keyval == gtk.GDK.Return:
#            if self.input.get_chars(self.input.get_length()-1,-1) == ":":
#                print "woo!"
#            else:
                self.sendMessage(entry)
                self.input.delete_text(0,-1)
                self.input.emit_stop_by_name("key_press_event")

    def messageReceived(self, message):
        print "received: ", message
        win = self.get_window()
        blue = win.colormap.alloc(0x0000, 0x0000, 0xffff)
        red = win.colormap.alloc(0xffff, 0x0000, 0x0000)
        green = win.colormap.alloc(0x0000, 0xffff, 0x0000)
        black = win.colormap.alloc(0x0000, 0x0000, 0x0000)

        t = self.output
        t.set_point(t.get_length())
        t.freeze()
        styles = {"out": black, "err": green, "result": blue, "error": red}
        for element in message:
            t.insert(font, styles[element[0]], None, element[1])
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
