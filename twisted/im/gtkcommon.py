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

import os
from twisted.python import reflect
from twisted.python import util
from twisted.manhole.ui.pywidgets import isCursorOnFirstLine, isCursorOnLastLine

import string
import gtk
from libglade import GladeXML

GLADE_FILE = util.sibpath(__file__, "instancemessenger.glade")
SETTINGS_FILE = os.path.expanduser("~/.InstanceMessenger")

OFFLINE = 0
ONLINE = 1
AWAY = 2

True = gtk.TRUE
False = gtk.FALSE


class InputOutputWindow:
    
    def __init__(self, rootName, inputName, outputName):
        self.xml = openGlade(GLADE_FILE, root=rootName)
        wid = self.xml.get_widget
        self.entry = wid(inputName)
        self.entry.set_word_wrap(gtk.TRUE)
        self.output = wid(outputName)
        self.output.set_word_wrap(gtk.TRUE)
        self.widget = wid(rootName)
        self.history = []
        self.histpos = 0
        self.linemode = True
        self.currentlyVisible = 0
        self.win = None
        autoConnectMethods(self)

    def show(self):
        if not self.currentlyVisible:
            self.win = w = gtk.GtkWindow(gtk.WINDOW_TOPLEVEL)
            w.connect("destroy", self.hidden)
            w.add(self.widget)
            w.set_title(self.getTitle())
            w.show_all()
            self.entry.grab_focus()
            self.currentlyVisible = 1

    def hidden(self, w):
        self.win = None
        w.remove(self.widget)
        self.currentlyVisible = 0

    def handle_key_press_event(self, entry, event):
        stopSignal = False
        # ASSUMPTION: Assume Meta == mod4
        isMeta = event.state & gtk.GDK.MOD4_MASK
        if event.keyval == gtk.GDK.Return:
            isShift = event.state & gtk.GDK.SHIFT_MASK
            if isShift:
                self.linemode = True
                entry.insert_defaults('\n')
            else:
                stopSignal = True
                text = entry.get_chars(0,-1)
                if not text:
                    return
                self.entry.delete_text(0, -1)
                self.linemode = False
                self.sendText(text)
        elif ((event.keyval == gtk.GDK.Up and isCursorOnFirstLine(entry))
              or (isMeta and event.string == 'p')):
            self.historyUp()
            stopSignal = True
        elif ((event.keyval == gtk.GDK.Down and isCursorOnLastLine(entry))
              or (isMeta and event.string == 'n')):
            self.historyDown()
            stopSignal = True

        if stopSignal:
            entry.emit_stop_by_name("key_press_event")
            return True

    def historyUp(self):
        if self.histpos > 0:
            self.histpos = self.histpos - 1
            self.entry.delete_text(0, -1)
            self.entry.insert_defaults(self.history[self.histpos])
            self.entry.set_position(0)

    def historyDown(self):
        if self.histpos < len(self.history) - 1:
            self.histpos = self.histpos + 1
            self.entry.delete_text(0, -1)
            self.entry.insert_defaults(self.history[self.histpos])
        elif self.histpos == len(self.history) - 1:
            self.entry.histpos = self.histpos + 1
            self.entry.delete_text(0, -1)


def createMethodDict(o):
    d = {}
    for base in reflect.allYourBase(o.__class__) + [o.__class__]:
        for n in dir(base):
            m = getattr(o, n)
            #print 'd[%s] = %s' % (n, m)
            d[n] = m
    #print d
    return d

def autoConnectMethods(obj):
    o = createMethodDict(obj)
    #print 'connecting', o
    obj.xml.signal_autoconnect(o)



def openGlade(*args, **kwargs):
    print "opening glade file"
    r = apply(GladeXML, args, kwargs)
    if r._o:
        return r
    else:
        raise IOError("Couldn't open Glade XML: %s; %s" % (args, kwargs))
