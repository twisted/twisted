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
import reflect, util

from twisted.persisted import styles

# system imports
import types
import warnings


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

    """


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
        result.extend(reflect.allYourBase(i))
    result = util.uniquify(result)
    result.remove(Interface)
    return result

def superInterfaces(interface):
    """Given an interface, return list of super-interfaces (including itself)."""
    result = [interface]
    result.extend(reflect.allYourBase(interface))
    result = util.uniquify(result)
    result.remove(Interface)
    return result


# mapping between (<class>, <interface>) and <adapter class>
adapterRegistry = {}


def registerAdapter(adapterClass, origClass, interfaceClass):
    """Register an adapter class.

    An adapter class is expected to implement the given interface, by
    adapting instances of paramter 'origClass'. An adapter class's
    __init__ method should accept one parameter, an instance of 'origClass'.
    """
    if adapterRegistry.has_key((origClass, interfaceClass)):
        raise ValueError, "an adapter was already registered."

    # this may need to be removed
    if not implements(adapterClass, interfaceClass):
        raise ValueError, "%s instances don't implement interface %s" % (adapterClass, interfaceClass)

    if not issubclass(interfaceClass, Interface):
        raise ValueError, "interface %s doesn't inherit from %s" % (interfaceClass, Interface)

    for i in superInterfaces(interfaceClass):
        # don't override already registered adapters for super-interfaces
        if not adapterRegistry.has_key((origClass, i)):
            adapterRegistry[(origClass, i)] = adapterClass


def getAdapterClass(klass, interfaceClass, default):
    """Return registered adapter for a given class and interface.
    """
    adapterClass = adapterRegistry.get((klass, interfaceClass), _Nothing)
    if adapterClass is _Nothing:
        return default
    else:
        return adapterClass


def getAdapterClassWithInheritance(klass, interfaceClass, default):
    """Return registered adapter for a given class and interface.
    """
    adapterClass = adapterRegistry.get((klass, interfaceClass), _Nothing)
    if adapterClass is _Nothing:
        for baseClass in reflect.allYourBase(klass):
            adapterClass = adapterRegistry.get((baseClass, interfaceClass),
                                               _Nothing)
            if adapterClass is not _Nothing:
                return adapterClass
    else:
        return adapterClass
    return default

class _default: pass

def getAdapter(obj, interfaceClass, default=_default,
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
    adapterClass =  (
        adapterClassLocator or getAdapterClass
                    )(
        klas, interfaceClass, None
                     )
    if adapterClass is None:
        if default is _default:
            raise NotImplementedError('%s instance does not implement %s, and '
                                      'there is no registered adapter.' %
                                      (obj, interfaceClass))
        return default
    else:
        return adapterClass(obj)

class _Nothing:
    pass

class Adapter:
    """I am the default implementation of an Adapter for some interface.

    This docstring contains a limerick, by popular demand.

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

    def getComponent(self, interface):
        """
        I forward getComponent to self.original on the assumption that it is an
        instance of Componentized.
        """
        return self.original.getComponent(interface)

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

    def locateAdapterClass(self, klass, interfaceClass, default):
        return getAdapterClassWithInheritance(klass, interfaceClass, default)

    def setAdapter(self, interfaceClass, adapterClass):
        self.setComponent(interfaceClass, adapterClass(self))

    def addAdapter(self, adapterClass, ignoreClass=0):
        """Utility method that calls addComponent.  I take an adapter class and
        instantiate it with myself as the first argument.
        """
        self.addComponent(adapterClass(self), ignoreClass)

    def setComponent(self, interfaceClass, component):
        self._adapterCache[reflect.qual(interfaceClass)] = component

    def addComponent(self, component, ignoreClass=0):
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
                (self.locateAdapterClass(self.__class__, iface, None)
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

    def getComponent(self, interface):
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
        k = reflect.qual(interface)
        if self._adapterCache.has_key(k):
            return self._adapterCache[k]
        elif implements(self, interface):
            return self
        else:
            adapter = getAdapter(self, interface, None,
                                 self.locateAdapterClass)
            if adapter is not None and not (
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
           "registerAdapter", "getAdapterClass", "getAdapter", "Componentized"]
