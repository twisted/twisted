#!/usr/bin/env python


from twisted.python import components
import zope.interface 


class IHaveAName(components.Interface):
    def getName():
        """returns my name as a string"""

class Foo(object):
    value = 'scrubble'

class GetFoosName(components.Adapter):
    zope.interface.implements(IHaveAName)

    # this is the default constructor for Adapter,
    # i've included it here for clarity
    def __init__(self, original):
        self.original = original

    def getName(self):
        return self.original.value

components.registerAdapter(GetFoosName, Foo, IHaveAName)

def main():
    f = Foo()
    print "f is an instance of %r" % f

    # what happens here is that the component architecture looks to see
    # if someone has registered an adapter from Foo to IHaveAName, it
    # finds GetFoosName, and does
    #
    # return GetFoosName(f)
    #
    haveAName = IHaveAName(f)

    print "haveAName is an instance of %r" % haveAName
    name = haveAName.getName()
    print "name: %s" % name


if __name__ == '__main__':
    main()
