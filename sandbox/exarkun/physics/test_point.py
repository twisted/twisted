
from twisted.trial import unittest

import point

class SpaceTest(unittest.TestCase):
    def testHandles(self):
        s = point.Space()

        handles = []
        for i in range(100):
            h = s.getNewHandle()
            self.failIf(h in handles, "%r double allocated" % (h,))
            handles.append(h)

        for h in handles[::-3]:
            s.freeHandle(h)
            handles.remove(h)

        for i in range(100):
            h = s.getNewHandle()
            self.failIf(h in handles)

        for h in handles:
            s.freeHandle(h)

class BodyTest(unittest.TestCase):
    def setUp(self):
        self.space = point.Space()

    def testInstantiation(self):
        b = point.Body(self.space, 10, (1, 2, 3), (-1, -2, -3))
        self.assertEquals(b.mass, 10)
        self.assertEquals(b.position, (1, 2, 3))
        self.assertEquals(b.velocity, (-1, -2, -3))

    def testAttributes(self):
        b = point.Body(self.space, 0, (0, 0, 0))

        b.mass = 12
        self.assertEquals(b.mass, 12)

        b.position = (-3, 3, 9)
        self.assertEquals(b.position, (-3, 3, 9))

        b.velocity = (3, -3, -9)
        self.assertEquals(b.velocity, (3, -3, -9))

    def testMovement(self):
        b = point.Body(self.space, 0, (0, 0, 0), (1, 0, 0))

        self.space.update()
        self.assertEquals(b.position, (1, 0, 0))

        self.space.update()
        self.assertEquals(b.position, (2, 0, 0))

        b.velocity = (-1, 1, 1)
        self.space.update()
        self.assertEquals(b.position, (1, 1, 1))

    def testMultipleMovement(self):
        x = point.Body(self.space, 1e9, (10, 0, 0), (-1, 0, 1))
        y = point.Body(self.space, 1e9, (0, 0, 10), (0, 1, -1))

        self.space.update()
        self.assertEquals(x.position, (9, 0, 1))
        self.assertEquals(y.position, (0, 1, 9))

        self.space.update()
        self.assertEquals(x.position, (8, 0, 2))
        self.assertEquals(y.position, (0, 2, 8))

