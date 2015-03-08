# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.


"""An input/output window for the glade reactor inspector.
"""

import time
import gtk
import gobject
import gtk.glade
from twisted.python.util import sibpath
from twisted.python import reflect

from twisted.manhole.ui import gtk2manhole
from twisted.python.components import Adapter, registerAdapter
from twisted.python import log
from twisted.protocols import policies
from zope.interface import implements, Interface

# the glade file uses stock icons, which requires gnome to be installed
import gnome
version = "$Revision: 1.1 $"[11:-2]
gnome.init("gladereactor Inspector", version)

class ConsoleOutput(gtk2manhole.ConsoleOutput):
    def _captureLocalLog(self):
        self.fobs = log.FileLogObserver(gtk2manhole._Notafile(self, "log"))
        self.fobs.start()

    def stop(self):
        self.fobs.stop()
        del self.fobs

class ConsoleInput(gtk2manhole.ConsoleInput):
    def sendMessage(self):
        buffer = self.textView.get_buffer()
        iter1, iter2 = buffer.get_bounds()
        text = buffer.get_text(iter1, iter2, False)
        self.do(text)

    def do(self, text):
        self.toplevel.do(text)

class INode(Interface):
    """A node in the inspector tree model.
    """

    def __adapt__(adaptable, default):
        if hasattr(adaptable, "__dict__"):
            return InstanceNode(adaptable)
        return AttributesNode(adaptable)

class InspectorNode(Adapter):
    implements(INode)

    def postInit(self, offset, parent, slot):
        self.offset = offset
        self.parent = parent
        self.slot = slot

    def getPath(self):
        L = []
        x = self
        while x.parent is not None:
            L.append(x.offset)
            x = x.parent
        L.reverse()
        return L

    def __getitem__(self, index):
        slot, o = self.get(index)
        n = INode(o, persist=False)
        n.postInit(index, self, slot)
        return n

    def origstr(self):
        return str(self.original)

    def format(self):
        return (self.slot, self.origstr())


class ConstantNode(InspectorNode):
    def __len__(self):
        return 0

class DictionaryNode(InspectorNode):
    def get(self, index):
        L = self.original.items()
        L.sort()
        return L[index]

    def __len__(self):
        return len(self.original)

    def origstr(self):
        return "Dictionary"

class ListNode(InspectorNode):
    def get(self, index):
        return index, self.original[index]

    def origstr(self):
        return "List"

    def __len__(self):
        return len(self.original)

class AttributesNode(InspectorNode):
    def __len__(self):
        return len(dir(self.original))

    def get(self, index):
        L = dir(self.original)
        L.sort()
        return L[index], getattr(self.original, L[index])

class InstanceNode(InspectorNode):
    def __len__(self):
        return len(self.original.__dict__) + 1

    def get(self, index):
        if index == 0:
            if hasattr(self.original, "__class__"):
                v = self.original.__class__
            else:
                v = type(self.original)
            return "__class__", v
        else:
            index -= 1
            L = self.original.__dict__.items()
            L.sort()
            return L[index]

import types

for x in dict, types.DictProxyType:
    registerAdapter(DictionaryNode, x, INode)
for x in list, tuple:
    registerAdapter(ListNode, x, INode)
for x in int, str:
    registerAdapter(ConstantNode, x, INode)


class InspectorTreeModel(gtk.GenericTreeModel):
    def __init__(self, root):
        gtk.GenericTreeModel.__init__(self)
        self.root = INode(root, persist=False)
        self.root.postInit(0, None, 'root')

    def on_get_flags(self):
        return 0

    def on_get_n_columns(self):
        return 1

    def on_get_column_type(self, index):
        return gobject.TYPE_STRING

    def on_get_path(self, node):
        return node.getPath()

    def on_get_iter(self, path):
        x = self.root
        for elem in path:
            x = x[elem]
        return x

    def on_get_value(self, node, column):
        return node.format()[column]

    def on_iter_next(self, node):
        try:
            return node.parent[node.offset + 1]
        except IndexError:
            return None

    def on_iter_children(self, node):
        return node[0]

    def on_iter_has_child(self, node):
        return len(node)

    def on_iter_n_children(self, node):
        return len(node)

    def on_iter_nth_child(self, node, n):
        if node is None:
            return None
        return node[n]

    def on_iter_parent(self, node):
        return node.parent


