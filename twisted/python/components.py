# -*- test-case-name: twisted.test.test_components -*-

# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.


"""Component architecture for Twisted, based on Zope3 components.

Using the Zope3 API directly is strongly recommended. Everything
you need is in the top-level of the zope.interface package, e.g.::

   from zope.interface import Interface, implements

   class IFoo(Interface):
       pass

   class Foo:
       implements(IFoo)

   print IFoo.implementedBy(Foo) # True
   print IFoo.providedBy(Foo()) # True

The one exception is L{twisted.python.components.registerAdapter}, which is
still the way to register adapters (at least, if you want Twisted's global
adapter registry).
"""

# twisted imports
from twisted.python import reflect
from twisted.persisted import styles

# system imports
import sys
import types
import warnings

# zope3 imports
from zope.interface import interface, declarations
from zope.interface.adapter import AdapterRegistry

class ComponentsDeprecationWarning(DeprecationWarning):
    """So you can filter new-components related deprecations easier."""
    pass

# Twisted's global adapter registry
globalRegistry = AdapterRegistry()

# Attribute that registerAdapter looks at. Is this supposed to be public?
ALLOW_DUPLICATES = 0

def registerAdapter(adapterFactory, origInterface, *interfaceClasses):
    """Register an adapter class.

    An adapter class is expected to implement the given interface, by
    adapting instances implementing 'origInterface'. An adapter class's
    __init__ method should accept one parameter, an instance implementing
    'origInterface'.
    """
    self = globalRegistry
    assert interfaceClasses, "You need to pass an Interface"
    global ALLOW_DUPLICATES

    # deal with class->interface adapters:
    if not isinstance(origInterface, interface.InterfaceClass):
        origInterface = declarations.implementedBy(origInterface)

    for interfaceClass in interfaceClasses:
        factory = self.get(origInterface).selfImplied.get(interfaceClass, {}).get('')
        if (factory and not ALLOW_DUPLICATES):
            raise ValueError("an adapter (%s) was already registered." % (factory, ))
    for interfaceClass in interfaceClasses:
        self.register([origInterface], interfaceClass, '', adapterFactory)


def getAdapterFactory(fromInterface, toInterface, default):
    """Return registered adapter for a given class and interface.

    Note that is tied to the *Twisted* global registry, and will
    thus not find adapters registered elsewhere.
    """
    self = globalRegistry
    if not isinstance(fromInterface, interface.InterfaceClass):
        fromInterface = declarations.implementedBy(fromInterface)
    factory = self.lookup1(fromInterface, toInterface)
    if factory == None:
        factory = default
    return factory


# add global adapter lookup hook for our newly created registry
def _hook(iface, ob, lookup=globalRegistry.lookup1):
    factory = lookup(declarations.providedBy(ob), iface)
    if factory is None:
        return None
    else:
        return factory(ob)
interface.adapter_hooks.append(_hook)


def backwardsCompatImplements(klass):
    """DEPRECATED.

    Does nothing. Previously handled backwards compat from a
    zope.interface using class to a class wanting old twisted
    components interface behaviors.
    """
    warnings.warn("components.backwardsCompatImplements doesn't do anything in Twisted 2.3, stop calling it.", ComponentsDeprecationWarning, stacklevel=2)

def fixClassImplements(klass):
    """DEPRECATED.

    Does nothing. Previously converted class from __implements__ to
    zope implementation.
    """
    warnings.warn("components.fixClassImplements doesn't do anything in Twisted 2.3, stop calling it.", ComponentsDeprecationWarning, stacklevel=2)


def getAdapterClass(klass, interfaceClass, default):
    """DEPRECATEED.
    
    Use getAdapterFactory instead.
    """
    warnings.warn("components.getAdapterClass is deprecated in Twisted 2.3. Use components.getAdapterFactory instead.", ComponentsDeprecationWarning, stacklevel=2)    
    return getAdapterFactory(klass, interfaceClass, default)

def getAdapterClassWithInheritance(klass, interfaceClass, default):
    """DEPRECATEED.
    
    Use getAdapterFactory instead.
    """
    warnings.warn("components.getAdapterClassWithInheritance is deprecated in Twisted 2.3. Use components.getAdapterFactory instead.", ComponentsDeprecationWarning, stacklevel=2)    
    return getAdapterFactory(klass, interfaceClass, default)


def getRegistry(r=None):
    """Returns the Twisted global
    C{zope.interface.adapter.AdapterRegistry} instance.
    """
    if r is not None:
        warnings.warn("components.getRegistry's argument is deprecated in Twisted 2.3 and has been ignored since 2.0.", ComponentsDeprecationWarning, stacklevel=2)
    return globalRegistry

# FIXME: deprecate attribute somehow?
CannotAdapt = TypeError


class _Nothing:
    """Default value for functions which raise if default not passed.
    """

