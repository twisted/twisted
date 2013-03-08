# -*- test-case-name: twisted.manhole.ui.test.test_gtk2manhole -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Manhole client with a GTK v2.x front-end.
"""

__version__ = '$Revision: 1.9 $'[11:-2]

from twisted import copyright
from twisted.internet import reactor
from twisted.python import components, failure, log, util
from twisted.python.reflect import prefixedMethodNames
from twisted.spread import pb
from twisted.spread.ui import gtk2util

from twisted.manhole.service import IManholeClient
from zope.interface import implements

# The pygtk.require for version 2.0 has already been done by the reactor.
import gtk

import code, types, inspect

# TODO:
#  Make wrap-mode a run-time option.
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
        self._manholeWindow.set_title("Manhole - %s" % (peer))
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

class History:
    def __init__(self, maxhist=10000):
        self.ringbuffer = ['']
        self.maxhist = maxhist
        self.histCursor = 0

    def append(self, htext):
        self.ringbuffer.insert(-1, htext)
        if len(self.ringbuffer) > self.maxhist:
            self.ringbuffer.pop(0)
        self.histCursor = len(self.ringbuffer) - 1
        self.ringbuffer[-1] = ''

    def move(self, prevnext=1):
        '''
        Return next/previous item in the history, stopping at top/bottom.
        '''
        hcpn = self.histCursor + prevnext
        if hcpn >= 0 and hcpn < len(self.ringbuffer):
            self.histCursor = hcpn
            return self.ringbuffer[hcpn]
        else:
            return None

    def histup(self, textbuffer):
        if self.histCursor == len(self.ringbuffer) - 1:
            si, ei = textbuffer.get_start_iter(), textbuffer.get_end_iter()
            self.ringbuffer[-1] = textbuffer.get_text(si,ei)
        newtext = self.move(-1)
        if newtext is None:
            return
        textbuffer.set_text(newtext)

    def histdown(self, textbuffer):
        newtext = self.move(1)
        if newtext is None:
            return
        textbuffer.set_text(newtext)


class ConsoleInput:
    toplevel, rkeymap = None, None
    __debug = False

    def __init__(self, textView):
        self.textView=textView
        self.rkeymap = {}
        self.history = History()
        for name in prefixedMethodNames(self.__class__, "key_"):
            keysymName = name.split("_")[-1]
            self.rkeymap[getattr(gtk.keysyms, keysymName)] = keysymName

    def _on_key_press_event(self, entry, event):
        stopSignal = False
        ksym = self.rkeymap.get(event.keyval, None)

        mods = []
        for prefix, mask in [('ctrl', gtk.gdk.CONTROL_MASK), ('shift', gtk.gdk.SHIFT_MASK)]:
            if event.state & mask:
                mods.append(prefix)

        if mods:
            ksym = '_'.join(mods + [ksym])

        if ksym:
            rvalue = getattr(
                self, 'key_%s' % ksym, lambda *a, **kw: None)(entry, event)

        if self.__debug:
            print ksym
        return rvalue

    def getText(self):
        buffer = self.textView.get_buffer()
        iter1, iter2 = buffer.get_bounds()
        text = buffer.get_text(iter1, iter2, False)
        return text

    def setText(self, text):
        self.textView.get_buffer().set_text(text)

    def key_Return(self, entry, event):
        text = self.getText()
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
                self.history.append(text)
                self.clear()
                # entry.emit_stop_by_name("key_press_event")
                return True
            else:
                # not a complete code block
                return False

        return False

    def key_Up(self, entry, event):
        # if I'm at the top, previous history item.
        textbuffer = self.textView.get_buffer()
        if textbuffer.get_iter_at_mark(textbuffer.get_insert()).get_line() == 0:
            self.history.histup(textbuffer)
            return True
        return False

    def key_Down(self, entry, event):
        textbuffer = self.textView.get_buffer()
        if textbuffer.get_iter_at_mark(textbuffer.get_insert()).get_line() == (
            textbuffer.get_line_count() - 1):
            self.history.histdown(textbuffer)
            return True
        return False

    key_ctrl_p = key_Up
    key_ctrl_n = key_Down

    def key_ctrl_shift_F9(self, entry, event):
        if self.__debug:
            import pdb; pdb.set_trace()

    def clear(self):
        buffer = self.textView.get_buffer()
        buffer.delete(*buffer.get_bounds())

    def sendMessage(self):
        buffer = self.textView.get_buffer()
        iter1, iter2 = buffer.get_bounds()
        text = buffer.get_text(iter1, iter2, False)
        self.toplevel.output.append(pythonify(text), 'command')
        # TODO: Componentize better!
        try:
            return self.toplevel.getComponent(IManholeClient).do(text)
        except OfflineError:
            self.toplevel.output.append("Not connected, command not sent.\n",
                                        "exception")


def pythonify(text):
    '''
    Make some text appear as though it was typed in at a Python prompt.
    '''
    lines = text.split('\n')
    lines[0] = '>>> ' + lines[0]
    return '\n... '.join(lines) + '\n'

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
    implements(IManholeClient)

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
