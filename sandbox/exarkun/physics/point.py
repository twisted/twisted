
import numarray as N

_V_DIMS = 7
_MASS = 0
_POSITION = slice(1, 4)
_VELOCITY = slice(4, 7)

class Space(object):
    def __init__(self):
        self.contents = N.array((), type='f')
        self.freelist = []

    def getNewHandle(self):
        if self.freelist:
            return self.freelist.pop()
        n = len(self.contents)
        m = int((n * 1.1) + 10)
        self.contents.resize((m, _V_DIMS))
        self.freelist.extend(range(m - 1, n, -1))
        return n

    def freeHandle(self, n):
        self.freelist.append(n)
        self.contents[n] = [-42] * _V_DIMS

class Body(object):
    __slots__ = ["_space", "_handle", "mass", "position", "velocity"]

    def mass():
        def get(self):
            return self._space.contents[self._handle][_MASS]
        def set(self, value):
            self._space.contents[self._handle][_MASS] = value
        doc = "Mass, in kilograms, of this body"
        return (get, set, None, doc)
    mass = property(*mass())

    def position():
        def get(self):
            return tuple(self._space.contents[self._handle][_POSITION])
        def set(self, pos):
            self._space.contents[self._handle][_POSITION] = pos
        doc = "XYZ coordinates of this body"
        return (get, set, None, doc)
    position = property(*position())

    def velocity():
        def get(self):
            return tuple(self._space.contents[self._handle][_VELOCITY])
        def set(self, vel):
            self._space.contents[self._handle][_VELOCITY] = vel
        doc = "XYZ velocity, in kilometers/second, of this body"
        return (get, set, None, doc)
    velocity = property(*velocity())

    def __init__(self, space, mass, position, velocity=(0, 0, 0)):
        self._space = space
        self._handle = space.getNewHandle()
        self.mass = mass
        self.position = position
        self.velocity = velocity
