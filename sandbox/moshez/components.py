# -*- test-case-name: twisted.test.test_components -*-

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

"""Component architecture for Twisted."""

# sibling imports
import reflect, util, context

from twisted.persisted import styles

# system imports
import types
import warnings
import weakref


ALLOW_DUPLICATES = 0

class _Nothing:
    """
    An alternative to None - default value for functions which raise if
    default not passed.
    """

class _NoImplementor:
    """
    Same as _Nothing but used by AdapterRegistry.locateComponent
    """

def getRegistry(r):
    if r is None:
        return context.get(AdapterRegistry, theAdapterRegistry)
    else:
        return r

class CannotAdapt(NotImplementedError):
    """
    Can't adapt some object to some Interface.
    """
    pass

class MetaInterface(type):
    def __call__(self, adaptable, default=_Nothing, persist=None, registry=None):
        """
        Try to adapt `adaptable' to self; return `default' if it was passed,
        otherwise raise L{CannotAdapt}.
        """
        return getRegistry(registry).locateComponent(adaptable, self,
                                                     default, persist)


class Interface:
    """Base class for interfaces.

    Interfaces define and document an interface for a class. An interface
    class's name must begin with I, and all its methods should have no
    implementation code.

    Objects that implement an interface should have an attribute __implements__,
    that should be either an Interface subclass or a tuple, or tuple of tuples,
    of such Interface classes.

    A class whose instances implement an interface should list the interfaces
    its instances implement in a class-level __implements__.

    For example::

        | class IAdder(Interface):
        |     'Objects implementing this interface can add objects.'
        |
        |     def add(self, a, b):
        |         'Add two objects together and return the result.'
        |
        | class Adder:
        |
        |     __implements__ = IAdder
        |
        |     def add(self, a, b):
        |         return a + b


    You can call an Interface with a single argument; If the passed object can
    be adapted to the Interface in some way, the adapter will be returned.
    """

    __metaclass__ = MetaInterface

    def adaptWith(self, using, to, registry=None):
        registry = getRegistry(registry)
        registry.registerAdapter(using, self, to)

    adaptWith = classmethod(adaptWith)


class IInterface(Interface):
    pass

MetaInterface.__implements__ = IInterface


def tupleTreeToList(t, l=None):
    """Convert an instance, or tree of tuples, into list."""
    if l is None: l = []
    if isinstance(t, types.TupleType):
        for o in t:
            tupleTreeToList(o, l)
    else:
        l.append(t)
    return l


def getInterfaces(obj, attr='__implements__'):
    """Return list of all interfaces an object implements, using a particular
    attribute name.  For example, if you wish to discover what interfaces a
    class implements directly, pass '__class_implements__' as the attribute
    name.
    """
    if not hasattr(obj, attr):
        return []

    result = []
    for i in tupleTreeToList(getattr(obj,attr,())):
        result.append(i)
        result.extend(reflect.allYourBase(i, Interface))
    result = util.uniquify(result)
    result.remove(Interface)
    return result

def superInterfaces(interface):
    """Given an interface, return list of super-interfaces (including itself)."""
    result = [interface]
    result.extend(reflect.allYourBase(interface, Interface))
    result = util.uniquify(result)
    result.remove(Interface)
    return result

def classToInterfaces(k):
    l = getInterfaces(k)
    l.insert(0, k)
    return l

class _ThingWithTwoSlots(object):
    __slots__ = 'a b'.split()

    def __init__(self, a, b):
        self.a = a
        self.b = b

    def __eq__(self, other):
        return ((self.a is other.a) and
                (self.b is other.b))

    def __hash__(self):
        return hash((id(self.a),self.b))

