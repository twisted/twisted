# -*- Python -*-

__version__ = '$Revision: 1.1 $'[11:-2]

from twisted.python import components, util
from twisted.spread import pb
from twisted.spread.ui import gtk2util

from twisted.manhole.service import IManholeClient

import gtk

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
        self.output.append("I'm going to get you, buddy.")
        d = gtk2util.login(self.getComponent(IManholeClient), **self.defaults)
        d.addCallback(self._cbLogin)
        d.addCallback(self.getComponent(IManholeClient)._cbLogin)

    def _cbLogin(self, perspective):
        self.output.append("Connected to %s" %
                           (perspective.broker.transport.getPeer(),))
        return perspective

    def _on_openMenuItem_activate(self, widget, userdata=None):
        self.login()

class ConsoleOutput:
    def __init__(self, textView):
        self.textView = textView
        self.buffer = textView.get_buffer()

    def append(self, text):
        self.buffer.insert(self.buffer.get_end_iter(), text)

class ManholeClient(components.Adapter, pb.Referenceable):
    __implements__ = (IManholeClient,)
        
    def _cbLogin(self, perspective):
        self.perspective = perspective

    def remote_console(self, messages):
        for kind, content in messages:
            if isinstance(content, (str, unicode)):
                self.original.output.append(content)
            else:
                self.original.output.append(str(content))

    def remote_receiveExplorer(self, xplorer):
        pass
    
components.registerAdapter(ManholeClient, ManholeWindow, IManholeClient)
