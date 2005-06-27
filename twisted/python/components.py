# -*- test-case-name: twisted.test.test_components -*-

# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.


"""Component architecture for Twisted, based on Zope3 components.

Using the Zope3 API directly is strongly recommended. Everything
you need is in the top-level of the zope.interface package, e.g.:

   from zope.interface import Interface, implements

   class IFoo(Interface):
       pass

   class Foo:
       implements(IFoo)

   print IFoo.implementedBy(Foo) # True
   print IFoo.providedBy(Foo()) # True

The one exception is twisted.python.components.registerAdapter, which
is still the way to register adapters (at least, if you want Twisted's
global adapter registry).


Backwards Compatability:

IMPORTANT: In old code the meaning of 'implementing' was too vague. In
this version we will switch to the Zope3 meaning (objects provide
interfaces, if a class implements interfaces that means its
*instances* provide them).  However, some deprecated methods
(e.g. twisted.python.components.implements()) are confusing because
they actually check if object *provides* an interface. Don't use them.

Possible bugs in your code may happen because you rely on
__implements__ existing and/or have only that and assumes that means
the component system knows it implements interfaces. This compat layer
will do its best to make sure that is the case, but sometimes it will
fail on edge cases, and it will always fail if you use zope.interface APIs directly,
e.g. this code will NOT WORK AS EXPECTED:

    from twisted.python.components import implements
    class Foo:
        __implements__ = IFoo,
    IFoo.providedBy(Foo()) # returns False, not True
    implements(Foo(), IFoo) # True! notice meaning of 'implements' changed
    IFoo.providedBy(Foo()) # now returns True, since implements() fixed it

The lesson - just switch all your code to zope.interface, or only use
old APIs. These are slow and will whine a lot. Use zope.interface.
"""

# twisted imports
from twisted.python import reflect, util
from twisted.persisted import styles

# system imports
import sys
import types
import warnings
import weakref

# zope3 imports
try:
    from zope.interface import interface, declarations
    from zope.interface.adapter import AdapterRegistry
except ImportError:
    raise ImportError, "you need zope.interface installed (http://zope.org/Products/ZopeInterface/)"

class ComponentsDeprecationWarning(DeprecationWarning):
    """So you can filter new-components related deprecations easier."""
    pass

# Twisted's global adapter registry
globalRegistry = AdapterRegistry()


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
        # fix up __implements__ if it's old style
        fixClassImplements(origInterface)
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
    fixClassImplements(fromInterface)
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


class _implementsTuple(tuple): pass

def backwardsCompatImplements(klass):
    """Make a class have __implements__, for backwards compatability.

    This allows you to use new zope.interface APIs for declaring
    implements on classes, while still allowing subclasses that
    expect the old API.

       class YourClass:
           zope.interface.implements(IFoo) # correct zope way

       backwardsCompatImplements(YourClass) # add __implements__
       ----

       # someone else still hasn't updated their code:
       
       class ThirdPartyClass(YourClass):
           __implements__ = IBar, YourClass.__implements__

    """
    for subclass in klass.__bases__:
        fixClassImplements(subclass)
    
    _fixedClasses[klass] = True # so fixClassImplements will skip it
    klass.__implements__ = _implementsTuple(declarations.implementedBy(klass))


# WARNING: EXTREME ICKYNESS FOLLOWS
#
# The code beneath this comment is the backwards compatability layer.
# You do not want to read it. You certainly do not want to use it.

class _Nothing:
    """Default value for functions which raise if default not passed.
    """

_fixedClasses = {}
def fixClassImplements(klass):
    """Switch class from __implements__ to zope implementation.

    This does the opposite of backwardsCompatImplements, takes a class
    using __implements__ and makes zope.interface know about it. Rather
    than using this yourself, it's better to port your code to the new
    API.
    """
    if _fixedClasses.has_key(klass):
        return
    if not hasattr(klass, "__implements__"):
        return
    if isinstance(klass.__implements__, _implementsTuple):
        # apparently inhereted from superclass that had backwardsCompatImplements()
        # called on it. if subclass did its own __implements__, this would
        # be a regular tuple, and thus trigger the warning-enabled code branch
        # below, but since it's not, they're probably using new style implements()
        # or didn't change implements from base class at all.
        backwardsCompatImplements(klass)
        return
    if isinstance(klass.__implements__, (tuple, MetaInterface)):
        warnings.warn("Please use implements(), not __implements__ for class %s" % klass, ComponentsDeprecationWarning, stacklevel=3)
        iList = tupleTreeToList(klass.__implements__)
        if iList:
            declarations.classImplementsOnly(klass, *iList)
        _fixedClasses[klass] = 1

ALLOW_DUPLICATES = 0


