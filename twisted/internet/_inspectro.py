#!/usr/bin/python2.3

import gtk
import gobject
import gtk.glade
from twisted.python.util import sibpath
from twisted.python import reflect

from twisted.manhole.ui import gtk2manhole
from twisted.python.components import Adapter, Interface, registerAdapter
from twisted.python import log

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
    __implements__ = INode
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
        for index, colname in enumerate(["Name", "Value"]):
            self.tree_view.append_column(
                gtk.TreeViewColumn(
                colname, gtk.CellRendererText(), text=index))
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


def main():
    x = Inspectro()
    x.inspect(x)
    gtk.main()

if __name__ == '__main__':
    import sys
    log.startLogging(sys.stdout)
    main()

