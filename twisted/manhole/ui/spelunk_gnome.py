# -*- Python -*-

# $Id: spelunk_gnome.py,v 1.3 2001/11/19 22:48:23 acapnotic Exp $

# TODO:
#  gzigzag-style navigation

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

import GDK

from twisted.python import explorer, reflect, text
from twisted.spread import pb

import string, sys, types
import UserList
_PIXELS_PER_UNIT=10


class PairList(UserList.UserList):
    """An ordered list of key, value pairs.

    Kinda like an ordered dictionary.  Made with small data sets
    in mind, as get() does a linear search, not hashing.
    """
    def get(self, key):
        i = 0
        for k, v in self.data:
            if key == k:
                return (i, v)
            i = i + 1
        else:
            return (None, None)

    def keys(self):
        return map(lambda x: x[0], self.data)


class SpelunkDisplay(gnome.Canvas):
    """Spelunk widget."""
    def __init__(self, aa=False):
        gnome.Canvas.__init__(self, aa)
        self.set_pixels_per_unit(_PIXELS_PER_UNIT)

    def makeDefaultCanvas(self):
        # Ugh.  For some reason, the 'canvas' and 'parent' properties of
        # CanvasItems aren't accessible thorugh pygnome.
        Explorer.canvas = self


class Explorer(pb.RemoteCache):
    """Base class for all RemoteCaches of explorer.Explorer cachables.

    Meaning that when an Explorer comes back over the wire, one of
    these is created.  From this, you can make a Visage for the
    SpelunkDisplay, or a widget to display as an Attribute.
    """
    canvas = None
    # From our cache:
    id = None
    identifier = None
    explorerClass = None
    attributeGroups = None

    def newVisage(self, group, canvas=None):
        klass = spelunkerClassTable.get(self.explorerClass, None)
        if (not klass) or (klass[0] is None):
            print self.explorerClass, "not in table, using generic"
            klass = GenericVisage
        else:
            klass = klass[0]
        spelunker = klass(self, group, canvas or self.canvas)

        self.give_properties(spelunker)

        for a in spelunker.groupLabels.keys():
            things = getattr(self, a)
            spelunker.fill_attributeGroup(a, things)

        return spelunker

    def newAttributeItem(self, group):
        klass = spelunkerClassTable.get(self.explorerClass, None)
        if (not klass) or (klass[1] is None):
            print self.explorerClass, "not in table, using generic"
            klass = GenericAttribute
        else:
            klass = klass[1]

        return klass(self, group)

    def give_properties(self, spelunker):
        """Give a spelunker my properties in an ordered list.
        """
        valuelist = PairList()
        for p in spelunker.propertyLabels.keys():
            value = getattr(self, p, None)
            valuelist.append((p,value))
        spelunker.fill_properties(valuelist)


class Visage(gnome.CanvasGroup):
    color = {'border': '#006644'}
    border_width = 8
    detail_level = 0
    # These are mappings from the strings the code calls these by
    # and the pretty names you want to see on the screen.
    # (e.g. Capitalized or localized)
    propertyLabels = []
    groupLabels = []

    def __init__(self, explorer, rootGroup, canvas):
        # Ugh.  PyGtk/GtkObject/GnomeCanvas interfacing grits.
        gnome.CanvasGroup.__init__(self,
                                   _obj = rootGroup.add('group')._o)

        self.propertyLabels = PairList()
        reflect.accumulateClassList(self.__class__, 'propertyLabels',
                                    self.propertyLabels)
        self.groupLabels = PairList()
        reflect.accumulateClassList(self.__class__, 'groupLabels',
                                    self.groupLabels)

        self.explorer = explorer
        self.identifier = explorer.identifier
        self.objectId = explorer.id

        self.canvas = canvas
        self.rootGroup = rootGroup

        self.ebox = gtk.EventBox()
        self.ebox.set_name("Visage")
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
        #  Movable/resizeable me
        #  Destroy me
        #  Set my detail level

        self.frame.connect("size_allocate", self.signal_size_allocate,
                           None)
        self.connect("destroy", self.signal_destroy, None)

        self.ebox.show_all()

        # Our creator will call our fill_ methods when she has the goods.

    def _setup_table(self):

        table = gtk.Table(len(self.propertyLabels), 2)
        self.container.add(table)
        table.set_name("PropertyTable")
        self.subtable['properties'] = table
        row = 0

        for p, name in self.propertyLabels:
            label = gtk.Label(name)
            label.set_name("PropertyName")
            label.set_data("property", p)
            table.attach(label, 0, 1, row, row + 1)
            label.set_alignment(0, 0)
            row = row + 1

        # XXX: make these guys collapsable
        for g, name in self.groupLabels:
            table = gtk.Table(1, 2)
            self.container.add(table)
            table.set_name("AttributeGroupTable")
            self.subtable[g] = table
            label = gtk.Label(name)
            label.set_name("AttributeGroupTitle")
            table.attach(label, 0, 2, 0, 1)

    def fill_properties(self, propValues):
        table = self.subtable['properties']

        table.resize(len(propValues), 2)

        # XXX: Do I need to destroy previously attached children?

        for name, value in propValues:
            self.fill_property(name, value)

        table.show_all()

    def fill_property(self, property, value):
        row, name = self.propertyLabels.get(property)
        if type(value) is not types.InstanceType:
            widget = gtk.Label(str(value))
            widget.set_alignment(0, 0)
        else:
            widget = value.newAttributeItem(self)
        widget.set_name("PropertyValue")

        self.subtable['properties'].attach(widget, 1, 2, row, row+1)

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
        del self.container

        self.subtable.clear()

