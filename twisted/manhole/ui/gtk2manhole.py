# -*- Python -*-
# $Id: gtk2manhole.py,v 1.9 2003/09/07 19:58:09 acapnotic Exp $
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

"""Manhole client with a GTK v2.x front-end.
"""
# Note: Because GTK 2.x Python bindings are only available for Python 2.2,
# this code may use Python 2.2-isms.

__version__ = '$Revision: 1.9 $'[11:-2]

from twisted import copyright
from twisted.internet import reactor
from twisted.python import components, failure, log, util
from twisted.spread import pb
from twisted.spread.ui import gtk2util

from twisted.manhole.service import IManholeClient

# The pygtk.require for version 2.0 has already been done by the reactor.
import gtk

import code, types, inspect

# TODO:
#  Make wrap-mode a run-time option.
#  Command history.
#  Explorer.
#  Code doesn't cleanly handle opening a second connection.  Fix that.
#  Make some acknowledgement of when a command has completed, even if
#     it has no return value so it doesn't print anything to the console.

class OfflineError(Exception):
    pass

class ManholeWindow(components.Componentized, gtk2util.GladeKeeper):
    gladefile = util.sibpath(__file__, "gtk2manhole.glade")

    _widgets = ('input','output','manholeWindow')

    def __init__(self):
        self.defaults = {}
        gtk2util.GladeKeeper.__init__(self)
        components.Componentized.__init__(self)

        self.input = ConsoleInput(self._input)
        self.input.toplevel = self
        self.output = ConsoleOutput(self._output)

        # Ugh.  GladeKeeper actually isn't so good for composite objects.
        # I want this connected to the ConsoleInput's handler, not something
        # on this class.
        self._input.connect("key_press_event", self.input._on_key_press_event)

    def setDefaults(self, defaults):
        self.defaults = defaults

    def login(self):
        client = self.getComponent(IManholeClient)
        d = gtk2util.login(client, **self.defaults)
        d.addCallback(self._cbLogin)
        d.addCallback(client._cbLogin)
        d.addErrback(self._ebLogin)

    def _cbDisconnected(self, perspective):
        self.output.append("%s went away. :(\n" % (perspective,), "local")
        self._manholeWindow.set_title("Manhole")

    def _cbLogin(self, perspective):
        peer = perspective.broker.transport.getPeer()
        self.output.append("Connected to %s\n" % (peer,), "local")
        perspective.notifyOnDisconnect(self._cbDisconnected)
        self._manholeWindow.set_title("Manhole - %s:%s" % (peer[1], peer[2]))
        return perspective

    def _ebLogin(self, reason):
        self.output.append("Login FAILED %s\n" % (reason.value,), "exception")

    def _on_aboutMenuItem_activate(self, widget, *unused):
        import sys
        from os import path
        self.output.append("""\
a Twisted Manhole client
  Versions:
    %(twistedVer)s
    Python %(pythonVer)s on %(platform)s
    GTK %(gtkVer)s / PyGTK %(pygtkVer)s
    %(module)s %(modVer)s
http://twistedmatrix.com/
""" % {'twistedVer': copyright.longversion,
       'pythonVer': sys.version.replace('\n', '\n      '),
       'platform': sys.platform,
       'gtkVer': ".".join(map(str, gtk.gtk_version)),
       'pygtkVer': ".".join(map(str, gtk.pygtk_version)),
       'module': path.basename(__file__),
       'modVer': __version__,
       }, "local")

    def _on_openMenuItem_activate(self, widget, userdata=None):
        self.login()

    def _on_manholeWindow_delete_event(self, widget, *unused):
        reactor.stop()

    def _on_quitMenuItem_activate(self, widget, *unused):
        reactor.stop()

    def on_reload_self_activate(self, *unused):
        from twisted.python import rebuild
        rebuild.rebuild(inspect.getmodule(self.__class__))


tagdefs = {
    'default': {"family": "monospace"},
    # These are message types we get from the server.
    'stdout': {"foreground": "black"},
    'stderr': {"foreground": "#AA8000"},
    'result': {"foreground": "blue"},
    'exception': {"foreground": "red"},
    # Messages generate locally.
    'local': {"foreground": "#008000"},
    'log': {"foreground": "#000080"},
    'command': {"foreground": "#666666"},
    }

# TODO: Factor Python console stuff back out to pywidgets.

