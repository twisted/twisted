
from zope import interface

class ILocated(interface.Interface):
    position = interface.Attribute(
        "position", __doc__="Three tuple of coordinates of a thing")

def distance(x, y):
    return ((x[0] - y[0]) ** 2 + (x[1] - y[1]) ** 2 + (x[2] - y[2]) ** 2) ** 0.5

class _TerminalNode(object):
    def __init__(self):
        self.objects = []

    def add(self, obj):
        self.objects.append(obj)

    def remove(self, obj):
        self.objects.remove(obj)

    def __iter__(self):
        return iter(self.objects)

    def iternear(self, center, radius):
        for o in self.objects:
            if distance(o.position, center) < radius:
                yield o

def fmt(left, front, bottom):
    return ' '.join((left and 'left' or 'right',
                     front and 'front' or 'back',
                     bottom and 'bottom' or 'top'))

def determinant(a, b, c):
    return (a[0] * b[1] * c[2] -
            a[0] * b[2] * c[1] +
            a[1] * b[2] * c[0] -
            a[1] * b[0] * c[2] +
            a[2] * b[0] * c[1] -
            a[2] * b[1] * c[0])

def between(c, p1, p2):
    # Return True if point c is between planes p1 and p2
    A1 = (det(p1[0], p1[1], p1[2]),
          det((1, 1, 1), p1[1], p1[2]),
          det(p1[0], (1, 1, 1), p1[2])
          det(p1[0], p1[1], (1, 1, 1)))

    A2 = (det(p2[0], p2[1], p2[2]),
          det((1, 1, 1), p2[1], p2[2]),
          det(p2[0], (1, 1, 1), p2[2])
          det(p2[0], p2[1], (1, 1, 1)))

    n = A1[1] * c[0] + A1[2] * c[1] + A1[3] * c[2] + A1[0]
    m = A2[1] * c[0] + A2[2] * c[1] + A2[3] * c[2] + A2[0]

    return (n > 0) == (m > 0)

def inPrism(c, (w1, x1, y1, z1), (w2, x2, y2, z2)):
    return (between(c, (w1, x1, y1), (w2, x2, y2)) and
            between(c, (w1, w2, z2), (x1, x2, y2)) and
            between(c, (w1, x1, x2), (z1, y1, y2)))

class OctTree(object):
    def __init__(self, center, width, depth, height, n=0):
        self.center = center
        self.width = width
        self.depth = depth
        self.height = height
        self._children = {}
        self.n = n

    def _getChild(self, p):
        left = p[0] < self.center[0]
        front = p[1] < self.center[1]
        bottom = p[2] < self.center[2]
        n = (left, front, bottom)

        # One way to implement the base case for this recursive function
        # is to stop when an empty node is found.  There is no need to
        # subdivide between a single object.  Even more, for small groups
        # of nodes, we can manage them all with one OctTree node, even if
        # they are further apart than other objects in the OctTree that do
        # not belong to the same node.

        # Another way is to use a fixed depth.  This is the way we will use.
        # Subsequent implementations may attempt to be smarter.

        child = self._children.get(n)
        if child is None:
            if self.n == 9:
                child = self._children[n] = _TerminalNode()
            else:
                # XXX Parameterize 2
                center = [None, None, None]
                width = self.width / 2
                depth = self.depth / 2
                height = self.depth / 2
                if left:
                    center[0] = self.center[0] - width / 2
                else:
                    center[0] = self.center[0] + width / 2
                if front:
                    center[1] = self.center[1] - depth / 2
                else:
                    center[1] = self.center[1] + depth / 2
                if bottom:
                    center[2] = self.center[2] - height / 2
                else:
                    center[2] = self.center[2] + height / 2
                child = self._children[n] = OctTree(tuple(center),
                                                    width,
                                                    depth,
                                                    height,
                                                    self.n + 1)
        return child

    def add(self, obj):
        child = self._getChild(obj.position)
        child.add(obj)

    def remove(self, obj):
        child = self._getChild(obj.position)
        child.remove(obj)

    def __iter__(self):
        for ch in self._children:
            if ch is not None:
                for obj in ch:
                    yield obj

    def iternear(self, center, radius):
        # Required condition for left octants
        left = ((self.center[0] - (self.width / 2) < center[0] + radius) and
                (self.center[0] > center[0] - radius))

        # Required condition for right octants
        right = ((self.center[0] + (self.width / 2) > center[0] - radius) and
                 (self.center[0] < center[0] + radius))

        if not (left or right):
            return

        # Required condition for front octants
        front = ((self.center[1] - (self.depth / 2) < center[1] + radius) and
                 (self.center[1] > center[1] - radius))

        # Required condition for back octants
        back = ((self.center[1] + (self.width / 2) > center[1] - radius) and
                (self.center[1] < center[1] + radius))

        if not (front or back):
            return

        # Required condition for bottom octants
        bottom = ((self.center[2] - (self.height / 2) < center[2] + radius) and
                  (self.center[2] > center[2] - radius))

        # Required condition for top octants
        top = ((self.center[2] + (self.height / 2) > center[2] - radius) and
               (self.center[2] < center[2] + radius))

        if not (bottom or top):
            return

        children = []
        f = lambda *a: children.append(self._children.get(a))
        if left:
            if front:
                if bottom:
                    f(True, True, True)
                if top:
                    f(True, True, False)
            if back:
                if bottom:
                    f(True, False, True)
                if top:
                    f(True, False, False)
        if right:
            if front:
                if bottom:
                    f(False, True, True)
                if top:
                    f(False, True, False)
            if back:
                if bottom:
                    f(False, False, True)
                if top:
                    f(False, False, False)

        for child in children:
            if child is not None:
                for obj in child.iternear(center, radius):
                    yield obj
