# -*- Python -*-
# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.


"""Object browser GUI, GnomeCanvas implementation.
"""

from twisted.python import log

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

from twisted.python import reflect, text
from twisted.spread import pb
from twisted.manhole import explorer

import string, sys, types
import UserList
_PIXELS_PER_UNIT=10

#### Support class.

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


#### Public

class SpelunkDisplay(gnome.Canvas):
    """Spelunk widget.

    The top-level widget for this module.  This gtk.Widget is where the
    explorer display will be, and this object is also your interface to
    creating new visages.
    """
    def __init__(self, aa=False):
        gnome.Canvas.__init__(self, aa)
        self.set_pixels_per_unit(_PIXELS_PER_UNIT)
        self.visages = {}

    def makeDefaultCanvas(self):
        """Make myself the default canvas which new visages are created on.
        """
        # XXX: For some reason, the 'canvas' and 'parent' properties
        # of CanvasItems aren't accessible thorugh pygnome.
        Explorer.canvas = self

    def receiveExplorer(self, xplorer):
        if self.visages.has_key(xplorer.id):
            log.msg("Using cached visage for %d" % (xplorer.id, ))
            # Ikk.  Just because we just received this explorer, that
            # doesn't necessarily mean its attributes are fresh.  Fix
            # that, either by having this side pull or the server
            # side push.
            visage = self.visages[xplorer.id]
            #xplorer.give_properties(visage)
            #xplorer.give_attributes(visage)
        else:
            log.msg("Making new visage for %d" % (xplorer.id, ))
            self.visages[xplorer.id] = xplorer.newVisage(self.root(),
                                                         self)

#### Base classes

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
        """Make a new visage for the object I explore.

        Returns a Visage.
        """
        canvas = canvas or self.canvas
        klass = spelunkerClassTable.get(self.explorerClass, None)
        if (not klass) or (klass[0] is None):
            log.msg("%s not in table, using generic" % self.explorerClass)
            klass = GenericVisage
        else:
            klass = klass[0]
        spelunker = klass(self, group, canvas)
        if hasattr(canvas, "visages") \
           and not canvas.visages.has_key(self.id):
            canvas.visages[self.id] = spelunker

        self.give_properties(spelunker)

        self.give_attributes(spelunker)

        return spelunker

    def newAttributeWidget(self, group):
        """Make a new attribute item for my object.

        Returns a gtk.Widget.
        """
        klass = spelunkerClassTable.get(self.explorerClass, None)
        if (not klass) or (klass[1] is None):
            log.msg("%s not in table, using generic" % self.explorerClass)
            klass = GenericAttributeWidget
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

    def give_attributes(self, spelunker):
        for a in spelunker.groupLabels.keys():
            things = getattr(self, a)
            spelunker.fill_attributeGroup(a, things)

class _LooseBoxBorder:
    box = None
    color = 'black'
    width = 1
    def __init__(self, box):
        self.box = box

class LooseBox(gnome.CanvasGroup):
    def __init__(self):
        self.border = _LooseBoxBorder(self)

class Visage(gnome.CanvasGroup):
    """A \"face\" of an object under exploration.

    A Visage is a representation of an object presented to the user.
    The \"face\" in \"interface\".

    'propertyLabels' and 'groupLabels' are lists of (key, name)
    2-ples, with 'key' being the string the property or group is
    denoted by in the code, and 'name' being the pretty human-readable
    string you want me to show on the Visage.  These attributes are
    accumulated from base classes as well.

    I am a gnome.CanvasItem (more specifically, CanvasGroup).
    """
    color = {'border': '#006644'}
    border_width = 8
    detail_level = 0
    # These are mappings from the strings the code calls these by
    # and the pretty names you want to see on the screen.
    # (e.g. Capitalized or localized)
    propertyLabels = []
    groupLabels = []

    drag_x0 = 0
    drag_y0 = 0

    def __init__(self, explorer, rootGroup, canvas):
        """Place a new Visage of an explorer in a canvas group.

        I also need a 'canvas' reference is for certain coordinate
        conversions, and pygnome doesn't give access to my GtkObject's
        .canvas attribute.  :(
        """
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
        self.connect("event", self.signal_event)

        self.ebox.show_all()

        # Our creator will call our fill_ methods when she has the goods.

    def _setup_table(self):
        """Called by __init__ to set up my main table.

        You can easily override me instead of clobbering __init__.
        """

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
        """Fill in values for my properites.

        Takes a list of (name, value) pairs.  'name' should be one of
        the keys in my propertyLabels, and 'value' either an Explorer
        or a string.
        """
        table = self.subtable['properties']

        table.resize(len(propValues), 2)

        # XXX: Do I need to destroy previously attached children?

        for name, value in propValues:
            self.fill_property(name, value)

        table.show_all()

    def fill_property(self, property, value):
        """Set a value for a particular property.

        'property' should be one of the keys in my propertyLabels.
        """
        row, name = self.propertyLabels.get(property)
        if type(value) is not types.InstanceType:
            widget = gtk.Label(str(value))
            widget.set_alignment(0, 0)
        else:
            widget = value.newAttributeWidget(self)
        widget.set_name("PropertyValue")

        self.subtable['properties'].attach(widget, 1, 2, row, row+1)

    def fill_attributeGroup(self, group, attributes):
        """Provide members of an attribute group.

        'group' should be one of the keys in my groupLabels, and
        'attributes' a list of (name, value) pairs, with each value as
        either an Explorer or string.
        """

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
                widget = value.newAttributeWidget(self)

            table.attach(label, 0, 1, row, row + 1)
            table.attach(widget, 1, 2, row, row + 1)
            row = row + 1

        table.show_all()

    def signal_event(self, widget, event=None):
        if not event:
            log.msg("Huh? got event signal with no event.")
            return
        if event.type == GDK.BUTTON_PRESS:
            if event.button == 1:
                self.drag_x0, self.drag_y0 = event.x, event.y
                return True
        elif event.type == GDK.MOTION_NOTIFY:
            if event.state & GDK.BUTTON1_MASK:
                self.move(event.x - self.drag_x0, event.y - self.drag_y0)
                self.drag_x0, self.drag_y0 = event.x, event.y
                return True
        return False

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


