
import gtk
import gnome.ui
import string
import traceback

# Font caching

normalFont = gtk.load_font("-adobe-courier-medium-r-normal-*-*-120-*-*-m-*-iso8859-1")
boldFont = gtk.load_font("-adobe-courier-bold-r-normal-*-*-120-*-*-m-*-iso8859-1")

from twisted import copyright
from twisted.internet import tcp, ingtkernet
ingtkernet.install()
from twisted.spread import pb

portno = 8889


def scrollify(widget):
    widget.set_word_wrap(gtk.TRUE)
    scrl=gtk.GtkScrolledWindow()
    scrl.add(widget)
    scrl.set_policy(gtk.POLICY_NEVER, gtk.POLICY_ALWAYS)
    # scrl.set_update_policy(gtk.POLICY_AUTOMATIC)
    return scrl

def defocusify(widget):
    widget.unset_flags(gtk.CAN_FOCUS)


def gtktextget(text):
    return text.get_chars(0,text.get_length())
def dontgo(*ev):
    return gtk.TRUE

class ResponseWindow(gtk.GtkWindow):
    def __init__(self,question,default,callifok,callifcancel):
        gtk.GtkWindow.__init__(self)
        self.callifok=callifok
        self.callifcancel=callifcancel
        self.text=gtk.GtkText()
        self.set_title(question)
        self.text.set_editable(gtk.TRUE)
        self.text.insert_defaults(default)
        scrl=scrollify(self.text)
        vb=gtk.GtkVBox()
        bb=gtk.GtkHButtonBox()
        vb.pack_start(scrl)
        bb.set_spacing(0)
        bb.set_layout(gtk.BUTTONBOX_END)
        cancelb=gnome.ui.GnomeStockButton(gnome.ui.STOCK_BUTTON_CANCEL)
        bb.add(cancelb)
        okb=gnome.ui.GnomeStockButton(gnome.ui.STOCK_BUTTON_OK)
        cancelb.set_flags(gtk.CAN_DEFAULT)
        okb.set_flags(gtk.CAN_DEFAULT)
        okb.set_flags(gtk.HAS_DEFAULT)
        bb.add(okb)
        okb.connect('clicked',self.callok)
        cancelb.connect('clicked',self.callcancel)
        vb.add(bb,expand=gtk.FALSE)
        
        self.add(vb)
        self.set_usize(300,200)
        self.connect('delete_event',dontgo)
        self.show_all()


    def callok(self,*ev):
        if self.callifok is not None:
            self.callifok(gtktextget(self.text))
        self.destroy()

    def callcancel(self,*ev):
        if self.callifcancel is not None:
            self.callifcancel()
        self.destroy()

    
