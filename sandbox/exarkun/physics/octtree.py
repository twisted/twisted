
from zope import interface

class ILocated(interface.Interface):
    position = property(doc="Three tuple of coordinates of a thing")

class _TerminalNode(object):
    def __init__(self):
        self.objects = []

    def add(self, obj):
        self.objects.append(obj)

class OctTree(object):
    def __init__(self, center, width, depth, height, n=0):
        self.center = center
        self.width = width
        self.depth = depth
        self.height = height
        self.n = n

    def add(self, obj):
        # One way to implement the base case for this recursive function
        # is to stop when an empty node is found.  There is no need to
        # subdivide between a single object.  Even more, for small groups
        # of nodes, we can manage them all with one OctTree node, even if
        # they are further apart than other objects in the OctTree that do
        # not belong to the same node.

        # Another way is to use a fixed depth.  This is the way we will use.
        # Subsequent implementations may attempt to be smarter.

        p = obj.position

        left = p[0] < self.center[0]
        front = p[1] < self.center[1]
        bottom = p[2] < self.center[2]

        if self._children[n] is None:
            if self.n == 9:
                self._children[n] = _TerminalNode()
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
                self._children[n] = OctTree(center, width, depth, height)
        self._children[n].add(obj)
