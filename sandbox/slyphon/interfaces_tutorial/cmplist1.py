#!/usr/bin/env python


from twisted.python import components
import zope.interface 


class IHaveAName(zope.interface.Interface):
    def getName():
        """returns my name as a string"""

class Foo(object):
    value = 'scrubble'

class GetFoosName(object):
    zope.interface.implements(IHaveAName)

    # this is the constructor for an adapter,
    # if you want a class to act as an adapter, it must take
    # a single argument, and assign that argument to the
    # instance attribute self.original
    def __init__(self, original):
        self.original = original

    def getName(self):
        return self.original.value

components.registerAdapter(GetFoosName, Foo, IHaveAName)

def main():
    f = Foo()
    print "repr(f) %r" % f

    # what happens here is that the component architecture looks to see
    # if someone has registered an adapter from Foo to IHaveAName, it
    # finds GetFoosName, and does
    #
    # return GetFoosName(f)
    #
    haveAName = IHaveAName(f)

    print "repr(haveAName): %r" % haveAName

    print "repr(haveAName.original): %r" % haveAName.original

    print "haveAName.original is f: %s" % (haveAName.original is f)

    name = haveAName.getName()
    print "name: %s" % name


if __name__ == '__main__':
    main()