class GameWindow(gtk.GtkWindow, pb.Referenced):

    request = ResponseWindow
    
    shortcuts = {"n":"go north",
                 "s":"go south",
                 "e":"go east",
                 "w":"go west",
                 "ne":"go northeast",
                 "nw":"go northwest",
                 "sw":"go southwest",
                 "se":"go southeast",
                 "u":"go up",
                 "d":"go down"}
    
    keycuts = {gtk.GDK.KP_0:"go up",
               gtk.GDK.KP_1:"go southwest",
               gtk.GDK.KP_2:"go south",
               gtk.GDK.KP_3:"go southeast",
               gtk.GDK.KP_4:"go west",
               gtk.GDK.KP_5:"go down",
               gtk.GDK.KP_6:"go east",
               gtk.GDK.KP_7:"go northwest",
               gtk.GDK.KP_8:"go north",
               gtk.GDK.KP_9:"go northeast"}

    histpos = 0
    def __hash__(self):
        return id(self)
    
    def __init__(self, remote, broker):
        #print self.send_
        gtk.GtkWindow.__init__(self, gtk.WINDOW_TOPLEVEL)
        self.set_title("Reality Faucet")
        self.set_usize(640,480)
        self.namelabel = gtk.GtkLabel("NameLabel")

        self.descbox=gtk.GtkText()
        self.descbox.set_usize(370,255)
        self.descscrl=scrollify(self.descbox)
        defocusify(self.descbox)
        
        self.itembox=gtk.GtkText()
        self.itemscrl=scrollify(self.itembox)
        defocusify(self.itembox)
        
        self.happenings=gtk.GtkText()
        self.happscrl=scrollify(self.happenings)
        defocusify(self.happenings)
        self.cmdarea=gtk.GtkEntry()

        self.hpaned=gtk.GtkHPaned()
        self.hpaned.add1(self.descscrl)
        self.hpaned.add2(self.itemscrl)
        
        self.vpaned=gtk.GtkVPaned()
        self.vpaned.add1(self.hpaned)
        self.vpaned.add2(self.happscrl)

        self.vbox=gtk.GtkVBox()
        self.vbox.pack_start(self.namelabel, expand=0)
        
        self.vbox.add(self.vpaned)
        self.vbox.pack_start(self.cmdarea, expand=0)
        
        self.add(self.vbox)
        
        self.signal_connect('destroy',gtk.mainquit,None)
        
        self.cmdarea.connect("key_press_event", self.key_function)
        self.cmdarea.grab_focus()

        self.history = ['']
        self.descriptions={}
        self.items={}
        self.exits=[]
        self.remote = remote
        broker.notifyOnDisconnect(self.connectionLost)

    def connectionLost(self):
        self.hide()
        lw.show_all()
        lw.loginReport("Disconnected from Server.")

    def sendVerb(self, verb):
        self.seeEvent("> "+verb,boldFont)
        self.cmdarea.set_text(verb)
        self.remote.execute(verb,
                            pbcallback = self.finishVerb,
                            pberrback = self.errorVerb)

    def errorVerb(self, error):
        self.seeEvent(error, boldFont)
        self.verbDone('')

    def finishVerb(self, result):
        self.cmdarea.set_sensitive(gtk.TRUE)
        self.cmdarea.set_editable(gtk.TRUE)
        self.focus_text()
        self.cmdarea.set_text("")


    def key_function(self, entry, event):
        possible_fill=self.keycuts.get(event.keyval)
        if possible_fill:
            self.cmdarea.set_sensitive(gtk.FALSE)
            self.cmdarea.set_editable(gtk.FALSE)
            self.sendVerb(possible_fill)
            self.clear_key()
        if len(entry.get_text()) == 0:
            if event.keyval == 39:
                entry.set_text('say ""')
                entry.set_position(5)
                self.clear_key()
            elif event.keyval == 59:
                entry.set_text('emote ""')
                entry.set_position(7)
                self.clear_key()
        if event.keyval == gtk.GDK.Return:
            self.sendText(entry)
        elif event.keyval == gtk.GDK.Tab:
            gtk.idle_add(self.focus_text)
        elif event.keyval in (gtk.GDK.KP_Up, gtk.GDK.Up):
            self.historyUp()
            gtk.idle_add(self.focus_text)
        elif event.keyval in (gtk.GDK.KP_Down, gtk.GDK.Down):
            self.historyDown()
            gtk.idle_add(self.focus_text)
        else: return
        self.clear_key()
        
    def historyUp(self):
        if self.histpos > 0:
            l = self.cmdarea.get_text()
            if len(l) > 0 and l[0] == '\n': l = l[1:]
            if len(l) > 0 and l[-1] == '\n': l = l[:-1]
            self.history[self.histpos] = l
            self.histpos = self.histpos - 1
            self.cmdarea.set_text(self.history[self.histpos])
            
    def historyDown(self):
        if self.histpos < len(self.history) - 1:
            l = self.cmdarea.get_text()
            if len(l) > 0 and l[0] == '\n': l = l[1:]
            if len(l) > 0 and l[-1] == '\n': l = l[:-1]
            self.history[self.histpos] = l
            self.histpos = self.histpos + 1
            self.cmdarea.set_text(self.history[self.histpos])

    def focus_text(self):
        self.cmdarea.grab_focus()
        return gtk.FALSE  # don't requeue this handler

    def script(self,filename):
        for i in open(filename).readlines():
            i=i[:-1]
            self.sendVerb(i)
    
    def sendText(self, entry):
        tosend=entry.get_text()
        if not tosend:
            return
        if tosend[0]=='@':
            exec tosend[1:]
            return
        possible_shortcut=self.shortcuts.get(tosend)
        if possible_shortcut:
            tosend = possible_shortcut
            gtk.idle_add(self.focus_text)
        # Put this line into the History
        if len(tosend) > 0:
            self.histpos = len(self.history) - 1
            self.history[self.histpos] = tosend
            self.histpos = self.histpos + 1
            self.history.append('')
        # tosend should now be the "final" command sent to the server
        self.cmdarea.set_sensitive(gtk.FALSE)
        self.cmdarea.set_editable(gtk.FALSE)
        
        self.sendVerb(tosend)
    
    bswp = 0

    def seeEvent(self,phrase,f=normalFont,fg=None,bg=None):
        txt=self.happenings
        txt.set_point(txt.get_length())
        txt.freeze()
        self.bswp = not self.bswp
        # txt.insert_defaults(phrase+"\n")
        txt.insert(f,fg,bg, phrase+"\n")
        adj=txt.get_vadjustment()
        txt.thaw()
        adj.set_value(adj.upper - adj.page_size)
        
    remote_seeEvent = seeEvent
    
    def remote_seeName(self,*args):
        self.namelabel.set_text(string.join(args,' - '))

    def remote_dontSeeItem(self,key,parent):
        try: del self.items[key]
        except: print 'tried to remove nonexistant item %s' % str(key)
        self.reitem()
        
    def remote_seeNoItems(self):
        self.items={}
        self.reitem()
    
    def remote_seeItem(self,key,parent,value):
        self.items[key]=value
        self.reitem()
        
    def remote_seeDescription(self,key,value):
        self.descriptions[key]=value
        self.redesc()

    def remote_dontSeeDescription(self,key):
        del self.descriptions[key]
        self.redesc()

    def remote_seeNoDescriptions(self):
        self.descriptions={}
        self.redesc()

    def reexit(self):
        self.remote_seeDescription('__EXITS__',"\nObvious Exits: %s"%string.join(self.exits,', '))
        
    def remote_seeExit(self,exit):
        self.exits.append(exit)
        self.reexit()

    def remote_dontSeeExit(self,exit):
        if exit in self.exits:
            self.exits.remove(exit)
            self.reexit()

    def remote_seeNoExits(self):
        self.exits=[]
        self.reexit()
        
    def reitem(self):
        txt=self.itembox
        txt.freeze()
        txt.delete_text(0,txt.get_length())
        txt.set_point(0)
        items = self.items.values()
        items.sort()
        x=string.join(items,'\n')
        txt.insert_defaults(x)
        txt.thaw()
        
    def redesc(self):
        txt=self.descbox
        txt.freeze()
        txt.delete_text(0,txt.get_length())
        txt.set_point(0)
        from copy import copy
        descs = copy(self.descriptions)
        try:
            del descs["__EXITS__"]
        except: pass
        try:
            del descs["__MAIN__"]
        except: pass
        mn=[self.descriptions.get('__MAIN__') or '']
        ex=[self.descriptions.get('__EXITS__') or '']
        values = descs.items()
        values.sort()
        values = map(lambda (x, y): y, values)
        x = string.join(mn + values + ex)
        txt.insert_defaults(x)
        txt.thaw()
        
    def clear_key(self):
        self.cmdarea.emit_stop_by_name("key_press_event")

