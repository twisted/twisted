# -*- Python -*-

# $Id: spelunk_gnome.py,v 1.1 2001/11/15 23:09:30 acapnotic Exp $

class SillyModule:
    def __init__(self, module, prefix):
        self.__module = module
        self.__prefix = prefix

    def __getattr__(self, attr):
        try:
            return getattr(self.__module, self.__prefix + attr)
        except AttributeError:
            return getattr(self.__module, attr)


# We use gnome.ui because that's what happens to have Python bindings
# for the Canvas.  I think this canvas widget is available seperately
# in "libart", but nobody's given me Python bindings for just that.

# The Gnome canvas is said to be modeled after the Tk canvas, so we
# could probably write this in Tk too.  But my experience is with GTK,
# not with Tk, so this is what I use.

import gnome.ui
gnome = SillyModule(gnome.ui, 'Gnome')

import gtk
(True, False) = (gtk.TRUE, gtk.FALSE)
gtk = SillyModule(gtk, 'Gtk')

from twisted.python import explorer, reflect, text
from twisted.spread import pb

import string, sys, types

_PIXELS_PER_UNIT=10

class SpelunkDisplay(gnome.Canvas):
    faces = None
    def __init__(self, aa=False):
        gnome.Canvas.__init__(self, aa)
        self.set_pixels_per_unit(_PIXELS_PER_UNIT)
        self.faces = {}

class Explorer(pb.RemoteCache):
    # From our cache:
    id = None
    identifier = None

    def newRootItem(self, group):
        klass = spelunkerClassTable.get(self.explorerClass, None)
        if (not klass) or (klass[0] is None):
            print self.explorerClass, "not in table, using generic"
            klass = SpelunkGenericRoot
        else:
            klass = klass[0]
        spelunker = klass(self, group)

        self.give_properties(spelunker)

        for a in self.attributeGroups:
            things = getattr(self, a)
            spelunker.fill_attributeGroup(a, things)

    def newAttributeItem(self, group):
        klass = spelunkerClassTable.get(self.explorerClass, None)
        if (not klass) or (klass[1] is None):
            print self.explorerClass, "not in table, using generic"
            klass = SpelunkGenericAttribute
        else:
            klass = klass[1]

        return klass(self, group)

    def give_properties(self, spelunker):
        """Give a spelunker my properties in an ordered list.
        """
        valuelist = []
        for p in spelunker.propertyLabels.keys():
            value = getattr(self, p, None)
            valuelist.append(value)
        spelunker.fill_properties(valuelist)


