# -*- Python -*-

__version__ = '$Revision: 1.2 $'[11:-2]

from twisted.python import components, failure, util
from twisted.spread import pb
from twisted.spread.ui import gtk2util

from twisted.manhole.service import IManholeClient

import gtk

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

    def _on_openMenuItem_activate(self, widget, userdata=None):
        self.output.append("You said open!\n")
        self.login()

tagdefs = {
    'default': {"family": "monospace"},
    'stdout': {"foreground": "black"},
    'stderr': {"foreground": "#AA8000"},
    'result': {"foreground": "blue"},
    'exception': {"foreground": "red"},
    'local': {"foreground": "#008000"},
    }


class ConsoleOutput:
    def __init__(self, textView):
        self.textView = textView
        self.buffer = textView.get_buffer()

        # TODO: Make this a singleton tag table.
        for name, props in tagdefs.iteritems():
            tag = self.buffer.create_tag(name)
            # This can be done in the constructor in newer pygtk.
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
        # where the bottom is.  This probably is hell on many-line updates.
        while gtk.events_pending():
            gtk.main_iteration_do(False)

        self.textView.scroll_to_iter(self.buffer.get_end_iter(), 0,
                                     True, 1.0, 1.0)

class ConsoleInput:
    def __init__(self, textView):
        pass

class Notafile:
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
            if isinstance(content, (str, unicode)):
                self.original.output.append(content, kind)
            elif (kind == "exception") and isinstance(content, failure.Failure):
                content.printTraceback(Notafile(self.original.output,
                                                "exception"))
            else:
                self.original.output.append(str(content), kind)

    def remote_receiveExplorer(self, xplorer):
        pass

    def remote_listCapabilities(self):
        return self.capabilities

components.registerAdapter(ManholeClient, ManholeWindow, IManholeClient)