class Attribute(gtk.Widget):
    def __init__(self, explorer, parent):
        self.parent = parent

        self.explorer = explorer
        self.identifier = explorer.identifier
        self.id = explorer.id

        widgetObj = self._makeWidgetObject()
        gtk.Widget.__init__(self, _obj=widgetObj)
        self.set_name("AttributeValue")
        self.connect("destroy", self.signal_destroy, None)
        self.connect("button-press-event", self.signal_buttonPressEvent,
                     None)

    def getTextForLabel(self):
        return self.identifier

    def _makeWidgetObject(self):
        ebox = gtk.EventBox()
        label = gtk.Label(self.getTextForLabel())
        label.set_alignment(0,0)
        ebox.add(label)
        return ebox._o

    def signal_destroy(self, unused_object, unused_data):
        del self.explorer

    def signal_buttonPressEvent(self, widget, eventButton, unused_data):
        if eventButton.type == GDK._2BUTTON_PRESS:
            visage = self.explorer.newVisage(self.parent.rootGroup,
                                             self.parent.canvas)
            (x, y, w, h) = self.get_allocation()
            wx, wy = self.parent.canvas.c2w(x, y)

            x1, y1, x2, y2 = self.parent.get_bounds()

            visage.move(x2, wy + y1)

class ExplorerInstance(Explorer):
    pass

class InstanceVisage(Visage):
    # Detail levels:
    # Just me
    # me and my class
    # me and my whole class heirarchy

    propertyLabels = [('klass', "Class")]
    groupLabels = [('data', "Data"),
                   ('methods', "Methods")]

    detail = 0

    def __init__(self, explorer, group, canvas):
        Visage.__init__(self, explorer, group, canvas)

        class_identifier = self.explorer.klass.name
        # XXX: include partial module name in class?
        self.frame.set_label("%s (%s)" % (self.identifier,
                                          class_identifier))

class InstanceAttribute(Attribute):
    def getTextForLabel(self):
        return "%s instance" % (self.explorer.klass.name,)

class ExplorerClass(Explorer):
    pass

class ClassVisage(Visage):
    propertyLabels = [("name", "Name"),
                      ("module", "Module"),
                      ("bases", "Bases")]
    groupLabels = [('data', "Data"),
                   ('methods', "Methods")]

    def fill_properties(self, propValues):
        Visage.fill_properties(self, propValues)
        basesExplorer = propValues.get('bases')[1]
        basesExplorer.view.get_elements(pbcallback=self.fill_bases)

    def fill_bases(self, baseExplorers):
        box = gtk.HBox()
        for b in baseExplorers:
            box.add(b.newAttributeItem(self))
        row = self.propertyLabels.get('bases')[0]
        self.subtable["properties"].attach(box, 1, 2, row, row+1)
        box.show_all()

class ClassAttribute(Attribute):
    def getTextForLabel(self):
        return self.explorer.name

class ExplorerFunction(Explorer):
    pass

class FunctionAttribute(Attribute):
    def getTextForLabel(self):
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

        return string.join(arglist, ", ")

class ExplorerMethod(ExplorerFunction):
    pass

class MethodAttribute(FunctionAttribute):
    pass

class ExplorerBulitin(Explorer):
    pass

class ExplorerModule(Explorer):
    pass

class ExplorerSequence(Explorer):
    pass

class SequenceVisage(Visage):
    propertyLabels = [('len', 'length')]
    # XXX: add elements group

class SequenceAttribute(Attribute):
    def getTextForLabel(self):
        # XXX: Differentiate between lists and tuples.
        if self.explorer.len:
            txt = "list of length %d" % (self.explorer.len,)
        else:
            txt = "[]"
        return txt

class ExplorerMapping(Explorer):
    pass

class MappingVisage(Visage):
    propertyLabels = [('len', 'length')]
    # XXX: add items group

class MappingAttribute(Attribute):
    def getTextForLabel(self):
        if self.explorer.len:
            txt = "dict with %d elements" % (self.explorer.len,)
        else:
            txt = "{}"
        return txt

class ExplorerImmutable(Explorer):
    pass

class ImmutableVisage(Visage):
    def __init__(self, explorer, rootGroup, canvas):
        Visage.__init__(self, explorer, rootGroup, canvas)
        widget = explorer.newAttributeItem(self)
        self.container.add(widget)
        self.container.show_all()

class ImmutableAttribute(Attribute):
    def getTextForLabel(self):
        return repr(self.explorer.value)

spelunkerClassTable = {
    "ExplorerInstance": (InstanceVisage, InstanceAttribute),
    "ExplorerFunction": (None, FunctionAttribute),
    "ExplorerMethod": (None, MethodAttribute),
    "ExplorerImmutable": (ImmutableVisage, ImmutableAttribute),
    "ExplorerClass": (ClassVisage, ClassAttribute),
    "ExplorerSequence": (SequenceVisage, SequenceAttribute),
    "ExplorerMapping": (MappingVisage, MappingAttribute),
    }
GenericVisage = Visage
GenericAttribute = Attribute

pb.setCopierForClassTree(sys.modules[__name__],
                         Explorer, 'twisted.python.explorer')
