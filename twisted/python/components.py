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


ALLOW_DUPLICATES = 0

class _Nothing:
    """
    An alternative to None - default value for functions which raise if default not passed.
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
        Try to adapt `adaptable' to self; return `default' if it was passed, otherwise
        raise L{CannotAdapt}.
        """
        adapter = default
        registry = getRegistry(registry)
        try:
            # should this be `implements' of some kind?
            if (persist is None or persist) and isinstance(adaptable, Componentized):
                adapter = adaptable.getComponent(self, registry, _Nothing)
            else:
                adapter = registry.getAdapter(adaptable, self, _Nothing)
                if persist:
                    registry.persistAdapter(adaptable, adapter)
        except NotImplementedError:
            if hasattr(self, '__adapt__'):
                adapter = self.__adapt__.im_func(adaptable, _Nothing)

        if adapter is _Nothing:
            raise CannotAdapt("%s cannot be adapted to %s." %
                                      (adaptable, self))
        return adapter


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


def tupleTreeToList(t, l=None):
    """Convert an instance, or tree of tuples, into list."""
    if l is None: l = []
    if isinstance(t, types.TupleType):
        for o in t:
            tupleTreeToList(o, l)
    else:
        l.append(t)
    return l


def implements(obj, interfaceClass):
    """Return boolean indicating if obj implements the given interface."""
    if not hasattr(obj, '__implements__'):
        return 0

    for i in tupleTreeToList(obj.__implements__):
        if issubclass(i, interfaceClass):
            return 1

    return 0


def getInterfaces(obj):
    """Return list of all interfaces a class implements."""
    if not hasattr(obj, '__implements__'):
        return []

    result = []
    for i in tupleTreeToList(obj.__implements__):
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


class AdapterRegistry:

    def __init__(self):
        # mapping between (<class>, <interface>) and <adapter class>
        self.adapterRegistry = {}

    def registerAdapter(self, adapterClass, origClass, *interfaceClasses):
        """Register an adapter class.

        An adapter class is expected to implement the given interface, by
        adapting instances of paramter 'origClass'. An adapter class's
        __init__ method should accept one parameter, an instance of 'origClass'.
        """
        assert interfaceClasses, "You need to pass an Interface"
        global ALLOW_DUPLICATES
        for interfaceClass in interfaceClasses:
            if (self.adapterRegistry.has_key((origClass, interfaceClass))
                and not ALLOW_DUPLICATES):
                raise ValueError(
                    "an adapter (%s) was already registered." % (
                        self.adapterRegistry[(origClass, interfaceClass)]
                    )
                )

            # this may need to be removed
            if not implements(adapterClass, interfaceClass):
                raise ValueError, "%s instances don't implement interface %s" % (adapterClass, interfaceClass)

            if not issubclass(interfaceClass, Interface):
                raise ValueError, "interface %s doesn't inherit from %s" % (interfaceClass, Interface)

            for i in superInterfaces(interfaceClass):
                # don't override already registered adapters for super-interfaces
                if not self.adapterRegistry.has_key((origClass, i)):
                    self.adapterRegistry[(origClass, i)] = adapterClass


    def getAdapterClass(self, klass, interfaceClass, default):
        """Return registered adapter for a given class and interface.
        """
        adapterClass = self.adapterRegistry.get((klass, interfaceClass), _Nothing)
        if adapterClass is _Nothing:
            return default
        else:
            return adapterClass

    def getAdapterClassWithInheritance(self, klass, interfaceClass, default):
        """Return registered adapter for a given class and interface.
        """
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
                   adapterClassLocator=None):
        """Return an object that implements the given interface.

        The result will be a wrapper around the object passed as a paramter, or
        the parameter itself if it already implements the interface. If no
        adapter can be found, the 'default' parameter will be returned.
        """
        if hasattr(obj, '__class__'):
            klas = obj.__class__
        else:
            klas = type(obj)

        if implements(obj, interfaceClass):
            return obj
        adapterClass = ( (adapterClassLocator or self.getAdapterClass)(
            klas, interfaceClass, None) )
        if adapterClass is None:
            if default is _Nothing:
                raise NotImplementedError('%s instance does not implement %s, and '
                                          'there is no registered adapter.' %
                                          (obj, interfaceClass))
            return default
        else:
            return adapterClass(obj)


theAdapterRegistry = AdapterRegistry()
registerAdapter = theAdapterRegistry.registerAdapter
getAdapterClass = theAdapterRegistry.getAdapterClass
getAdapterClassWithInheritance = theAdapterRegistry.getAdapterClassWithInheritance
getAdapter = theAdapterRegistry.getAdapter


class Adapter:
    """I am the default implementation of an Adapter for some interface.

    This docstring contains a limerick, by popular demand::

        Subclassing made Zope and TR
        much harder to work with by far.
            So before you inherit,
            be sure to declare it
        Adapter, not PyObject*
    """

    # These attributes are used with Componentized.

    temporaryAdapter = 0
    # should this adapter be ephemeral?
    multiComponent = 1
    # If this adapter is persistent, should it be automatically registered for
    # all appropriate interfaces when it is loaded?

    def __init__(self, original):
        """Set my 'original' attribute to be the object I am adapting.
        """
        self.original = original

    def getComponent(self, interface, registry=None, default=None):
        """
        I forward getComponent to self.original on the assumption that it is an
        instance of Componentized.
        """
        return self.original.getComponent(interface, registry=None, default=None)

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

    def __init__(self):
        self._adapterCache = {}

    def locateAdapterClass(self, klass, interfaceClass, default, registry=None):
        return getRegistry(registry).getAdapterClassWithInheritance(klass, interfaceClass, default)

    def setAdapter(self, interfaceClass, adapterClass):
        self.setComponent(interfaceClass, adapterClass(self))

    def addAdapter(self, adapterClass, ignoreClass=0, registry=None):
        """Utility method that calls addComponent.  I take an adapter class and
        instantiate it with myself as the first argument.

        Returns the adapter instantiated.
        """
        adapt = adapterClass(self)
        self.addComponent(adapt, ignoreClass, registry)
        return adapt

    def setComponent(self, interfaceClass, component):
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
        Remove the given component from me entirely, for all interfaces which
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
        elif implements(self, interface):
            return self
        else:
            adapter = registry.getAdapter(self, interface, default,
                                          lambda k, ik, d:
                                          self.locateAdapterClass(k, ik, d, registry))
            if adapter is not None and adapter is not _Nothing and not (
                hasattr(adapter, "temporaryAdapter") and
                adapter.temporaryAdapter):
                self._adapterCache[k] = adapter
                if (hasattr(adapter, "multiComponent") and
                    adapter.multiComponent and
                    hasattr(adapter, '__implements__')):
                    self.addComponent(adapter)
            return adapter

    def upgradeToVersion1(self):
        # To let Componentized instances interact correctly with
        # rebuild(), we cannot use class objects as dictionary keys.
        for (k, v) in self._adapterCache.items():
            self._adapterCache[reflect.qual(k)] = v


__all__ = ["Interface", "implements", "getInterfaces", "superInterfaces",
           "registerAdapter", "getAdapterClass", "getAdapter", "Componentized",
           "AdapterRegistry"]