class ConsoleOutput:
    _willScroll = None
    def __init__(self, textView):
        self.textView = textView
        self.buffer = textView.get_buffer()

        # TODO: Make this a singleton tag table.
        for name, props in tagdefs.iteritems():
            tag = self.buffer.create_tag(name)
            # This can be done in the constructor in newer pygtk (post 1.99.14)
            for k, v in props.iteritems():
                tag.set_property(k, v)

        self.buffer.tag_table.lookup("default").set_priority(0)

        self._captureLocalLog()

    def _captureLocalLog(self):
        return log.startLogging(_Notafile(self, "log"), setStdout=False)

    def append(self, text, kind=None):
        # XXX: It seems weird to have to do this thing with always applying
        # a 'default' tag.  Can't we change the fundamental look instead?
        tags = ["default"]
        if kind is not None:
            tags.append(kind)

        self.buffer.insert_with_tags_by_name(self.buffer.get_end_iter(),
                                             text, *tags)
        # Silly things, the TextView needs to update itself before it knows
        # where the bottom is.
        if self._willScroll is None:
            self._willScroll = gtk.idle_add(self._scrollDown)

    def _scrollDown(self, *unused):
        self.textView.scroll_to_iter(self.buffer.get_end_iter(), 0,
                                     True, 1.0, 1.0)
        self._willScroll = None
        return False


class ConsoleInput:
    toplevel = None
    def __init__(self, textView):
        self.textView=textView

    def _on_key_press_event(self, entry, event):
        stopSignal = False
        if event.keyval == gtk.keysyms.Return:
            buffer = self.textView.get_buffer()
            iter1, iter2 = buffer.get_bounds()
            text = buffer.get_text(iter1, iter2, False)

            # Figure out if that Return meant "next line" or "execute."
            try:
                c = code.compile_command(text)
            except SyntaxError, e:
                # This could conceivably piss you off if the client's python
                # doesn't accept keywords that are known to the manhole's
                # python.
                point = buffer.get_iter_at_line_offset(e.lineno, e.offset)
                buffer.place(point)
                # TODO: Componentize!
                self.toplevel.output.append(str(e), "exception")
            except (OverflowError, ValueError), e:
                self.toplevel.output.append(str(e), "exception")
            else:
                if c is not None:
                    self.sendMessage()
                    # Don't insert Return as a newline in the buffer.
                    entry.emit_stop_by_name("key_press_event")
                    self.clear()
                else:
                    # not a complete code block
                    pass

        return False

    def clear(self):
        buffer = self.textView.get_buffer()
        buffer.delete(*buffer.get_bounds())

    def sendMessage(self):
        buffer = self.textView.get_buffer()
        iter1, iter2 = buffer.get_bounds()
        text = buffer.get_text(iter1, iter2, False)
        # TODO: Componentize better!
        try:
            return self.toplevel.getComponent(IManholeClient).do(text)
        except OfflineError:
            self.toplevel.output.append("Not connected, command not sent.\n",
                                        "exception")


class _Notafile:
    """Curry to make failure.printTraceback work with the output widget."""
    def __init__(self, output, kind):
        self.output = output
        self.kind = kind

    def write(self, txt):
        self.output.append(txt, self.kind)

    def flush(self):
        pass

class ManholeClient(components.Adapter, pb.Referenceable):
    __implements__ = (IManholeClient,)

    capabilities = {
#        "Explorer": 'Set',
        "Failure": 'Set'
        }

    def _cbLogin(self, perspective):
        self.perspective = perspective
        perspective.notifyOnDisconnect(self._cbDisconnected)
        return perspective

    def remote_console(self, messages):
        for kind, content in messages:
            if isinstance(content, types.StringTypes):
                self.original.output.append(content, kind)
            elif (kind == "exception") and isinstance(content, failure.Failure):
                content.printTraceback(_Notafile(self.original.output,
                                                 "exception"))
            else:
                self.original.output.append(str(content), kind)

    def remote_receiveExplorer(self, xplorer):
        pass

    def remote_listCapabilities(self):
        return self.capabilities

    def _cbDisconnected(self, perspective):
        self.perspective = None

    def do(self, text):
        if self.perspective is None:
            raise OfflineError
        return self.perspective.callRemote("do", text)

components.registerAdapter(ManholeClient, ManholeWindow, IManholeClient)
