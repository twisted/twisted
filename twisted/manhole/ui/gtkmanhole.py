# -*- Python -*-
# Twisted, the Framework of Your Internet
# $Id: gtkmanhole.py,v 1.33 2002/04/10 12:15:33 itamarst Exp $
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

# TODO:
#  * send script
#  * replace method
#  * save readline history
#  * save-history-as-python
#  * save transcript
#  * identifier completion

import code, string, sys, traceback, types
import gtk

from twisted.python import rebuild, util
from twisted.spread.ui import gtkutil
from twisted.internet import ingtkernet
from twisted.spread import pb
from twisted.manhole import explorer

True = gtk.TRUE
False = gtk.FALSE

try:
    import spelunk_gnome
except ImportError:
    _GNOME_POWER = False
else:
    _GNOME_POWER = True

ingtkernet.install()

rcfile = util.sibpath(__file__, 'gtkrc')
gtk.rc_parse(rcfile)

## def findBeginningOfLineWithPoint(entry):
##     pos = entry.get_point()
##     while pos:
##         pos = pos - 1
##         #print 'looking at',pos
##         c = entry.get_chars(pos, pos+1)
##         #print 'found',repr(c)
##         if c == '\n':
##             #print 'got it!'
##             return pos+1
##     #print 'oops.'
##     return 0

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
        self.set_default_size(300, 300)
        self.set_name("Manhole")

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

        if _GNOME_POWER:
            self.display = BrowserDisplay()
            dWindow = gtk.GtkWindow(title="Spelunking")
            dWindow.add(self.display)
            dWindow.show_all()
            self.display.makeDefaultCanvas()
        else:
            self.display = BrowserDisplay(self)
        # The referencable attached to the Perspective
        self.client = self

        self.remote_console = self.output.console

    def remote_receiveExplorer(self, xplorer):
        if _GNOME_POWER:
            self.display.receiveExplorer(xplorer)
        else:
            XXX # text display?

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


if _GNOME_POWER:
    BrowserDisplay = spelunk_gnome.SpelunkDisplay
else:
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
        previous_kind = None
        style = self.get_style()
        style_cache = {}
        try:
            for element in message:
                if element[0] == 'exception':
                    s = traceback.format_list(element[1]['traceback'])
                    s.extend(element[1]['exception'])
                    s = string.join(s, '')
                else:
                    s = element[1]

                if element[0] != previous_kind:
                    style = style_cache.get(element[0], None)
                    if style is None:
                        gtk.rc_parse_string(
                            'widget \"Manhole.*.Console\" '
                            'style \"Console_%s\"\n'
                            % (element[0]))
                        self.set_rc_style()
                        style_cache[element[0]] = style = self.get_style()
                # XXX: You'd think we'd use style.bg instead of 'None'
                # here, but that doesn't seem to match the color of
                # the backdrop.
                self.insert(style.font, style.fg[gtk.STATE_NORMAL],
                            None, s)
                previous_kind = element[0]
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
            self.set_position(0)

    def historyDown(self):
        if self.histpos < len(self.history) - 1:
            self.histpos = self.histpos + 1
            self.delete_text(0, -1)
            self.insert_defaults(self.history[self.histpos])
        elif self.histpos == len(self.history) - 1:
            self.histpos = self.histpos + 1
            self.delete_text(0, -1)

    def processKey(self, entry, event):
        # TODO: make key bindings easier to customize.

        stopSignal = False
        # ASSUMPTION: Assume Meta == mod4
        isMeta = event.state & gtk.GDK.MOD4_MASK
        if event.keyval == gtk.GDK.Return:
            isShift = event.state & gtk.GDK.SHIFT_MASK
            if isShift:
                self.linemode = True
                self.insert_defaults('\n')
            else:
                stopSignal = True
                text = self.get_chars(0,-1)
                if not text: return
                try:
                    if text[0] == '/':
                        # It's a local-command, don't evaluate it as
                        # Python.
                        c = True
                    else:
                        # This will tell us it's a complete expression.
                        c = code.compile_command(text)
                except SyntaxError, e:
                    # Ding!
                    self.set_positionLineOffset(e.lineno, e.offset)
                    print "offset", e.offset
                    errmsg = {'traceback': [],
                              'exception': [str(e) + '\n']}
                    self.toplevel.output.console([('exception', errmsg)])
                except OverflowError, e:
                    e = traceback.format_exception_only(OverflowError, e)
                    errmsg = {'traceback': [],
                              'exception': e}
                    self.toplevel.output.console([('exception', errmsg)])
                else:
                    if c is None:
                        self.linemode = True
                        stopSignal = False
                    else:
                        self.sendMessage(entry)
                        self.clear()

        elif ((event.keyval == gtk.GDK.Up and isCursorOnFirstLine(self))
              or (isMeta and event.string == 'p')):
            self.historyUp()
            stopSignal = True
        elif ((event.keyval == gtk.GDK.Down and isCursorOnLastLine(self))
              or (isMeta and event.string == 'n')):
            self.historyDown()
            stopSignal = True

        if stopSignal:
            self.emit_stop_by_name("key_press_event")
            return True

    def clear(self):
        self.delete_text(0, -1)
        self.linemode = False

    def set_positionLineOffset(self, line, offset):
        text = self.get_chars(0, -1)
        pos = 0
        for l in xrange(line - 1):
            pos = string.index(text, '\n', pos) + 1
        pos = pos + offset - 1
        self.set_position(pos)

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

        methodName = 'do'

        if text[0] == '/':
            split = string.split(text[1:],' ',1)
            statement = split[0]
            if len(split) == 2:
                remainder = split[1]
            if statement in ('browse', 'explore'):
                methodName = 'explore'
                text = remainder
            elif statement == 'watch':
                methodName = 'watch'
                text = remainder
            elif statement == 'self_rebuild':
                rebuild.rebuild(explorer)
                if _GNOME_POWER:
                    rebuild.rebuild(spelunk_gnome)
                rebuild.rebuild(sys.modules[__name__])
                return
        try:
            self.toplevel.perspective.callRemote(methodName, text)
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

    def readHistoryFile(self, filename=None):
        if filename is None:
            filename = self.historyfile

        f = open(filename, 'r', 1)
        self.history.extend(f.readlines())
        f.close()
        self.histpos = len(self.history)

    def writeHistoryFile(self, filename=None):
        if filename is None:
            filename = self.historyfile

        f = open(filename, 'a', 1)
        f.writelines(self.history)
        f.close()

class Signature(pb.RemoteCopy, explorer.Signature):
    def __init__(self):
        pass

    __str__ = explorer.Signature.__str__

pb.setCopierForClass('twisted.python.explorer.Signature', Signature)
