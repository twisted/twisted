# -*- test-case-name: test_components -*-

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

"""Component architecture for Twisted, based on Zope3 components.

IMPORTANT: In old code the meaning of 'implementing' was too vague. In this
version we will switch to the Zope3 meaning (objects provide interfaces,
if a class implements interfaces that means its *instances* provide them).
However, some methods (e.g. implements()) are confusing because they actually
check if object *provides* an interface. Using the Zope3 API directly is thus
strongly recommended.

TODO: make zope.interface run in 2.2

CHANGES:
1. __adapt__ now uses zope3's semantics, which are slighly different.
2. dunno what happens to persisting adapters. I think it is always on
in zope3, but need to check. For now no special code to deal with it.
3. getComponent will only be called if __conform__ is not present

Removed features from old version:
1. context-based registries.
2. 
"""

# twisted imports
from twisted.python import reflect, util, context
from twisted.persisted import styles

# system imports
import types
import warnings
import weakref

# zope3
from zope.interface import interface, declarations
from zope.interface.adapter import AdapterRegistry as ZopeAdapterRegistry

ALLOW_DUPLICATES = 0

class _Nothing:
    """
    An alternative to None - default value for functions which raise if default not passed.
    """


def getRegistry(r):
    return theAdapterRegistry

class CannotAdapt(NotImplementedError, TypeError):
    """
    Can't adapt some object to some Interface.
    """
    pass

class MetaInterface(interface.InterfaceClass):
    def __call__():
        # Copying evil trick I dinna understand
        def __call__(self, adaptable, default=_Nothing, persist=None, registry=None):
            if registry != None:
                raise RuntimeError, "registry argument will be ignored"
            # possibly should be removed for efficiency reasons
            if persist != None:
                warnings.warn("persist argument is deprecated", DeprecationWarning)
            # XXX does this go away?
            if hasattr(adaptable, "getComponent") and not hasattr(adaptable, "__conform__"):
                warnings.warn("please use __conform__ instead of getComponent", DeprecationWarning)
                return adaptable.getComponent(self)
            if default == _Nothing:
                return interface.InterfaceClass.__call__(self, adaptable)
            else:
                return interface.InterfaceClass.__call__(self, adaptable, alternate=default)
        return __call__
    __call__ = __call__()
    
    def adaptWith(self, using, to, registry=None):
        if registry != None:
            raise RuntimeError, "registry argument will be ignored"
        warnings.warn("persist argument is deprecated", DeprecationWarning)
        registry = theAdapterRegistry
        registry.register([to], self, '', using)

Interface = MetaInterface("Interface", __module__="twisted.python.components")

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
    """Return boolean indicating if obj *provides* the given interface.

    This method checks if object provides, not if it implements. The confusion
    is due to the change in terminology.
    """
    return interfaceClass.providedBy(obj)


def getInterfaces(klass):
    """DEPRECATED. Return list of all interfaces the class implements. Or the object provides.

    This is horrible and stupid. Please use zope.interface.providedBy() or implementedBy().
    """
    warnings.warn("getInterfaces should not be used, use providedBy() or implementedBy()", DeprecationWarning)
    # try to support both classes and instances, giving different behaviour
    # which is HORRIBLE :(
    if isinstance(klass, (type, types.ClassType)):
        return list(declarations.implementedBy(klass))
    else:
        return list(declarations.providedBy(klass))


def superInterfaces(interface):
    """DEPRECATED. Given an interface, return list of super-interfaces (including itself)."""
    warnings.warn("Please use zope.interface APIs", DeprecationWarning)
    result = [interface]
    result.extend(reflect.allYourBase(interface, Interface))
    result = util.uniquify(result)
    result.remove(Interface)
    return result


class _Wrapper(object):
    """Makes any object be able to be dict key."""

    __slots__ = ["a"]

    def __init__(self, a):
        self.a = a


class AdapterRegistry(ZopeAdapterRegistry):

    def __init__(self):
        ZopeAdapterRegistry.__init__(self)
        # we may need to make marker interfaces for class->iface adapters
        # so we store them here:
        self.classInterfaces = {}
    
    def persistAdapter(self, original, iface, adapter):
        self.adapterPersistence[(id(original), iface)] = adapter
        # make sure as long as adapter is alive the original object is alive
        self.adapterOrigPersistence[_Wrapper(original)] = adapter
    
    def registerAdapter(self, adapterFactory, origInterface, *interfaceClasses):
        """Register an adapter class.

        An adapter class is expected to implement the given interface, by
        adapting instances implementing 'origInterface'. An adapter class's
        __init__ method should accept one parameter, an instance implementing
        'origInterface'.
        """
        assert interfaceClasses, "You need to pass an Interface"
        if not issubclass(origInterface, Interface):
            class IMarker(Interface):
                pass
            declarations.directlyProvides(origInterface, IMarker)
            self.classInterfaces[origInterface] = IMarker
            origInterface = IMarker
        self.register(interfaceClasses, origInterface, '', adapterFactory)
    
    def getAdapterFactory(self, fromInterface, toInterface, default):
        """Return registered adapter for a given class and interface.
        """
        if not issubclass(fromInterface, Interface):
            fromInterface = self.classInterfaces[fromInterface]
        # XXX maybe this should just use lookup1 - check!
        return self.get(fromInterface).adapters[False, (), '', toInterface]

    getAdapterClass = getAdapterFactory

    def getAdapterClassWithInheritance(self, klass, interfaceClass, default):
        """Return registered adapter for a given class and interface.
        """
        # XXX
        raise NotImplementedError
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
        for iface in declarations.providedBy(obj):
            factory = self.lookup1(interfaceClass, iface)
            if factory != None:
                return factory(obj)
        if default == _Nothing:
            raise ZeroDivisionError # XXX
        else:
            return default


theAdapterRegistry = AdapterRegistry()
# XXX may need to change to raise correct exceptions
interface.adapter_hooks.append(lambda iface, ob: theAdapterRegistry.getAdapter(ob, iface))
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

    @cvar temporaryAdapter: If this is True, the adapter will not be
          persisted on the Componentized.
    @cvar multiComponent: If this adapter is persistent, should it be
          automatically registered for all appropriate interfaces.
    """

    # These attributes are used with Componentized.

    temporaryAdapter = 0
    multiComponent = 1

    def __init__(self, original):
        """Set my 'original' attribute to be the object I am adapting.
        """
        self.original = original

    def getComponent(self, interface, registry=None, default=None):
        """
        I forward getComponent to self.original if it has it, otherwise I
        simply return default.
        """
        try:
            f = self.original.getComponent
        except AttributeError:
            return default
        else:
            return f(interface, registry=registry, default=default)

    def isuper(self, iface, adapter):
        """
        Forward isuper to self.original
        """
        return self.original.isuper(iface, adapter)

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


class ReprableComponentized(Componentized):
    def __init__(self):
        Componentized.__init__(self)

    def __repr__(self):
        from cStringIO import StringIO
        from pprint import pprint
        sio = StringIO()
        pprint(self._adapterCache, sio)
        return sio.getvalue()

__all__ = ["Interface", "implements", "getInterfaces", "superInterfaces",
           "registerAdapter", "getAdapterClass", "getAdapter", "Componentized",
           "AdapterRegistry", "Adapter", "ReprableComponentized"]
