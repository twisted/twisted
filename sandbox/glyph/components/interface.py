
"""
The new definition of a Twisted interface.

Itamar's z.i integration work so far has focused on providing a backwards
compatibility layer, but we're not using the zope components system, so there
is a pretty big hole in terms of what this new code is capable of without
backwards compatibility.  (No, we are _NOT_ going to use zcml.)

This is a minimalist components system to fill that gap.  The backwards compat
wrappers should be implemented in terms of this.

"""

import zope.interface.interface as zii
import zope.interface.adapter as zia
import zope.interface as zi

import types

globalRegistry = zia.AdapterRegistry()

def twistedInterfaceAdapterHook(interface, adaptee):
    """A simpler version of Zope's adapter hook; provide a global registry as
    truly global, not accessed through context.
    """
    factory = globalRegistry.lookup1(zi.providedBy(adaptee), interface, '')
    if factory is not None:
        adapter = factory(adaptee)
        if adapter is not None:
            return adapter

zii.adapter_hooks.append(twistedInterfaceAdapterHook)

def registerAdapter(adapterFactory, originalSpec, interface):
    """A convenience function for registering an adapter with Twisted's global
    registry.

    @param adapterFactory: a 1-arg callable which procduces an object that
    implements 'interface'.

    @param originalSpec: An interface, specification, type or class to register
    the adapter *from*.  An instance or implementor of this argument will be
    passed to 'adapterFactory' when adaptation happens.

    @param interface: The interface to adapt to.  adapterFactory must return
    providers of this interface.
    """
    if isinstance(originalSpec, type) or isinstance(originalSpec, types.ClassType):
        originalSpec = zi.implementedBy(originalSpec)
    globalRegistry.register(required=[originalSpec], provided=interface,
                            name='', value=adapterFactory)

class MetaInterface(zii.InterfaceClass):
    def __setitem__(self, originalSpec, adapterFactory):
        """Register an adapter to me from a provided interface or type.  For
        example,

                IResource[FooBar] = WebBarAdapter

        is exactly equivalent to

                registerAdapter(WebBarAdapter, FooBar, IResource)

        This is a convenience syntax to make the order of arguments for
        registerAdapter easier to remember.  You can remember that the above
        syntax has conceptual parity the expression with:

                IResource(FooBar()) # ==> Returns a WebBarAdapter()
        """
        registerAdapter(adapterFactory, originalSpec, self)

Interface = MetaInterface('Interface', __module__=__name__)

def test():
    class ITo(Interface):
        pass

    class IFrom(Interface):
        pass

    class Abstract:
        zi.implements(IFrom)

    def converter(ifromImpl):
        print 'converting impl', ifromImpl
        return 7
    ITo[IFrom] = converter
    # IJ[H] = hToJ
    print ITo(Abstract())
    class Concrete:
        pass

    def mixer(concr):
        print 'mixing concrete', concr
        return 9

    ITo[Concrete] = mixer
    print ITo(Concrete())
    print ITo(7, None)
    ITo[int] = lambda x : 100
    print ITo(7)

if __name__ == '__main__':
    test()
