from math import pi, cos

from twisted.trial import unittest
from zope import interface
from numarray import array

import octtree

class Thingy:
    interface.implements(octtree.ILocated)
    def __init__(self, x=0, y=0, z=0):
        self.position = array((x, y, z), typecode='d')
    def __str__(self):
        return 'Thingy%r' % (self.position,)
    __repr__ = __str__

class UtilTestCase(unittest.TestCase):
    def testPermute(self):
        e = [['a', 'a'], ['a', 'b'], ['b', 'a'], ['b', 'b']]
        e.sort()
        r = list(octtree.permute(('a', 'b'), 2))
        r.sort()
        self.assertEquals(e, r)

    def testVisible(self):
        # Dead on
        self.failUnless(
            octtree.visible((0, 0, 0), (0, 1, 0), cos(pi / 4), (0, 1, 0)))

        # Each of the 4 sides
        self.failUnless(
            octtree.visible((0, 0, 0), (0, 1, 0), cos(pi / 4), (0.9, 1, 0)))

        self.failUnless(
            octtree.visible((0, 0, 0), (0, 1, 0), cos(pi / 4), (-0.9, 1, 0)))

        self.failUnless(
            octtree.visible((0, 0, 0), (0, 1, 0), cos(pi / 4), (0, 1, 0.9)))

        self.failUnless(
            octtree.visible((0, 0, 0), (0, 1, 0), cos(pi / 4), (0, 1, -0.9)))

        # Each of the 4 corners
        self.failUnless(
            octtree.visible((0, 0, 0), (0, 1, 0), cos(pi / 4), (1, 1.415, 1)))

        self.failUnless(
            octtree.visible((0, 0, 0), (0, 1, 0), cos(pi / 4), (1, 1.415, -1)))

        self.failUnless(
            octtree.visible((0, 0, 0), (0, 1, 0), cos(pi / 4), (-1, 1.415, 1)))

        self.failUnless(
            octtree.visible((0, 0, 0), (0, 1, 0), cos(pi / 4), (-1, 1.415, -1)))

        # Behind us
        self.failIf(
            octtree.visible((0, 0, 0), (0, 1, 0), cos(pi / 4), (0, -1, 0)))

        # Just outside of each side
        self.failIf(
            octtree.visible((0, 0, 0), (0, 1, 0), cos(pi / 4), (1.1, 1, 0)))

        self.failIf(
            octtree.visible((0, 0, 0), (0, 1, 0), cos(pi / 4), (-1.1, 1, 0)))

        self.failIf(
            octtree.visible((0, 0, 0), (0, 1, 0), cos(pi / 4), (0, 1, 1.1)))

        self.failIf(
            octtree.visible((0, 0, 0), (0, 1, 0), cos(pi / 4), (0, 1, -1.1)))

        # Just outside each corner
        self.failIf(
            octtree.visible((0, 0, 0), (0, 1, 0), cos(pi / 4), (1, 1.414, 1)))

        self.failIf(
            octtree.visible((0, 0, 0), (0, 1, 0), cos(pi / 4), (1, 1.414, -1)))

        self.failIf(
            octtree.visible((0, 0, 0), (0, 1, 0), cos(pi / 4), (-1, 1.414, 1)))

        self.failIf(
            octtree.visible((0, 0, 0), (0, 1, 0), cos(pi / 4), (-1, 1.414, -1)))


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
    testNearBoundarySearch.skip = "write me"

    def testVisibility(self):
        viewpoint = (0, 0, 0)
        direction = (0, 1, 0)
        fovAngle = cos(pi / 4)
        o = [Thingy(*c) for c in [(0, 1, 0), (0, 2, 0), (0, 3, 0)]]

        ot = octtree.OctTree([0, 0, 0], 20, 20, 20)
        for obj in o:
            ot.add(obj)

        vis = list(ot.itervisible(viewpoint, direction, fovAngle))
        self.assertEquals(len(vis), len(o))
        vis.sort()
        o.sort()
        self.assertEquals(vis, o)