def getAdapter(obj, interfaceClass, default=_Nothing,
               adapterClassLocator=None, persist=None):
    """DEPRECATED. Return an object that implements the given interface.

    The result will be a wrapper around the object passed as a parameter, or
    the parameter itself if it already implements the interface. If no
    adapter can be found, the 'default' parameter will be returned.

    The recommended way of replacing uses of this function is to use
    IFoo(o), since getAdapter is tied to a specific Twisted registry
    and thus won't interoperate well.
    """
    warnings.warn("components.getAdapter() is deprecated.", ComponentsDeprecationWarning, stacklevel=2)
    if hasattr(obj, '__class__'):
        fixClassImplements(obj.__class__)
    self = globalRegistry
    if interfaceClass.providedBy(obj):
        return obj

    if persist != False:
        pkey = (id(obj), interfaceClass)
        if _adapterPersistence.has_key(pkey):
            return _adapterPersistence[pkey]

    factory = self.lookup1(declarations.providedBy(obj), interfaceClass)
    if factory != None:
        return factory(obj)

    if default == _Nothing:
        raise NotImplementedError
    else:
        return default

getAdapterClass = getAdapterFactory

def getAdapterClassWithInheritance(klass, interfaceClass, default):
    """Return registered adapter for a given class and interface.
    """
    fixClassImplements(klass)
    adapterClass = getAdapterFactory(klass, interfaceClass, _Nothing)
    if adapterClass is _Nothing:
        for baseClass in reflect.allYourBase(klass):
            adapterClass = getAdapterFactory(klass, interfaceClass, _Nothing)
            if adapterClass is not _Nothing:
                return adapterClass
    else:
        return adapterClass
    return default


def getRegistry(r=None):
    return globalRegistry

class CannotAdapt(NotImplementedError, TypeError):
    """
    Can't adapt some object to some Interface.
    """


_adapterPersistence = weakref.WeakValueDictionary()
_adapterOrigPersistence = weakref.WeakValueDictionary()

class MetaInterface(interface.InterfaceClass):

    def __init__(self, name, bases=(), attrs=None, __doc__=None,
                 __module__=None):
        self.__attrs = {}
        if attrs is not None:
            if __module__ == None and attrs.has_key('__module__'):
                __module__ = attrs['__module__']
                del attrs['__module__']
            if __doc__ == None and attrs.has_key('__doc__'):
                __doc__ = attrs['__doc__']
                del attrs['__doc__']
            if attrs.has_key("__adapt__"):
                warnings.warn("Please don't use __adapt__ on Interface subclasses", ComponentsDeprecationWarning, stacklevel=2)
                self.__instadapt__ = attrs["__adapt__"]
                del attrs["__adapt__"]
            for k, v in attrs.items():
                if isinstance(v, types.FunctionType):
                    attrs[k] = interface.fromFunction(v, name, name=k, imlevel=1)
                elif not isinstance(v, interface.Attribute):
                    why = "Please only use functions and zope.interface.Attributes as Interface class attributes (.%s)" % (k,)
                    warnings.warn(why, ComponentsDeprecationWarning, stacklevel=2)
                    self.__attrs[k] = v
                    attrs[k] = interface.Attribute(repr(v))
        # BEHOLD A GREAT EVIL SHALL COME UPON THEE
        if __module__ == None:
            __module__ = sys._getframe(1).f_globals['__name__']
        return interface.InterfaceClass.__init__(self, name, bases, attrs, __doc__, __module__)

    def __call__(self, adaptable, default=_Nothing, persist=None, registry=None):
        if hasattr(adaptable, "__class__"):
            fixClassImplements(adaptable.__class__)
        if registry != None:
            raise RuntimeError, "registry argument will be ignored"
        # getComponents backwards compat
        if hasattr(adaptable, "getComponent") and not hasattr(adaptable, "__conform__") and persist != False:
            warnings.warn("please use __conform__ instead of getComponent in %s" % type(adaptable), ComponentsDeprecationWarning)
            result = adaptable.getComponent(self)
            if result != None:
                return result

        if persist != None:
            warnings.warn("Adapter persistence (e.g. IFoo(bar, persist=True)) is deprecated.", ComponentsDeprecationWarning, stacklevel=2)
        
        # check for weakref persisted adapters
        if persist != False:
            pkey = (id(adaptable), self)
            if _adapterPersistence.has_key(pkey):
                return _adapterPersistence[pkey]

        if persist:
            # we need to recreate the whole z.i.i.Interface.__call__
            # code path here, cause we should only persist stuff
            # that isn't coming from __conform__. Sigh.
            conform = getattr(adaptable, '__conform__', None)
            if conform is not None:
                try:
                    adapter = conform(self)
                except TypeError:
                    if sys.exc_info()[2].tb_next is not None:
                        raise CannotAdapt("%s to %s" % (adaptable, self))
                else:
                    if adapter is not None:
                        return adapter
            adapter = self.__adapt__(adaptable)
            if adapter == None:
                if default == _Nothing:
                    raise CannotAdapt("%s to %s" % (adaptable, self))
                else:
                    return default
            _adapterPersistence[(id(adaptable), self)] = adapter
            # make sure as long as adapter is alive the original object is alive
            _adapterOrigPersistence[_Wrapper(adaptable)] = adapter
            return adapter

        marker = object()
        adapter = interface.InterfaceClass.__call__(self, adaptable, alternate=marker)
        if adapter is marker:
            if hasattr(self, '__instadapt__'):
                adapter = self.__instadapt__(adaptable, default)
            else:
                adapter = default
        if adapter is default and default is _Nothing:
            raise CannotAdapt("%s to %s" % (adaptable, self))
        return adapter
    
    def adaptWith(self, using, to, registry=None):
        if registry != None:
            raise RuntimeError, "registry argument will be ignored"
        warnings.warn("adaptWith is only supported for backwards compatability", ComponentsDeprecationWarning)
        registry = globalRegistry
        registry.register([self], to, '', using)

    def __getattr__(self, attr):
        if attr.startswith("_v_"):
            raise AttributeError # z.i internal thing,
        if attr != "__instadapt__": # __instadapt__ is part of our own backwards compat layer
            warnings.warn("Don't get attributes (in this case, %r) off Interface, use "
                          ".queryDescriptionFor() etc. instead" % (attr,),
                          ComponentsDeprecationWarning, stacklevel=3)
        if self.__attrs.has_key(attr):
            return self.__attrs[attr]
        result = self.queryDescriptionFor(attr)
        if result != None:
            return result
        raise AttributeError, attr


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
    """DEPRECATED. Return boolean indicating if obj *provides* the given interface.

    This method checks if object provides, not if it implements. The confusion
    is due to the change in terminology.
    """
    warnings.warn("Please use providedBy() or implementedBy()", ComponentsDeprecationWarning, stacklevel=2)
    # try to support both classes and instances, which is HORRIBLE
    if isinstance(obj, (type, types.ClassType)):
        fixClassImplements(obj)
        return interfaceClass.implementedBy(obj)
    else:
        fixClassImplements(obj.__class__)
        return interfaceClass.providedBy(obj)


