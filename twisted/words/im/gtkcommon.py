# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.


import os, re

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
        #self.entry.set_word_wrap(gtk.TRUE)
        self.output = wid(outputName)
        #self.output.set_word_wrap(gtk.TRUE)
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
            self.connectid = w.connect("destroy", self.hidden)
            w.add(self.widget)
            w.set_title(self.getTitle())
            w.show_all()
            self.entry.grab_focus()
            self.currentlyVisible = 1

    def hidden(self, w):
        self.win = None
        w.remove(self.widget)
        self.currentlyVisible = 0

    def hide(self):
        if self.currentlyVisible:
            self.win.remove(self.widget)
            self.currentlyVisible = 0
            self.win.disconnect(self.connectid)
            self.win.destroy()


    def handle_key_press_event(self, entry, event):
        stopSignal = False
        # ASSUMPTION: Assume Meta == mod4
        isMeta = event.state & gtk.GDK.MOD4_MASK

        ##
        # Return handling
        ##
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
                self.history.append(text)
                self.histpos = len(self.history)

        ##
        # History handling
        ##
        elif ((event.keyval == gtk.GDK.Up and isCursorOnFirstLine(entry))
              or (isMeta and event.string == 'p')):
            print "history up"
            self.historyUp()
            stopSignal = True
        elif ((event.keyval == gtk.GDK.Down and isCursorOnLastLine(entry))
              or (isMeta and event.string == 'n')):
            print "history down"
            self.historyDown()
            stopSignal = True

        ##
        # Tab Completion
        ##
        elif event.keyval == gtk.GDK.Tab:
            oldpos = entry.get_point()
            word, pos = self.getCurrentWord(entry)
            result = self.tabComplete(word)

            #If there are multiple potential matches, then we spit
            #them out and don't insert a tab, so the user can type
            #a couple more characters and try completing again.
            if len(result) > 1:
                for nick in result:
                    self.output.insert_defaults(nick + " ")
                self.output.insert_defaults('\n')
                stopSignal = True

            elif result: #only happens when len(result) == 1
                entry.freeze()
                entry.delete_text(*pos)
                entry.set_position(pos[0])
                entry.insert_defaults(result[0])
                entry.set_position(oldpos+len(result[0])-len(word))
                entry.thaw()
                stopSignal = True

        if stopSignal:
            entry.emit_stop_by_name("key_press_event")
            return True

    def tabComplete(self, word):
        """Override me to implement tab completion for your window,
        I should return a list of potential matches."""
        return []

    def getCurrentWord(self, entry):
        i = entry.get_point()
        text = entry.get_chars(0,-1)
        word = re.split(r'\s', text)[-1]
        start = string.rfind(text, word)
        end = start+len(word)
        return (word, (start, end))
    
    def historyUp(self):
        if self.histpos > 0:
            self.entry.delete_text(0, -1)
            self.histpos = self.histpos - 1
            self.entry.insert_defaults(self.history[self.histpos])
            self.entry.set_position(0)

    def historyDown(self):
        if self.histpos < len(self.history) - 1:
            self.histpos = self.histpos + 1
            self.entry.delete_text(0, -1)
            self.entry.insert_defaults(self.history[self.histpos])
        elif self.histpos == len(self.history) - 1:
            self.histpos = self.histpos + 1
            self.entry.delete_text(0, -1)


def createMethodDict(o, d=None):
    if d is None:
        d = {}
    for base in reflect.allYourBase(o.__class__) + [o.__class__]:
        for n in dir(base):
            m = getattr(o, n)
            #print 'd[%s] = %s' % (n, m)
            d[n] = m
    #print d
    return d

def autoConnectMethods(*objs):
    o = {}
    for obj in objs:
        createMethodDict(obj, o)
    # print 'connecting', o
    objs[0].xml.signal_autoconnect(o)



def openGlade(*args, **kwargs):
    # print "opening glade file"
    r = GladeXML(*args, **kwargs)
    if r._o:
        return r
    else:
        raise IOError("Couldn't open Glade XML: %s; %s" % (args, kwargs))
