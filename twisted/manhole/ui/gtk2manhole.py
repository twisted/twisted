# -*- Python -*-

"""Manhole client with a GTK v2.x front-end.
"""
# Note: Because GTK 2.x Python bindings are only available for Python 2.2,
# this code may use Python 2.2-isms.

__version__ = '$Revision: 1.3 $'[11:-2]

from twisted import copyright
from twisted.internet import reactor
from twisted.python import components, failure, util
from twisted.spread import pb
from twisted.spread.ui import gtk2util

from twisted.manhole.service import IManholeClient

# The pygtk.require for version 2.0 has already been done by the reactor.
import gtk

import types

# TODO:
#  Make wrap-mode a run-time option.


class ManholeWindow(components.Componentized, gtk2util.GladeKeeper):
    gladefile = util.sibpath(__file__, "gtk2manhole.glade")

    _widgets = ('input','output','manholeWindow')

    def __init__(self):
        self.defaults = {}
        gtk2util.GladeKeeper.__init__(self)
        components.Componentized.__init__(self)

        self.output = ConsoleOutput(self._output)

    def setDefaults(self, defaults):
        self.defaults = defaults

    def login(self):
        client = self.getComponent(IManholeClient)
        d = gtk2util.login(client, **self.defaults)
        d.addCallbacks(self._cbLogin, self._ebLogin)
        d.addCallback(client._cbLogin)

    def _disconnect(self, perspective):
        self.output.append("%s went away. :(\n" % (perspective,), "local")

    def _cbLogin(self, perspective):
        self.output.append("Connected to %s\n" %
                           (perspective.broker.transport.getPeer(),),
                           "local")
        perspective.notifyOnDisconnect(self._disconnect)
        return perspective

    def _ebLogin(self, reason):
        self.output.append("Login FAILED %s\n" % (reason.value,), "exception")
        return None

    def _on_aboutMenuItem_activate(self, widget, *unused):
        from os import path
        self.output.append("""\
a Twisted Manhole client
  Versions:
    %(twistedVer)s
    GTK %(gtkVer)s / PyGTK %(pygtkVer)s
    %(module)s %(modVer)s
http://twistedmatrix.com/
""" % {'twistedVer': copyright.longversion,
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

tagdefs = {
    'default': {"family": "monospace"},
    'stdout': {"foreground": "black"},
    'stderr': {"foreground": "#AA8000"},
    'result': {"foreground": "blue"},
    'exception': {"foreground": "red"},
    'local': {"foreground": "#008000"},
    }


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
    def __init__(self, textView):
        pass

class _Notafile:
    """Curry to make failure.printTraceback work with the output widget."""
    def __init__(self, output, kind):
        self.output = output
        self.kind = kind

    def write(self, txt):
        self.output.append(txt, self.kind)


class ManholeClient(components.Adapter, pb.Referenceable):
    __implements__ = (IManholeClient,)

    capabilities = {
#        "Explorer": 'Set',
        "Failure": 'Set'
        }

    def _cbLogin(self, perspective):
        self.perspective = perspective

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

components.registerAdapter(ManholeClient, ManholeWindow, IManholeClient)