class SpelunkRoot(gnome.CanvasGroup):
    color = {'border': '#006644'}
    border_width = 8
    detail_level = 0
    # These are mappings from the strings the code calls these by
    # and the pretty names you want to see on the screen.
    # (e.g. Capitalized or localized)
    propertyLabels = {}
    groupLabels = {}

    def __init__(self, explorer, parentGroup):
        # Ugh.  PyGtk/GtkObject/GnomeCanvas interfacing grits.
        gnome.CanvasGroup.__init__(self,
                                   _obj = parentGroup.add('group')._o)

        self.propertyLabels = {}
        reflect.accumulateClassDict(self.__class__, 'propertyLabels',
                                    self.propertyLabels)
        self.groupLabels = {}
        reflect.accumulateClassDict(self.__class__, 'groupLabels',
                                    self.groupLabels)

        self.explorer = explorer
        self.identifier = explorer.identifier
        self.objectId = explorer.id

        self.parent = parentGroup

        self.ebox = gtk.EventBox()
        self.frame = gtk.Frame(self.identifier)
        self.container = gtk.VBox()
        self.ebox.add(self.frame)
        self.frame.add(self.container)

        self.canvasWidget = self.add('widget', widget=self.ebox,
                                     x=0, y=0, anchor=gtk.ANCHOR_NW,
                                     size_pixels=0)

        self.border = self.add('rect', x1=0, y1=0,
                               x2=1, y2=1,
                               fill_color=None,
                               outline_color=self.color['border'],
                               width_pixels=self.border_width)

        self.subtable = {}

        self._setup_table()

        # TODO:
        #  Collapse me
        #  Destroy me
        #  Set my detail level

        self.frame.connect("size_allocate", self.signal_size_allocate,
                           None)
        self.connect("destroy", self.signal_destroy, None)

        self.ebox.show_all()

        # Our creator will call our fill_ methods when she has the goods.

    def _setup_table(self):

        table = gtk.Table(len(self.explorer.properties), 2)
        self.container.add(table)
        table.set_name("PropertyTable")
        self.subtable['properties'] = table
        row = 0

        for p, name in self.propertyLabels.items():
            label = gtk.Label(name)
            label.set_name("PropertyName")
            label.set_data("property", p)
            table.attach(label, 0, 1, row, row + 1)
            label.set_alignment(0, 0)
            print row, p, name
            row = row + 1

        # XXX: make these guys collapsable
        for g in self.explorer.attributeGroups:
            table = gtk.Table(1, 2)
            self.container.add(table)
            table.set_name("AttributeGroupTable")
            self.subtable[g] = table
            name = self.groupLabels.get(g, g)
            label = gtk.Label(name)
            label.set_name("AttributeGroupTitle")
            table.attach(label, 0, 2, 0, 1)

    def fill_properties(self, propValues):
        table = self.subtable['properties']

        table.resize(len(propValues), 2)

        # XXX: Do I need to destroy previously attached children?

        row = 0
        for value in propValues:
            print "property value", type(value), value
            if type(value) is not types.InstanceType:
                widget = gtk.Label(str(value))
                widget.set_name("PropertyValue")
                widget.set_alignment(0, 0)
            else:
                widget = value.newAttributeItem(self)

            table.attach(widget, 1, 2, row, row+1)
            row = row + 1

        table.show_all()

    def fill_attributeGroup(self, group, attributes):

        # XXX: How to indicate detail level of members?

        table = self.subtable[group]
        if not attributes:
            table.hide()
            return

        table.resize(len(attributes)+1, 2)

        # XXX: Do I need to destroy previously attached children?

        row = 1 # 0 is title

        for name, value in attributes.items():
            label = gtk.Label(name)
            label.set_name("AttributeName")
            label.set_alignment(0, 0)

            if type(value) is types.StringType:
                widget = gtk.Label(value)
                widget.set_name("PropertyValue")
                widget.set_alignment(0, 0)
            else:
                widget = value.newAttributeItem(self)

            table.attach(label, 0, 1, row, row + 1)
            table.attach(widget, 1, 2, row, row + 1)
            row = row + 1

        table.show_all()

    def signal_size_allocate(self, frame_widget,
                             unusable_allocation, unused_data):
        (x, y, w, h) = frame_widget.get_allocation()

        # XXX: allocation PyCObject is apparently unusable!
        # (w, h) = allocation.width, allocation.height

        w, h = (float(w)/_PIXELS_PER_UNIT, float(h)/_PIXELS_PER_UNIT)

        x1, y1 = (self.canvasWidget['x'], self.canvasWidget['y'])

        b = self.border
        (b['x1'], b['y1'], b['x2'], b['y2']) = (x1, y1, x1+w, y1+h)

    def signal_destroy(self, unused_object, unused_data):
        del self.explorer

        del self.canvasWidget
        del self.border

        del self.ebox
        del self.frame
        del self.table

        self.subtable.clear()

class SpelunkAttribute(gtk.Widget):
    def __init__(self, explorer, parentGroup):
        self.explorer = explorer
        self.identifier = explorer.identifier
        self.id = explorer.id

        widgetObj = self._makeWidgetObject()
        gtk.Widget.__init__(self, _obj=widgetObj)
        self.connect("destroy", self.signal_destroy, None)

    def _makeWidgetObject(self):
        widget = gtk.Label(self.identifier)
        widget.set_alignment(0,0)
        return widget._o

    def signal_destroy(self, unused_object, unused_data):
        del self.explorer


class ExplorerInstance(Explorer):
    pass

