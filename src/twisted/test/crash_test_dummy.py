
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.


from twisted.python import components
from zope.interface import implements, Interface

def foo():
    return 2

class X:
    def __init__(self, x):
        self.x = x

    def do(self):
        #print 'X',self.x,'doing!'
        pass


class XComponent(components.Componentized):
    pass

class IX(Interface):
    pass

class XA(components.Adapter):
    implements(IX)

    def method(self):
        # Kick start :(
        pass

components.registerAdapter(XA, X, IX)