class AttributeWidget(gtk.Widget):
    """A widget briefly describing an object.

    This is similar to a Visage, but has far less detail.  This should
    display only essential identifiying information, a gtk.Widget
    suitable for including in a single table cell.

    (gtk.Widgets are used here instead of the more graphically
    pleasing gnome.CanvasItems because I was too lazy to re-write
    gtk.table for the canvas.  A new table widget/item would be great
    though, not only for canvas prettiness, but also because we could
    use one with a mone pythonic API.)

    """
    def __init__(self, explorer, parent):
        """A new AttributeWidget describing an explorer.
        """
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
        """Returns text for my label.

        The default implementation of AttributeWidget is a gtk.Label
        widget.  You may override this method to change the text which
        appears in the label.  However, if you don't want to be a
        label, override _makeWidgetObject instead.
        """
        return self.identifier

    def _makeWidgetObject(self):
        """Make the GTK widget object that is me.

        Called by __init__ to construct the GtkObject I wrap-- the ._o
        member of a pygtk GtkObject.  Isn't subclassing GtkObjects in
        Python fun?
        """
        ebox = gtk.EventBox()
        label = gtk.Label(self.getTextForLabel())
        label.set_alignment(0,0)
        ebox.add(label)
        return ebox._o

    def signal_destroy(self, unused_object, unused_data):
        del self.explorer

    def signal_buttonPressEvent(self, widget, eventButton, unused_data):
        if eventButton.type == GDK._2BUTTON_PRESS:
            if self.parent.canvas.visages.has_key(self.explorer.id):
                visage = self.parent.canvas.visages[self.explorer.id]
            else:
                visage = self.explorer.newVisage(self.parent.rootGroup,
                                                 self.parent.canvas)
            (x, y, w, h) = self.get_allocation()
            wx, wy = self.parent.canvas.c2w(x, y)

            x1, y1, x2, y2 = self.parent.get_bounds()

            v_x1, v_y1, v_x2, v_y2 = visage.get_bounds()

            visage.move(x2 - v_x1, wy + y1 - v_y1)


#### Widget-specific subclasses of Explorer, Visage, and Attribute

# Instance

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

class InstanceAttributeWidget(AttributeWidget):
    def getTextForLabel(self):
        return "%s instance" % (self.explorer.klass.name,)


# Class

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
        basesExplorer.view.callRemote("get_elements").addCallback(self.fill_bases)

    def fill_bases(self, baseExplorers):
        box = gtk.HBox()
        for b in baseExplorers:
            box.add(b.newAttributeWidget(self))
        row = self.propertyLabels.get('bases')[0]
        self.subtable["properties"].attach(box, 1, 2, row, row+1)
        box.show_all()

class ClassAttributeWidget(AttributeWidget):
    def getTextForLabel(self):
        return self.explorer.name


# Function

class ExplorerFunction(Explorer):
    pass

class FunctionAttributeWidget(AttributeWidget):
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


# Method

class ExplorerMethod(ExplorerFunction):
    pass

class MethodAttributeWidget(FunctionAttributeWidget):
    pass

class ExplorerBulitin(Explorer):
    pass

class ExplorerModule(Explorer):
    pass

class ExplorerSequence(Explorer):
    pass


# Sequence

class SequenceVisage(Visage):
    propertyLabels = [('len', 'length')]
    # XXX: add elements group

class SequenceAttributeWidget(AttributeWidget):
    def getTextForLabel(self):
        # XXX: Differentiate between lists and tuples.
        if self.explorer.len:
            txt = "list of length %d" % (self.explorer.len,)
        else:
            txt = "[]"
        return txt


# Mapping

class ExplorerMapping(Explorer):
    pass

class MappingVisage(Visage):
    propertyLabels = [('len', 'length')]
    # XXX: add items group

class MappingAttributeWidget(AttributeWidget):
    def getTextForLabel(self):
        if self.explorer.len:
            txt = "dict with %d elements" % (self.explorer.len,)
        else:
            txt = "{}"
        return txt

class ExplorerImmutable(Explorer):
    pass


# Immutable

class ImmutableVisage(Visage):
    def __init__(self, explorer, rootGroup, canvas):
        Visage.__init__(self, explorer, rootGroup, canvas)
        widget = explorer.newAttributeWidget(self)
        self.container.add(widget)
        self.container.show_all()

class ImmutableAttributeWidget(AttributeWidget):
    def getTextForLabel(self):
        return repr(self.explorer.value)


#### misc. module definitions

spelunkerClassTable = {
    "ExplorerInstance": (InstanceVisage, InstanceAttributeWidget),
    "ExplorerFunction": (None, FunctionAttributeWidget),
    "ExplorerMethod": (None, MethodAttributeWidget),
    "ExplorerImmutable": (ImmutableVisage, ImmutableAttributeWidget),
    "ExplorerClass": (ClassVisage, ClassAttributeWidget),
    "ExplorerSequence": (SequenceVisage, SequenceAttributeWidget),
    "ExplorerMapping": (MappingVisage, MappingAttributeWidget),
    }
GenericVisage = Visage
GenericAttributeWidget = AttributeWidget

pb.setCopierForClassTree(sys.modules[__name__],
                         Explorer, 'twisted.manhole.explorer')
