from twisted.trial import unittest
from zope import interface

import numarray

import octtree

class Thingy:
    interface.implements(octtree.ILocated)
    def __init__(self, x=0, y=0, z=0):
        self.position = (x, y, z)

class OctTreeTest(unittest.TestCase):
    def testTrivialSearch(self):
        o1 = Thingy(x=5, y=5, z=5)
        o2 = Thingy(x=5, y=5, z=6)
        o3 = Thingy(x=5, y=5, z=10)
        # XXX What the heck is center (first arg to OctTree)
        ot = octtree.OctTree(numarray.array([0,0,0], numarray.Int),
                             20, 20, 20)
        for x in o1, o2, o3:
            ot.add(x)
        objs = list(ot.iternear(o1.position, 5))
        self.failUnless(o1 in objs)
        self.failUnless(o2 in objs)
        self.failIf(o3 in objs)

    def testNearBoundarySearch(self):
        "Make sure the OT does inter-node searches good"

    def testVisibility(self):
        o1 = Thingy(5,5,5)
        o2 = Thingy(6,6,6)
        o3 = Thingy(3,3,3)

        ot = octtree.OctTree(None, # XXX
                             20, 20, 20)

        ot.iterInCone(point=(4,4,4), length=10, base=5,
                      angle=angleBetween((4,4,4), o1.position))

