from math import pi

from twisted.trial import unittest
from zope import interface

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
        ot = octtree.OctTree([0,0,0],
                             20, 20, 20)
        for x in o1, o2, o3:
            ot.add(x)
        objs = list(ot.iternear(o1.position, 5))
        self.failUnless(o1 in objs)
        self.failUnless(o2 in objs)
        self.failIf(o3 in objs)

    def testNearBoundarySearch(self):
        "Make sure the OT does inter-node searches good"
        raise "Write Me"

    def testVisibility(self):
        o1 = Thingy(5,5,5)
        o2 = Thingy(6,6,6)
        o3 = Thingy(3,3,3)

        ot = octtree.OctTree([0,0,0],
                             20, 20, 20)

        ot.iterInPrism(
            # Points defining the quadrilateral closest to the viewer,
            # starting at the top left and proceeding clockwise
            ((-2, 0, 2), (2, 0, 2), (2, 0, -2), (-2, 0, -2)),

            # Points defining the quadrilateral further from the viewer,
            # as above.
            ((-8, 0, 8), (8, 0, 8), (8, 0, -8), (-8, 0, -8)))