def getInterfaces(klass):
    """DEPRECATED. Return list of all interfaces the class implements. Or the object provides.

    This is horrible and stupid. Please use zope.interface.providedBy() or implementedBy().
    """
    warnings.warn("getInterfaces should not be used, use providedBy() or implementedBy()", ComponentsDeprecationWarning, stacklevel=2)
    # try to support both classes and instances, giving different behaviour
    # which is HORRIBLE :(
    if isinstance(klass, (type, types.ClassType)):
        fixClassImplements(klass)
        l = list(declarations.implementedBy(klass))
    else:
        fixClassImplements(klass.__class__)
        l = list(declarations.providedBy(klass))
    r = []
    for i in l:
        r.extend(superInterfaces(i))
    return util.uniquify(r)


def superInterfaces(interface):
    """DEPRECATED. Given an interface, return list of super-interfaces (including itself)."""
    warnings.warn("Please use zope.interface APIs", ComponentsDeprecationWarning, stacklevel=2)
    result = [interface]
    result.extend(reflect.allYourBase(interface, Interface))
    result = util.uniquify(result)
    if Interface in result:
        result.remove(Interface)
    return result


class _Wrapper(object):
    """Makes any object be able to be dict key."""

    __slots__ = ["a"]

    def __init__(self, a):
        self.a = a


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
        if hasattr(self.original, "__conform__"):
            result = self.original.__conform__(interface)
            if result == None:
                result = default
            return result
        try:
            f = self.original.getComponent
        except AttributeError:
            return default
        else:
            warnings.warn("please use __conform__ instead of getComponent on %r's class" % self.original, ComponentsDeprecationWarning, stacklevel=2)
            return f(interface, registry=registry, default=default)

    def __conform__(self, interface):
        return self.getComponent(interface)
    
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
        return getAdapterClassWithInheritance(klass, interfaceClass, default)

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
        if hasattr(component, "__class__"):
            fixClassImplements(component.__class__)
        self._adapterCache[reflect.qual(interfaceClass)] = component

    def addComponent(self, component, ignoreClass=0, registry=None):
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
        if hasattr(component, "__class__"):
            fixClassImplements(component.__class__)
        for iface in declarations.providedBy(component):
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
        else:
            adapter = interface.__adapt__(self)
            if hasattr(adapter, "__class__"):
                fixClassImplements(adapter.__class__)
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
           "Adapter", "ReprableComponentized", "backwardsCompatImplements",
           "fixClassImplements", "MetaInterface", "getRegistry", "ComponentsDeprecationWarning",
           "globalRegistry"]