class SpelunkInstanceRoot(SpelunkRoot):
    # Detail levels:
    # Just me
    # me and my class
    # me and my whole class heirarchy

    propertyLabels = {'klass': "Class"}
    attributeGroups = {'data':"Data",
                       'methods': "Methods"}

    detail = 0

    def __init__(self, explorer, group):
        SpelunkRoot.__init__(self, explorer, group)

        class_identifier = self.explorer.klass.name
        # XXX: include partial module name in class?
        self.frame.set_label("%s (%s) 0x%x" % (self.identifier,
                                               class_identifier,
                                               self.objectId))


class SpelunkInstanceAttribute(SpelunkAttribute):
    def _makeWidgetObject(self):
        widget = gtk.Label("%s instance" % (self.explorer.klass.name))
        widget.set_alignment(0,0)
        return widget._o


class ExplorerClass(Explorer):
    properties = ["bases", "name", "module"]
    attributeGroups = ["data", "methods"]

class SpelunkClassAttribute(SpelunkAttribute):
    def _makeWidgetObject(self):
        widget = gtk.Label(self.explorer.name)
        widget.set_alignment(0,0)
        return widget._o


class ExplorerFunction(Explorer):
    properties = ["name","signature"] # ...

class SpelunkFunctionAttribute(SpelunkAttribute):
    def _makeWidgetObject(self):
        signature = self.explorer.signature
        arglist = []
        for arg in xrange(len(signature)):
            name = signature.name[arg]
            hasDefault, default = signature.get_default(arg)
            if hasDefault:
                if default.explorerClass == "ExplorerImmutable":
                    default = default.value
                else:
                    # XXX
                    pass
                a = "%s=%s" % (name, default)
            elif signature.is_varlist(arg):
                a = "*%s" % (name,)
            elif signature.is_keyword(arg):
                a = "**%s" % (name,)
            else:
                a = name
            arglist.append(a)

        widget = gtk.Label(string.join(arglist, ", "))
        widget.set_alignment(0,0)
        return widget._o

class ExplorerMethod(ExplorerFunction):
    properties = ["class", "self"]

class SpelunkMethodAttribute(SpelunkFunctionAttribute):
    pass

class ExplorerBulitin(Explorer):
    properties = ["name"]

class ExplorerModule(Explorer):
    properties = ["name", "file"] # ...
    pass

class ExplorerSequence(Explorer):
    pass

class SpelunkSequenceAttribute(SpelunkAttribute):
    def _makeWidgetObject(self):
        # XXX: Differentiate between lists and tuples.
        if self.explorer.len:
            widget = gtk.Label("list of length %d" % (self.explorer.len,))
        else:
            widget = gtk.Label("[]")
        widget.set_alignment(0,0)
        return widget._o

class ExplorerMapping(Explorer):
    pass

class SpelunkMappingAttribute(SpelunkAttribute):
    def _makeWidgetObject(self):
        if self.explorer.len:
            widget = gtk.Label("dict with %d elements"
                               % (self.explorer.len,))
        else:
            widget = gtk.Label("{}")
        widget.set_alignment(0,0)
        return widget._o

class ExplorerImmutable(Explorer):
    pass

class SpelunkImmutableAttribute(SpelunkAttribute):
    def _makeWidgetObject(self):
        widget = gtk.Label(repr(self.explorer.value))
        widget.set_alignment(0,0)
        return widget._o

spelunkerClassTable = {
    "ExplorerInstance": (SpelunkInstanceRoot, SpelunkInstanceAttribute),
    "ExplorerFunction": (None, SpelunkFunctionAttribute),
    "ExplorerMethod": (None, SpelunkMethodAttribute),
    "ExplorerImmutable": (None, SpelunkImmutableAttribute),
    "ExplorerClass": (None, SpelunkClassAttribute),
    "ExplorerSequence": (None, SpelunkSequenceAttribute),
    "ExplorerMapping": (None, SpelunkMappingAttribute),
    }
SpelunkGenericRoot = SpelunkRoot
SpelunkGenericAttribute = SpelunkAttribute

pb.setCopierForClassTree(sys.modules[__name__],
                         Explorer, 'twisted.python.explorer')
