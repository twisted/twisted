
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
import string
import traceback

# Font caching

normalFont = gtk.load_font("-adobe-courier-medium-r-normal-*-*-120-*-*-m-*-iso8859-1")
boldFont = gtk.load_font("-adobe-courier-bold-r-normal-*-*-120-*-*-m-*-iso8859-1")

from twisted import copyright
from twisted.internet import tcp, ingtkernet
ingtkernet.install()
from twisted.spread import pb
from twisted.spread.ui import gtkutil

def gtktextget(text):
    return text.get_chars(0,text.get_length())
def dontgo(*ev):
    return gtk.TRUE

class ResponseWindow(gtk.GtkWindow):
    def __init__(self,question,default,callback):
        gtk.GtkWindow.__init__(self)
        self.callback =callback
        self.text=gtk.GtkText()
        self.set_title(question)
        self.text.set_editable(gtk.TRUE)
        self.text.insert_defaults(default)
        self.text.set_word_wrap(gtk.TRUE)
        scrl=gtkutil.scrollify(self.text)
        vb=gtk.GtkVBox()
        bb=gtk.GtkHButtonBox()
        vb.pack_start(scrl)
        bb.set_spacing(0)
        bb.set_layout(gtk.BUTTONBOX_END)
        cancelb=gtkutil.cbutton("Cancel", self.callcancel)
        bb.add(cancelb)
        okb=gtkutil.cbutton("OK", self.callok)
        cancelb.set_flags(gtk.CAN_DEFAULT)
        okb.set_flags(gtk.CAN_DEFAULT)
        okb.set_flags(gtk.HAS_DEFAULT)
        bb.add(okb)
        vb.add(bb,expand=gtk.FALSE)

        self.add(vb)
        self.set_usize(300,200)
        self.connect('delete_event',dontgo)
        self.show_all()


    def callok(self,*ev):
        self.callback.callRemote('ok', gtktextget(self.text))
        self.destroy()

    def callcancel(self,*ev):
        self.callback.callRemote('cancel')
        self.destroy()


class GameWindow(gtk.GtkWindow, pb.Referenceable):

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

    def __init__(self):
        gtk.GtkWindow.__init__(self, gtk.WINDOW_TOPLEVEL)
        self.set_title("Reality Faucet")
        self.set_usize(640,480)
        self.namelabel = gtk.GtkLabel("NameLabel")

        self.descbox=gtk.GtkText()
        self.descbox.set_usize(370,255)
        self.descbox.set_word_wrap(gtk.TRUE)
        self.descscrl=gtkutil.scrollify(self.descbox)
        gtkutil.defocusify(self.descbox)

        self.itembox=gtk.GtkText()
        self.itembox.set_word_wrap(gtk.TRUE)
        self.itemscrl=gtkutil.scrollify(self.itembox)
        gtkutil.defocusify(self.itembox)

        self.happenings=gtk.GtkText()
        self.happenings.set_word_wrap(gtk.TRUE)
        self.happscrl=gtkutil.scrollify(self.happenings)
        gtkutil.defocusify(self.happenings)
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

        self.cmdarea.connect("key_press_event", self.processKey)
        self.cmdarea.grab_focus()

        self.history = ['']
        self.descriptions={}
        self.items={}
        self.exits=[]

    def connected(self, rem):
        rem.broker.notifyOnDisconnect(self.connectionLost)
        self.remote = rem
        self.show_all()
        self.loginWindow.hide()

    def connectionLost(self):
        self.hide()
        self.loginWindow.show_all()
        self.loginWindow.loginReport("Disconnected from Server.")

    def sendVerb(self, verb):
        self.seeEvent("> "+verb,boldFont)
        self.cmdarea.set_text(verb)
        self.remote.callRemote("execute", verb).addCallbacks(self.finishVerb, self.errorVerb)

    def errorVerb(self, error):
        self.seeEvent(error, boldFont)
        self.finishVerb('')

    def finishVerb(self, result):
        self.cmdarea.set_sensitive(gtk.TRUE)
        self.cmdarea.set_editable(gtk.TRUE)
        self.focus_text()
        self.cmdarea.set_text("")


    def processKey(self, entry, event):
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

    def remote_seeName(self,name):
        self.namelabel.set_text(name)

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

    def remote_request(self,q,d,c):
        ResponseWindow(q,d,c)
        return None

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


def main():
    gw = GameWindow()
    lw = gtkutil.Login(gw.connected, gw,
                       initialUser="guest", initialPassword="guest",
                       initialHostname="localhost", initialService="twisted.reality")
    gw.loginWindow = lw
    lw.show_all()
    gtk.mainloop()