class MetaInterface(interface.InterfaceClass):
    def __init__(self, name, bases=(), attrs=None, __doc__=None,
                 __module__=None):
        if attrs is not None:
            if __module__ == None and attrs.has_key('__module__'):
                __module__ = attrs['__module__']
                del attrs['__module__']
            if __doc__ == None and attrs.has_key('__doc__'):
                __doc__ = attrs['__doc__']
                del attrs['__doc__']

            for k, v in attrs.items():
                if isinstance(v, types.FunctionType):
                    # Look here: the following line is the only useful thing
                    # this function is actually doing. z.i interfaces don't
                    # specify self as the first argument, but t.p.c interfaces
                    # do, so we need to use the imlevel=1 argument.
                    attrs[k] = interface.fromFunction(v, name, name=k, imlevel=1)
                elif not isinstance(v, interface.Attribute):
                    raise interface.InvalidInterface("Concrete attribute, %s" % k)

        # BEHOLD A GREAT EVIL SHALL COME UPON THEE
        if __module__ == None:
            __module__ = sys._getframe(1).f_globals['__name__']
            
        if not __module__.startswith("twisted."):
            # Don't warn for use within twisted, because twisted classes must
            # not be switched to z.i.Interface yet, b/c we forgot to deprecate
            # the "default" kwarg to __call__. Also when t.p.c.Interface is
            # removed, the rest of twisted can be updated simultaneously. But
            # everyone else should just use z.i.Interface directly now.
            warnings.warn("twisted.python.components.Interface is deprecated in Twisted 2.3. Use zope.interface.Interface instead. (also note that you should not use 'self' as the first arg on function decls in z.i.Interfaces).", ComponentsDeprecationWarning, stacklevel=2)

        return interface.InterfaceClass.__init__(self, name, bases, attrs, __doc__, __module__)

    def __call__(self, adaptable, alternate=_Nothing, default=_Nothing):
        if default is not _Nothing:
            warnings.warn("The 'default=' keyword to Interface.__call__ is deprecated in Twisted 2.3. Use a 2nd positional argument instead.", ComponentsDeprecationWarning, stacklevel=2)

            if alternate is not _Nothing:
                raise RuntimeError("Cannot specify both default and alternate to Interface.__call__.")
            alternate = default
        
        if alternate is _Nothing:
            return interface.InterfaceClass.__call__(self, adaptable)
        else:
            return interface.InterfaceClass.__call__(self, adaptable, alternate)


Interface = MetaInterface("Interface", __module__="twisted.python.components")


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

    def __conform__(self, interface):
        """
        I forward __conform__ to self.original if it has it, otherwise I
        simply return None.
        """
        if hasattr(self.original, "__conform__"):
            return self.original.__conform__(interface)
        return None

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

    def locateAdapterClass(self, klass, interfaceClass, default):
        return getAdapterFactory(klass, interfaceClass, default)

    def setAdapter(self, interfaceClass, adapterClass):
        self.setComponent(interfaceClass, adapterClass(self))

    def addAdapter(self, adapterClass, ignoreClass=0):
        """Utility method that calls addComponent.  I take an adapter class and
        instantiate it with myself as the first argument.

        @return: The adapter instantiated.
        """
        adapt = adapterClass(self)
        self.addComponent(adapt, ignoreClass)
        return adapt

    def setComponent(self, interfaceClass, component):
        """
        """
        self._adapterCache[reflect.qual(interfaceClass)] = component

    def addComponent(self, component, ignoreClass=0):
        """
        Add a component to me, for all appropriate interfaces.

        In order to determine which interfaces are appropriate, the component's
        provided interfaces will be scanned.

        If the argument 'ignoreClass' is True, then all interfaces are
        considered appropriate.

        Otherwise, an 'appropriate' interface is one for which its class has
        been registered as an adapter for my class according to the rules of
        getComponent.

        @return: the list of appropriate interfaces
        """
        for iface in declarations.providedBy(component):
            if (ignoreClass or
                (self.locateAdapterClass(self.__class__, iface, None)
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
    
    def getComponent(self, interface, default=None):
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
        else:
            adapter = interface.__adapt__(self)
            if adapter is not None and adapter is not _Nothing and not (
                hasattr(adapter, "temporaryAdapter") and
                adapter.temporaryAdapter):
                self._adapterCache[k] = adapter
                if (hasattr(adapter, "multiComponent") and
                    adapter.multiComponent):
                    self.addComponent(adapter)
            return adapter

    def __conform__(self, interface):
        return self.getComponent(interface)


class ReprableComponentized(Componentized):
    def __init__(self):
        Componentized.__init__(self)

    def __repr__(self):
        from cStringIO import StringIO
        from pprint import pprint
        sio = StringIO()
        pprint(self._adapterCache, sio)
        return sio.getvalue()

__all__ = [
    # Sticking around:
    "ComponentsDeprecationWarning", 
    "registerAdapter", "getAdapterFactory",
    "Adapter", "Componentized", "ReprableComponentized", "getRegistry",

    # Deprecated:
    "Interface", "getAdapterClass", "backwardsCompatImplements",
    "fixClassImplements",
]
