
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

import gtk, string, sys, traceback, types

from twisted.python import explorer, util
from twisted.spread.ui import gtkutil
from twisted.internet import ingtkernet
from twisted.spread import pb
ingtkernet.install()

True = gtk.TRUE
False = gtk.FALSE

rcfile = util.sibpath(__file__, 'gtkrc')
gtk.rc_parse(rcfile)

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

def isCursorOnFirstLine(entry):
    firstnewline = string.find(entry.get_chars(0,-1), '\n')
    if entry.get_point() <= firstnewline or firstnewline == -1:
        return 1

def isCursorOnLastLine(entry):
    if entry.get_point() >= string.rfind(string.rstrip(entry.get_chars(0,-1)), '\n'):
        return 1

class Interaction(gtk.GtkWindow, pb.Referenceable):
    loginWindow = None

    def __init__(self):
        gtk.GtkWindow.__init__(self, gtk.WINDOW_TOPLEVEL)
        self.set_title("Manhole Interaction")
        self['name'] = "Manhole"

        vbox = gtk.GtkVBox()
        pane = gtk.GtkVPaned()

        self.output = OutputConsole(toplevel=self)
        pane.pack1(gtkutil.scrollify(self.output), gtk.TRUE, gtk.FALSE)

        self.input = InputText(toplevel=self)
        pane.pack2(gtkutil.scrollify(self.input), gtk.FALSE, gtk.TRUE)
        vbox.pack_start(pane, 1,1,0)

        self.add(vbox)
        self.input.grab_focus()
        self.signal_connect('destroy', gtk.mainquit, None)

        self.display = BrowserDisplay(self)
        # The referencable attached to the Perspective
        self.client = self
        self.remote_receiveBrowserObject=self.display.receiveBrowserObject
        self.remote_console = self.output.console

    def connected(self, perspective):
        self.loginWindow.hide()
        self.name = self.loginWindow.username.get_text()
        self.hostname = self.loginWindow.hostname.get_text()
        perspective.broker.notifyOnDisconnect(self.connectionLost)
        self.perspective = perspective
        self.show_all()
        self.set_title("Manhole: %s@%s" % (self.name, self.hostname))

    def connectionLost(self, reason=None):
        if not reason:
            reason = "Connection Lost"
        self.loginWindow.loginReport(reason)
        self.hide()
        self.loginWindow.show()


class LineOrientedBrowserDisplay:
    def __init__(self, toplevel=None):
        if toplevel:
            self.toplevel = toplevel

    def receiveBrowserObject(self, obj):
        """Display a browser ObjectLink.
        """
        # This is a stop-gap implementation.  Ideally, everything
        # would be nicely formatted with pretty colours and you could
        # select referenced objects to browse them with
        # browse(selectedLink.identifier)

        if obj.type in map(explorer.typeString, [types.FunctionType,
                                                 types.MethodType]):
            arglist = []
            for arg in obj.value['signature']:
                if arg.has_key('default'):
                    a = "%s=%s" % (arg['name'], arg['default'])
                elif arg.has_key('list'):
                    a = "*%s" % (arg['name'],)
                elif arg.has_key('keywords'):
                    a = "**%s" % (arg['name'],)
                else:
                    a = arg['name']
                arglist.append(a)

            things = ''
            if obj.value.has_key('class'):
                things = "Class: %s\n" % (obj.value['class'],)
            if obj.value.has_key('self'):
                things = things + "Self: %s\n" % (obj.value['self'],)

            s = "%(name)s(%(arglist)s)\n%(things)s\n%(doc)s\n" % {
                'name': obj.value['name'],
                'doc': obj.value['doc'],
                'things': things,
                'arglist': string.join(arglist,", "),
                }
        else:
            s = str(obj) + '\n'

        self.toplevel.output.console([('stdout',s)])

#if _GNOME_POWER:
#    BrowserDisplay = CanvasBrowserDisplay
#else:
BrowserDisplay = LineOrientedBrowserDisplay

