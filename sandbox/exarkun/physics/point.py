
import numarray as N

G = 6.667e-11

_V_DIMS = 7
_MASS = 0
_POSITION = slice(1, 4)
_VELOCITY = slice(4, 7)

class Space(object):
    topHandle = -1
    def __init__(self):
        self.contents = N.array((), type='d')
        self.handleMap = {}

    def __getitem__(self, h):
        return self.contents[self.handleMap[h]]

    def getNewHandle(self):
        x = len(self.contents)
        if self.topHandle == x - 1:
            m = int((x * 1.1) + 10)
            self.contents.resize((m, _V_DIMS))
        self.topHandle += 1
        self.handleMap[self.topHandle] = self.topHandle
        return self.topHandle

    def freeHandle(self, n):
        topHandle = self.topHandle
        j = self.handleMap.pop(n)
        if n != topHandle:
            i = self.handleMap[topHandle]
            self.contents[j] = self.contents[i]
            self.handleMap[topHandle] = j
        self.topHandle = max(self.handleMap)

    def update(self):
        self._updatePosition()
        self._updateVelocity()

    def _updatePosition(self):
        # Add velocity to position to get new positions
        # Do it in place for speeeed
        N.add(self.contents[:,_POSITION], self.contents[:,_VELOCITY], self.contents[:,_POSITION])

    def _updateVelocity(self, sum=N.sum, add=N.add, _M=_MASS, _P=_POSITION, _V=_VELOCITY, NewAxis=N.NewAxis):
        # Adjust velocities for gravitational effects

        # XXX This loop can probably be pushed into numeric, but I'm not sure
        # how yet.
        contents = N.array(self.contents[:self.topHandle + 1])
        for i, a in enumerate(contents):
            mass = a[_M]
            if not mass:
                continue

            deltas = contents[:,_P] - a[_P]
            deltas2 = deltas * deltas
            distances2 = sum(deltas2, 1)
            distances = distances2 ** 0.5

            # NaN!@
            distances[i] = 1
            distances2[i] = 1
            # @!NaN

            units = deltas / distances[:,NewAxis]
            forces = G * mass * contents[:,_M] / distances2
            deltaAs = units * forces[:,NewAxis] / mass

            # NaN!@
            deltaAs[i][:] = [0]
            # @!NaN

            add(self.contents[i][_V], sum(deltaAs), self.contents[i][_V])

class Body(object):
    __slots__ = ["_space", "_handle", "mass", "position", "velocity"]

    def mass():
        def get(self):
            return self._space[self._handle][_MASS]
        def set(self, value):
            self._space[self._handle][_MASS] = value
        doc = "Mass, in kilograms, of this body"
        return (get, set, None, doc)
    mass = property(*mass())

    def position():
        def get(self):
            return tuple(self._space[self._handle][_POSITION])
        def set(self, pos):
            self._space[self._handle][_POSITION] = pos
        doc = "XYZ coordinates of this body"
        return (get, set, None, doc)
    position = property(*position())

    def velocity():
        def get(self):
            return tuple(self._space[self._handle][_VELOCITY])
        def set(self, vel):
            self._space[self._handle][_VELOCITY] = vel
        doc = "XYZ velocity, in kilometers/second, of this body"
        return (get, set, None, doc)
    velocity = property(*velocity())

    def __init__(self, space, mass, position, velocity=(0, 0, 0)):
        self._space = space
        self._handle = space.getNewHandle()
        self.mass = mass
        self.position = position
        self.velocity = velocity