class AdapterRegistry:

    def __init__(self):
        # mapping between (<class>, <interface>) and <adapter class>
        self.adapterRegistry = {}
        # hack -- initialize with MetaInterface->IInterface
        self.implementsRegistry = {MetaInterface: {IInterface:1}}
        self.autoCached = {MetaInterface:1}
        self.adapterPersistence = weakref.WeakValueDictionary()
        self.registerAdapter(ComponentizeSomethingElse,
                             IPreComponentized, IComponentized)

    def persistAdapter(self, original, iface, adapter):
        self.adapterPersistence[_ThingWithTwoSlots(original, iface)] = adapter

    def registerImplements(self, origInterface, *interfaceClasses):
        assert interfaceClasses, "You need to pass an Interface"
        for interfaceClass in interfaceClasses:
            if not self.implements(interfaceClass, IInterface):
                raise ValueError, "%s is not an interface" % interfaceClass
            d = self.implementsRegistry.setdefault(origInterface, {})
            for i in superInterfaces(interfaceClass):
                d[i] = 1
                for subi in self.implementsRegistry.get(i, ()):
                    d[subi] = 1

    def implements(self, obj, interface):
        klass = getattr(obj, '__class__', type(obj))
        if klass not in self.autoCached:
            self.autoCached[klass] = 1
            implements = tupleTreeToList(getattr(klass, '__implements__', ()))
            if implements:
                self.registerImplements(klass, *implements)
        return interface in self.implementsRegistry.get(klass, ())

    def registerAdapter(self, adapterFactory, origInterface, *interfaceClasses):
        """Register an adapter class.

        An adapter class is expected to implement the given interface, by
        adapting instances implementing 'origInterface'. An adapter class's
        __init__ method should accept one parameter, an instance implementing
        'origInterface'.
        """
        assert interfaceClasses, "You need to pass an Interface"
        global ALLOW_DUPLICATES
        for interfaceClass in interfaceClasses:
            if (self.adapterRegistry.has_key((origInterface, interfaceClass))
                and not ALLOW_DUPLICATES):
                raise ValueError(
                    "an adapter (%s) was already registered." % (
                        self.adapterRegistry[(origInterface, interfaceClass)]
                    )
                )

            if not self.implements(interfaceClass, IInterface):
                raise ValueError, "%s is not an interface" % interfaceClass

            for i in superInterfaces(interfaceClass):
                # don't override already registered adapters for super-interfaces
                if not self.adapterRegistry.has_key((origInterface, i)):
                    self.adapterRegistry[(origInterface, i)] = adapterFactory


    def getAdapterFactory(self, fromInterface, toInterface, default):
        """Return registered adapter for a given class and interface.
        """
        return self.adapterRegistry.get((fromInterface, toInterface), default)

    getAdapterClass = getAdapterFactory

    def getAdapterClassWithInheritance(self, klass, interfaceClass, default):
        """Return registered adapter for a given class and interface.
        """
        #import warnings
        #warnings.warn("You almost certainly want to be "
        #              "using interface->interface adapters. "
        #              "If you do not, modify your desire.",
        #              DeprecationWarning, stacklevel=3)
        adapterClass = self.adapterRegistry.get((klass, interfaceClass), _Nothing)
        if adapterClass is _Nothing:
            for baseClass in reflect.allYourBase(klass):
                adapterClass = self.adapterRegistry.get((baseClass, interfaceClass),
                                                          _Nothing)
                if adapterClass is not _Nothing:
                    return adapterClass
        else:
            return adapterClass
        return default

    def getAdapter(self, obj, interfaceClass, default=_Nothing,
                   adapterClassLocator=None, persist=None):
        """Return an object that implements the given interface.

        The result will be a wrapper around the object passed as a parameter, or
        the parameter itself if it already implements the interface. If no
        adapter can be found, the 'default' parameter will be returned.
        """
        if self.implements(obj, interfaceClass):
            return obj

        if persist != False:
            pkey = _ThingWithTwoSlots(obj, interfaceClass)
            if self.adapterPersistence.has_key(pkey):
                return self.adapterPersistence[pkey]

        klas = getattr(obj, '__class__', type(obj))
        for fromInterface in classToInterfaces(klas):
            adapterFactory = ( (adapterClassLocator or self.getAdapterFactory)(
                fromInterface, interfaceClass, None) )
            if adapterFactory is not None:
                adapter = adapterFactory(obj)
                if persist:
                    self.persistAdapter(obj, interfaceClass, adapter)
                return adapter
        if default is _Nothing:
            raise NotImplementedError('%s instance does not implement %s, and '
                                      'there is no registered adapter.' %
                                      (obj, interfaceClass))
        return default

    def locateComponent(self, adaptable, iface, default=_Nothing, persist=None):
        """
        Try to adapt `adaptable' to iface; return `default' if it was passed,
        otherwise raise L{CannotAdapt}.
        """
        adapter = default
        if self.implements(adaptable, iface):
            return adaptable
        if (persist is None or persist):
            componentized = self.locateComponent(adaptable, IComponentized,
                                                 None, 0)
        if (persist is None or persist) and (componentized is not None):
            adapter = componentized.getComponent(iface, self,
                                                 default=_NoImplementor)
        else:
            adapter = self.getAdapter(adaptable, iface, _NoImplementor,
                                      persist=persist)
        if adapter is _NoImplementor:
            if hasattr(iface, '__adapt__'):
                adapter = iface.__adapt__.im_func(adaptable, default)
            else:
                adapter = default

        if adapter is _Nothing:
            raise CannotAdapt("%s cannot be adapted to %s." %
                              (adaptable, self))
        return adapter


