import gtk, sys, string

from twisted.words.ui import gtkim
from twisted.spread.ui import gtkutil
from twisted.internet import ingtkernet
from twisted.spread import pb
ingtkernet.install()

normalFont = gtk.load_font("-adobe-courier-medium-r-normal-*-*-120-*-*-m-*-iso8859-1")
font = normalFont
boldFont = gtk.load_font("-adobe-courier-bold-r-normal-*-*-120-*-*-m-*-iso8859-1")
errorFont = gtk.load_font("-adobe-courier-medium-o-normal-*-*-120-*-*-m-*-iso8859-1")

def findBeginningOfLineWithPoint(entry):
    pos = entry.get_point()
    while pos:
        pos = pos - 1
        #print 'looking at',pos
        c = entry.get_chars(pos, pos+1)
        #print 'found',repr(c)
        if c == '\n':
            #print 'got it!'
            return pos+1
    #print 'oops.'
    return 0

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
        self.history = []
        self.histpos = 0

    linemode = 0

    def historyUp(self):
        if self.histpos > 0:
            self.histpos = self.histpos - 1
            self.input.delete_text(0, -1)
            self.input.insert_defaults(self.history[self.histpos])

    def historyDown(self):
        if self.histpos < len(self.history) - 1:
            self.histpos = self.histpos + 1
            self.input.delete_text(0, -1)
            self.input.insert_defaults(self.history[self.histpos])
        elif self.histpos == len(self.history) - 1:
            self.histpos = self.histpos + 1
            self.input.delete_text(0, -1)
    
    def processKey(self, entry, event):
        if event.keyval == gtk.GDK.Return:
            l = self.input.get_length()
            # if l is 0, this coredumps gtk ;-)
            if not l:
                self.input.emit_stop_by_name("key_press_event")
                return
            lpos = findBeginningOfLineWithPoint(self.input)
            pt = entry.get_point()
            #print 'HELLO',pt,lpos
            isShift = event.state & gtk.GDK.SHIFT_MASK
            #print isShift
            if (self.input.get_chars(l-1,-1) == ":"):
                #print "woo!"
                self.linemode = 1
            elif isShift:
                self.linemode = 1
                self.input.insert_defaults('\n')
            elif (not self.linemode) or (pt == lpos):
                self.sendMessage(entry)
                self.input.delete_text(0, -1)
                self.input.emit_stop_by_name("key_press_event")
                self.linemode = 0
        elif event.keyval == gtk.GDK.Up:
            self.historyUp()
            gtk.idle_add(self.focusInput)
            self.input.emit_stop_by_name("key_press_event")
        elif event.keyval == gtk.GDK.Down:
            self.historyDown()
            gtk.idle_add(self.focusInput)
            self.input.emit_stop_by_name("key_press_event")

    def focusInput(self):
        self.input.grab_focus()
        return gtk.FALSE # do not requeue
    maxBufSz = 10000
    
    def messageReceived(self, message):
        # print "received: ", message
        t = self.output
        t.set_point(t.get_length())
        t.freeze()
        for element in message:
            # print 'processing',element
            t.insert(font, self.textStyles[element[0]], None, element[1])
        l = t.get_length()
        diff = self.maxBufSz - l
        if diff < 0:
            diff = - diff
            t.delete_text(0,diff)
        t.thaw()
        a = t.get_vadjustment()
        a.set_value(a.upper - a.page_size)
        self.input.grab_focus()

    blockcount = 0
    
    def sendMessage(self, unused_data=None):
        text = self.input.get_chars(0,-1)
        if self.linemode:
            self.blockcount = self.blockcount + 1
            fmt = ">>> # begin %s\n%%s\n#end %s\n" % (
                self.blockcount, self.blockcount)
        else:
            fmt = ">>> %s\n"
        self.history.append(text)
        self.histpos = len(self.history)
        self.messageReceived([['command',fmt % text]])
        self.perspective.do(text,
                            pbcallback=self.messageReceived)

    def connected(self, perspective):
        self.name = lw.username.get_text()
        lw.hide()
        self.perspective = perspective
        self.show_all()
        win = self.get_window()
        blue = win.colormap.alloc(0x0000, 0x0000, 0xffff)
        red = win.colormap.alloc(0xffff, 0x0000, 0x0000)
        orange = win.colormap.alloc(0xaaaa, 0x8888, 0x0000)
        black = win.colormap.alloc(0x0000, 0x0000, 0x0000)
        gray = win.colormap.alloc(0x6666, 0x6666, 0x6666)
        self.textStyles = {"out": black,   "err": orange,
                           "result": blue, "error": red,
                           "command": gray}


def main():
    global lw
    i = Interaction()
    lw = gtkutil.Login(i.connected,
                       initialUser="guest",
                       initialPassword="guest",
                       initialService="manhole")
    lw.show_all()
    gtk.mainloop()

if __name__=='__main__':main()