class Inspectro:
    selected = None
    def __init__(self, o=None):
        self.xml = x = gtk.glade.XML(sibpath(__file__, "inspectro.glade"))
        self.tree_view = x.get_widget("treeview")
        colnames = ["Name", "Value"]
        for i in range(len(colnames)):
            self.tree_view.append_column(
                gtk.TreeViewColumn(
                colnames[i], gtk.CellRendererText(), text=i))
        d = {}
        for m in reflect.prefixedMethods(self, "on_"):
            d[m.im_func.__name__] = m
        self.xml.signal_autoconnect(d)
        if o is not None:
            self.inspect(o)
        self.ns = {'inspect': self.inspect}
        iwidget = x.get_widget('input')
        self.input = ConsoleInput(iwidget)
        self.input.toplevel = self
        iwidget.connect("key_press_event", self.input._on_key_press_event)
        self.output = ConsoleOutput(x.get_widget('output'))

    def select(self, o):
        self.selected = o
        self.ns['it'] = o
        self.xml.get_widget("itname").set_text(repr(o))
        self.xml.get_widget("itpath").set_text("???")

    def inspect(self, o):
        self.model = InspectorTreeModel(o)
        self.tree_view.set_model(self.model)
        self.inspected = o

    def do(self, command):
        filename = '<inspector>'
        try:
            print repr(command)
            try:
                code = compile(command, filename, 'eval')
            except:
                code = compile(command, filename, 'single')
            val = eval(code, self.ns, self.ns)
            if val is not None:
                print repr(val)
            self.ns['_'] = val
        except:
            log.err()

    def on_inspect(self, *a):
        self.inspect(self.selected)

    def on_inspect_new(self, *a):
        Inspectro(self.selected)

    def on_row_activated(self, tv, path, column):
        self.select(self.model.on_get_iter(path).original)


class LoggingProtocol(policies.ProtocolWrapper):
    """Log network traffic."""

    logging = True
    logViewer = None
    
    def __init__(self, *args):
        policies.ProtocolWrapper.__init__(self, *args)
        self.inLog = []
        self.outLog = []

    def write(self, data):
        if self.logging:
            self.outLog.append((time.time(), data))
            if self.logViewer:
                self.logViewer.updateOut(self.outLog[-1])
        policies.ProtocolWrapper.write(self, data)

    def dataReceived(self, data):
        if self.logging:
            self.inLog.append((time.time(), data))
            if self.logViewer:
                self.logViewer.updateIn(self.inLog[-1])
        policies.ProtocolWrapper.dataReceived(self, data)

    def __repr__(self):
        r = "wrapped " + repr(self.wrappedProtocol)
        if self.logging:
            r += " (logging)"
        return r


class LoggingFactory(policies.WrappingFactory):
    """Wrap protocols with logging wrappers."""

    protocol = LoggingProtocol
    logging = True
    
    def buildProtocol(self, addr):
        p = self.protocol(self, self.wrappedFactory.buildProtocol(addr))    
        p.logging = self.logging
        return p

    def __repr__(self):
        r = "wrapped " + repr(self.wrappedFactory)
        if self.logging:
            r += " (logging)"
        return r


class LogViewer:
    """Display log of network traffic."""
    
    def __init__(self, p):
        self.p = p
        vals = [time.time()]
        if p.inLog:
            vals.append(p.inLog[0][0])
        if p.outLog:
            vals.append(p.outLog[0][0])
        self.startTime = min(vals)
        p.logViewer = self
        self.xml = gtk.glade.XML(sibpath(__file__, "logview.glade"))
        self.xml.signal_autoconnect(self)
        self.loglist = self.xml.get_widget("loglist")
        # setup model, connect it to my treeview
        self.model = gtk.ListStore(str, str, str)
        self.loglist.set_model(self.model)
        self.loglist.set_reorderable(1)
        self.loglist.set_headers_clickable(1)
        # self.servers.set_headers_draggable(1)
        # add a column
        for col in [
            gtk.TreeViewColumn('Time',
                               gtk.CellRendererText(),
                               text=0),
            gtk.TreeViewColumn('D',
                               gtk.CellRendererText(),
                               text=1),
            gtk.TreeViewColumn('Data',
                               gtk.CellRendererText(),
                               text=2)]:
            self.loglist.append_column(col)
            col.set_resizable(1)
        r = []
        for t, data in p.inLog:
            r.append(((str(t - self.startTime), "R", repr(data)[1:-1])))
        for t, data in p.outLog:
            r.append(((str(t - self.startTime), "S", repr(data)[1:-1])))
        r.sort()
        for i in r:
            self.model.append(i)
    
    def updateIn(self, (time, data)):
        self.model.append((str(time - self.startTime), "R", repr(data)[1:-1]))

    def updateOut(self, (time, data)):
        self.model.append((str(time - self.startTime), "S", repr(data)[1:-1]))

    def on_logview_destroy(self, w):
        self.p.logViewer = None
        del self.p


def main():
    x = Inspectro()
    x.inspect(x)
    gtk.main()

if __name__ == '__main__':
    import sys
    log.startLogging(sys.stdout)
    main()

