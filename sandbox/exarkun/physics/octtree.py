
from zope import interface

class ILocated(interface.Interface):
    position = property(doc="Three tuple of coordinates of a thing")

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
                    center[0] = self.center - width / 2
                else:
                    center[0] = self.center + width / 2
                if front:
                    center[1] = self.center - depth / 2
                else:
                    center[1] = self.center + depth / 2
                if bottom:
                    center[2] = self.center - height / 2
                else:
                    center[2] = self.center + height / 2
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
        f = lambda *a: children.append(self._children[a])
        if left:
            if front:
                if bottom:
                    f(True, True, False)
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
            for obj in child.iternear(center, radius):
                yield obj
