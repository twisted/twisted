
from zope import interface

from numarray import array, dot, alltrue, outerproduct
from numarray.linear_algebra import determinant

from util import distance, _distance, magnitude, normalize
from util import visible, _visible, permute
from util import linePointDistance, _linePointDistance, cross

class ILocated(interface.Interface):
    position = interface.Attribute(
        "position", __doc__="shape (3,) numarray of coordinates")

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