class OutputConsole(gtk.GtkText):
    maxBufSz = 10000

    def __init__(self, toplevel=None):
        gtk.GtkText.__init__(self)
        self['name'] = "Console"
        gtkutil.defocusify(self)
        self.set_word_wrap(gtk.TRUE)

        if toplevel:
            self.toplevel = toplevel

    def console(self, message):
        self.set_point(self.get_length())
        self.freeze()
        try:
            for element in message:
                if element[0] == 'exception':
                    s = traceback.format_list(element[1]['traceback'])
                    s.extend(element[1]['exception'])
                    s = string.join(s, '')
                else:
                    s = element[1]
                gtk.rc_parse_string(
                    'widget \"Manhole.*.Console\" style \"Console_%s\"\n'
                    % (element[0]))
                self.set_rc_style()
                style = self.get_style()
                # XXX: You'd think we'd use style.bg instead of 'None'
                # here, but that doesn't seem to match the color of
                # the backdrop.
                self.insert(style.font, style.fg[gtk.STATE_NORMAL],
                            None, s)
            l = self.get_length()
            diff = self.maxBufSz - l
            if diff < 0:
                diff = - diff
                self.delete_text(0,diff)
        finally:
            self.thaw()
        a = self.get_vadjustment()
        a.set_value(a.upper - a.page_size)

class InputText(gtk.GtkText):
    linemode = 0
    blockcount = 0

    def __init__(self, toplevel=None):
        gtk.GtkText.__init__(self)
        self['name'] = 'Input'
        self.set_editable(gtk.TRUE)
        self.connect("key_press_event", self.processKey)
        self.set_word_wrap(gtk.TRUE)

        self.history = []
        self.histpos = 0

        if toplevel:
            self.toplevel = toplevel

    def historyUp(self):
        if self.histpos > 0:
            self.histpos = self.histpos - 1
            self.delete_text(0, -1)
            self.insert_defaults(self.history[self.histpos])
            self.set_point(1)

    def historyDown(self):
        if self.histpos < len(self.history) - 1:
            self.histpos = self.histpos + 1
            self.delete_text(0, -1)
            self.insert_defaults(self.history[self.histpos])
        elif self.histpos == len(self.history) - 1:
            self.histpos = self.histpos + 1
            self.delete_text(0, -1)

    def processKey(self, entry, event):
        stopSignal = False
        if event.keyval == gtk.GDK.Return:
            l = self.get_length()
            # if l is 0, this coredumps gtk ;-)
            if not l:
                self.emit_stop_by_name("key_press_event")
                return True
            lpos = findBeginningOfLineWithPoint(self)
            pt = entry.get_point()
            isShift = event.state & gtk.GDK.SHIFT_MASK
            if (self.get_chars(l-1,-1) == ":"):
                self.linemode = 1
            elif isShift:
                self.linemode = 1
                self.insert_defaults('\n')
            elif (not self.linemode) or (pt == lpos):
                self.sendMessage(entry)
                self.delete_text(0, -1)
                stopSignal = True
                self.linemode = 0
        elif event.keyval == gtk.GDK.Up and isCursorOnFirstLine(self):
            self.historyUp()
            stopSignal = True
        elif event.keyval == gtk.GDK.Down and isCursorOnLastLine(self):
            self.historyDown()
            stopSignal = True

        if stopSignal:
            self.emit_stop_by_name("key_press_event")
            return True

    def sendMessage(self, unused_data=None):
        text = self.get_chars(0,-1)
        if self.linemode:
            self.blockcount = self.blockcount + 1
            fmt = ">>> # begin %s\n%%s\n#end %s\n" % (
                self.blockcount, self.blockcount)
        else:
            fmt = ">>> %s\n"
        self.history.append(text)
        self.histpos = len(self.history)
        self.toplevel.output.console([['command',fmt % text]])

        method = self.toplevel.perspective.do

        split = string.split(text,' ',1)
        if len(split) == 2:
            (statement, remainder) = split
            if statement == 'browse':
                method = self.toplevel.perspective.browse
                text = remainder
            elif statement == 'watch':
                method = self.toplevel.perspective.watch
                text = remainder

        try:
            method(text)
        except pb.ProtocolError:
            # ASSUMPTION: pb.ProtocolError means we lost our connection.
            (eType, eVal, tb) = sys.exc_info()
            del tb
            s = string.join(traceback.format_exception_only(eType, eVal),
                            '')
            self.toplevel.connectionLost(s)
        except:
            traceback.print_exc()
            gtk.mainquit()

class ObjectLink(pb.RemoteCopy, explorer.ObjectLink):
    """RemoteCopy of explorer.ObjectLink"""

    def __init__(self):
        pass

    __str__ = explorer.ObjectLink.__str__

pb.setCopierForClass('twisted.python.explorer.ObjectLink',
                     ObjectLink)