class LoginWindow(gtk.GtkWindow):
    def __init__(self):
        gtk.GtkWindow.__init__(self,gtk.WINDOW_TOPLEVEL)
        version_label = gtk.GtkLabel("Python GTK Faucet %s" %
                                     copyright.version)
        version_label.show()
        self.character=gtk.GtkEntry()
        self.password=gtk.GtkEntry()
        self.worldname=gtk.GtkEntry()
        self.hostname=gtk.GtkEntry()
        self.port=gtk.GtkEntry()
        self.password.set_visibility(gtk.FALSE)

        self.character.set_text("Damien")
        self.password.set_text("admin")
        self.worldname.set_text("reality")
        self.hostname.set_text("localhost")
        self.port.set_text(str(portno))

        charlbl=gtk.GtkLabel("Character Name:")
        passlbl=gtk.GtkLabel("Password:")
        worldlbl=gtk.GtkLabel("World:")
        hostlbl=gtk.GtkLabel("Hostname:")
        portlbl=gtk.GtkLabel("Port:")
        
        self.logstat = gtk.GtkLabel("Protocol PB0")
        self.okbutton=gtk.GtkButton("Log In")

        okbtnbx=gtk.GtkHButtonBox()
        okbtnbx.add(self.okbutton)
        
        vbox=gtk.GtkVBox()
        vbox.add(version_label)
        table=gtk.GtkTable(2,5)
        z=0
        for i in [[charlbl,self.character],
                  [passlbl,self.password],
                  [hostlbl,self.hostname],
                  [worldlbl,self.worldname],
                  [portlbl,self.port]]:
            table.attach(i[0],0,1,z,z+1)
            table.attach(i[1],1,2,z,z+1)
            z=z+1

        vbox.add(table)
        vbox.add(self.logstat)
        vbox.add(okbtnbx)
        self.add(vbox)

        self.okbutton.signal_connect('clicked',self.play)
        self.signal_connect('destroy',gtk.mainquit,None)
        #self.set_geometry_hints(max_width=0, max_height=0)

    def loginReset(self):
        self.logstat.set_text("Idle.")
        
    def loginReport(self, txt):
        self.logstat.set_text(txt)
        gtk.timeout_add(30000, self.loginReset)
        
    def play(self,button):
        global gw
        host = self.hostname.get_text()
        port = self.port.get_text()
        world = self.worldname.get_text()
        # Maybe we're connecting to a unix socket, so don't make any
        # assumptions
        try:
            port = int(port)
        except:
            pass
        char = self.character.get_text()
        pswd = self.password.get_text()
        b = pb.Broker()
        self.broker = b
        b.requestPerspective(world, char, pswd, self.gameWindow, self.tryAgain)
        b.notifyOnDisconnect(self.discoInferno)
        tcp.Client(host, port, b)

    def gameWindow(self, rem):
        print 'window'
        gw = GameWindow(rem,self.broker)
        gw.show_all()
        rem.observe(gw)
        self.hide()

    def tryAgain(self):
        self.loginReport("could not connect.")

    def discoInferno(self):
        self.loginReport("meep, meep")
        
##def poke(button):
##    global gw
##    import select
##    print select.select([gw.socket, gw.rfile],[],[],0)
##    gw.parse(gw.recv_())

##def debug_blocking_bug():
##    win = gtk.GtkWindow()
##    win.set_title("Poke")
##    win.set_usize(125,-1)
##    b = gtk.GtkButton('Poke')
##    b.connect('clicked', poke)
##    win.add(b)
##    win.show_all()

##def debug_main_quit():
##    """Create a window with a button to call mainquit"""
##    win = gtk.GtkWindow()
##    win.set_title("Quit")
##    win.set_usize(125, -1)
##    b = gtk.GtkButton("Main Quit")
##    b.connect("clicked", gtk.mainquit)
##    win.add(b)
##    b.show()
##    win.show()
        
##quitted = 0
        
##def myMainLoop():
##    global quitted
##    while not quitted:
##        gtk.mainiteration()

##def myMainQuit():
##    global quitted
##    quitted = 1

def main():
    global lw
    lw = LoginWindow()
    lw.show_all()
    gtk.mainloop()