class IPreComponentized(Interface):
    pass

class IComponentized(IPreComponentized):

    def getComponent(self, interface, registry=None, default=None):
        pass


class Adapter:
    """I am the default implementation of an Adapter for some interface.

    This docstring contains a limerick, by popular demand::

        Subclassing made Zope and TR
        much harder to work with by far.
            So before you inherit,
            be sure to declare it
        Adapter, not PyObject*

    @cvar temporaryAdapter: If this is True, the adapter will not be
          persisted on the Componentized.
    @cvar multiComponent: If this adapter is persistent, should it be
          automatically registered for all appropriate interfaces.
    """
    # These attributes are used with Componentized.

    temporaryAdapter = 0
    multiComponent = 1
    __implements__ = IComponentized

    def __init__(self, original):
        """Set my 'original' attribute to be the object I am adapting.
        """
        self.original = original

    def getComponent(self, interface, registry=None, default=None):
        """
        I forward getComponent to self.original on the assumption that it is an
        instance of Componentized.
        """
        return self.original.getComponent(interface, registry=registry,
                                          default=default)


class Componentized(styles.Versioned):
    """I am a mixin to allow you to be adapted in various ways persistently.

    I define a list of persistent adapters.  This is to allow adapter classes
    to store system-specific state, and initialized on demand.  The
    getComponent method implements this.  You must also register adapters for
    this class for the interfaces that you wish to pass to getComponent.

    Many other classes and utilities listed here are present in Zope3; this one
    is specific to Twisted.
    """

    persistenceVersion = 1

    __implements__ = IComponentized

    def __init__(self):
        self._adapterCache = {}


    def locateAdapterClass(self, klass, interfaceClass, default, registry=None):
        return getRegistry(registry).getAdapterClassWithInheritance(klass, interfaceClass, default)

    def setAdapter(self, interfaceClass, adapterClass):
        self.setComponent(interfaceClass, adapterClass(self))

    def addAdapter(self, adapterClass, ignoreClass=0, registry=None):
        """Utility method that calls addComponent.  I take an adapter class and
        instantiate it with myself as the first argument.

        @return: The adapter instantiated.
        """
        adapt = adapterClass(self)
        self.addComponent(adapt, ignoreClass, registry)
        return adapt

    def setComponent(self, interfaceClass, component):
        """
        """
        self._adapterCache[reflect.qual(interfaceClass)] = component

    def addComponent(self, component, ignoreClass=0, registry=None):
        """
        Add a component to me, for all appropriate interfaces.

        In order to determine which interfaces are appropriate, the component's
        __implements__ attribute will be scanned.

        If the argument 'ignoreClass' is True, then all interfaces are
        considered appropriate.

        Otherwise, an 'appropriate' interface is one for which its class has
        been registered as an adapter for my class according to the rules of
        getComponent.

        @return: the list of appropriate interfaces
        """
        for iface in tupleTreeToList(component.__implements__):
            if (ignoreClass or
                (self.locateAdapterClass(self.__class__, iface, None, registry)
                 == component.__class__)):
                self._adapterCache[reflect.qual(iface)] = component
        
    def unsetComponent(self, interfaceClass):
        """Remove my component specified by the given interface class."""
        del self._adapterCache[reflect.qual(interfaceClass)]

    def removeComponent(self, component):
        """
        Remove the given component from me entirely, for all interfaces for which
        it has been registered.

        @return: a list of the interfaces that were removed.
        """
        if (isinstance(component, types.ClassType) or
            isinstance(component, types.TypeType)):
            warnings.warn("passing interface to removeComponent, you probably want unsetComponent", DeprecationWarning, 1)
            self.unsetComponent(component)
            return [component]
        l = []
        for k, v in self._adapterCache.items():
            if v is component:
                del self._adapterCache[k]
                l.append(reflect.namedObject(k))
        return l

    def getComponent(self, interface, registry=None, default=None):
        """Create or retrieve an adapter for the given interface.

        If such an adapter has already been created, retrieve it from the cache
        that this instance keeps of all its adapters.  Adapters created through
        this mechanism may safely store system-specific state.

        If you want to register an adapter that will be created through
        getComponent, but you don't require (or don't want) your adapter to be
        cached and kept alive for the lifetime of this Componentized object,
        set the attribute 'temporaryAdapter' to True on your adapter class.

        If you want to automatically register an adapter for all appropriate
        interfaces (with addComponent), set the attribute 'multiComponent' to
        True on your adapter class.
        """
        registry = getRegistry(registry)
        k = reflect.qual(interface)
        if self._adapterCache.has_key(k):
            return self._adapterCache[k]
        elif registry.implements(self, interface):
            return self
        else:
            adapter = registry.getAdapter(self, interface, default,
                                          lambda k, ik, d:
                                          self.locateAdapterClass(k, ik, d, registry))
            if adapter is not None and adapter is not _Nothing and not (
                getattr(adapter, "temporaryAdapter", None)):
                self._adapterCache[k] = adapter
                if (getattr(adapter, "multiComponent", None) and
                    hasattr(adapter, '__implements__')):
                    self.addComponent(adapter)
            return adapter

    def upgradeToVersion1(self):
        # To let Componentized instances interact correctly with
        # rebuild(), we cannot use class objects as dictionary keys.
        for (k, v) in self._adapterCache.items():
            self._adapterCache[reflect.qual(k)] = v

class PreComponentized:

    __implements__ = IPreComponentized

    def __init__(self):
        self._adapterCache = {}


class ComponentizeSomethingElse(Componentized):

    __implements__ = IComponentized

    def __init__(self, original):
        self._adapterCache = original._adapterCache
        self.orig_class = original.__class__

    def addComponent(self, component, ignoreClass=0, registry=None):
        for iface in tupleTreeToList(component.__implements__):
            if (ignoreClass or
                (self.locateAdapterClass(self.orig_class, iface, None, registry)
                 == component.__class__)):
                self._adapterCache[reflect.qual(iface)] = component




theAdapterRegistry = AdapterRegistry()
registerAdapter = theAdapterRegistry.registerAdapter
getAdapterClass = theAdapterRegistry.getAdapterClass
getAdapterClassWithInheritance = theAdapterRegistry.getAdapterClassWithInheritance
getAdapter = theAdapterRegistry.getAdapter
implements = theAdapterRegistry.implements
registerImplements = theAdapterRegistry.registerImplements

__all__ = ["Interface", "implements", "getInterfaces", "superInterfaces",
           "registerAdapter", "getAdapterClass", "getAdapter", "Componentized",
           "AdapterRegistry"]
