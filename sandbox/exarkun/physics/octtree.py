
from zope import interface

from numarray import array, dot, alltrue, outerproduct
from numarray.linear_algebra import determinant

class ILocated(interface.Interface):
    position = interface.Attribute(
        "position", __doc__="shape (3,) numarray of coordinates")

def distance(x, y):
    return _distance(array(x, typecode='d'),
                     array(y, typecode='d'))

def _distance(x, y):
    return sum((x - y) ** 2) ** 0.5

def magnitude(a):
    return sum(a * a) ** 0.5

def normalize(a):
    return a / magnitude(a)

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
        return self._iternear(array(center, typecode='d'),
                              radius)

    def _iternear(self, center, radius):
        for o in self.objects:
            if _distance(o.position, center) < radius:
                yield o

    def itervisible(self, viewpoint, direction, cosAngle=0.866):
        return self._itervisible(array(viewpoint, typecode='d'),
                                 array(direction, typecode='d'),
                                 cosAngle)

    def _itervisible(self, viewpoint, direction, cosAngle):
        for o in self.objects:
            if _visible(viewpoint, direction, cosAngle, o.position):
                yield o


def visible(viewpoint, direction, cosAngle, target):
    return _visible(array(viewpoint, typecode='d'),
                    array(direction, typecode='d'),
                    cosAngle,
                    array(target, typecode='d'))

def _visible(viewpoint, direction, cosAngle, target):
    if alltrue(target == viewpoint):
        return False
    target = normalize(target - viewpoint)
    direction = normalize(direction)
    prod = dot(target, direction - viewpoint)
    return prod > cosAngle

def permute(s, n):
    if n == 0:
        yield []
    else:
        for e in s:
            for r in permute(s, n - 1):
                yield r + [e]

class OctTree(object):
    def __init__(self, center, width, depth, height, n=0):
        self.center = array(center, typecode='d')
        self.width = float(width)
        self.depth = float(depth)
        self.height = float(height)
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
        for ch in self._children.itervalues():
            if ch is not None:
                for obj in ch:
                    yield obj

    def iternear(self, center, radius):
        return self._iternear(array(center, typecode='d'),
                              radius)

    def _iternear(self, center, radius):
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
                for obj in child._iternear(center, radius):
                    yield obj

    def itervisible(self, viewpoint, direction, cosAngle=0.866):
        return self._itervisible(array(viewpoint, typecode='d'),
                                 array(direction, typecode='d'),
                                 cosAngle)

    def _itervisible(self, viewpoint, direction, cosAngle):
        c = self.center
        w = self.width
        d = self.depth
        h = self.height

        corners = [c + (x * w, y * d, z * h)
                   for (x, y, z) in permute((-1, 1), 3)]
        vis = [cr
               for cr in corners
               if _visible(viewpoint, direction, cosAngle, cr)]
        if len(vis) == 9:
            # All corners visible, therefore all children visible.
            for ch in self._children.itervalues():
                if ch is not None:
                    for obj in ch:
                        yield obj
        elif len(vis) > 0:
            # Some corners visible, therefore some children visible.
            for ch in self._children.itervalues():
                if ch is not None:
                    for obj in ch._itervisible(viewpoint, direction, cosAngle):
                        yield obj
        else:
            # No corners visible.  The view frustum may pass through this
            # octant without intersecting a corner.  If the center of the
            # frustum lies within a particular distance of the center of
            # this octant, we know some children may be visible.
            critDist = magnitude(array((w / 2, d / 2, h / 2)))
            dist = _linePointDistance(c, array((0.0, 0, 0)), direction)
            if dist < critDist:
                for ch in self._children.itervalues():
                    if ch is not None:
                        for obj in ch._itervisible(viewpoint, direction, cosAngle):
                            yield obj

def linePointDistance(x0, x1, x2):
    return _linePointDistance(array(x0, typecode='d'),
                              array(x1, typecode='d'),
                              array(x2, typecode='d'))

def cross(a, b):
    x = a[1] * b[2] - a[2] * b[1]
    y = a[2] * b[0] - a[0] * b[2]
    z = a[0] * b[1] - a[1] * b[0]
    return array([x, y, z], typecode='d')

def _linePointDistance(x0, x1, x2):
    x = cross(x2 - x1, x1 - x0)
    num = magnitude(x)
    den = magnitude(x2 - x1)
    r = num / den
    return r
