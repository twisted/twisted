
"""
The new definition of a Twisted interface.

Itamar's z.i integration work so far has focused on providing a backwards
compatibility layer, but we're not using the zope components system, so there
is a pretty big hole in terms of what this new code is capable of without
backwards compatibility.  (No, we are _NOT_ going to use zcml.)

This is a minimalist components system to fill that gap.  The backwards compat
wrappers should be implemented in terms of this.

TODO

"""

import zope.interface.interface as zii
import zope.interface.adapter as zia
import zope.interface as zi

import types

globalRegistry = zia.AdapterRegistry()

class MetaInterface(zii.InterfaceClass):
    def __adapt__(self, adaptee):
        factory = globalRegistry.lookup1(zi.providedBy(adaptee), self, '')
        if factory is not None:
            adapter = factory(adaptee)
            if adapter is not None:
                return adapter
        return zii.InterfaceClass.__adapt__(self, adaptee)

    def __setitem__(self, originalSpec, adapterFactory):
        """Register an adapter to me from a provided interface or type.  For
        example,

                IResource[FooBar] = WebBarAdapter
        """
        if isinstance(originalSpec, type) or isinstance(originalSpec, types.ClassType):
            originalSpec = zi.implementedBy(originalSpec)
        globalRegistry.register(required=[originalSpec], provided=self,
                                name='', value=adapterFactory)

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

if __name__ == '__main__':
    test()
