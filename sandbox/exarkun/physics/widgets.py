
from OpenGL.GL import *

from util import distance, normalize

class Overlay(object):
    def __init__(self, x, y, w, h, color):
        self.x = x
        self.y = y
        self.w = w
        self.h = h
        self.color = color

    def begin_round(self):
        pass

    def end_round(self):
        pass

    def advance_time(self, proportion):
        pass

    def resize(self, x, y, w, h):
        pass

    def render(self):
        blend = self.color[3] < 1.0
        if blend:
            glEnable(GL_BLEND)
        glColor4f(*self.color)
        glBegin(GL_QUADS)
        for (x, y) in ((self.x, self.y),
                       (self.x + self.w, self.y),
                       (self.x + self.w, self.y + self.h),
                       (self.x, self.y + self.h)):
            glVertex2i(x, y)
        glEnd()
        if blend:
            glDisable(GL_BLEND)

class RadarOverlay(Overlay):
    location = (0, 0, 0)
    perspective = (0, 0, 1)
    range = 100
    bodies = ()

    def setLocation(self, l):
        self.location = l

    def setPerspective(self, p):
        self.perspective = normalize(p)

    def setRange(self, r):
        self.range = r

    def setBodies(self, b):
        self.bodies = b

    def render(self):
        Overlay.render(self)

        glPointSize(5.0)
        glBegin(GL_POINTS)
        l = self.location
        for b in self.bodies:
            bx, by, bz = b.position
            if distance(l, b.position) < self.range:
                n = normalize((bx - l[0], by - l[1], bz - l[2]))
                x = n[0] / 2.0 * self.w + self.x + self.w / 2.0
                y = n[2] / 2.0 * self.h + self.y + self.h / 2.0
                glVertex2i(x, y)
        glEnd()

def test():
    import soya, soya.widget
    soya.init("widget test", 800, 600)

    class B:
        def __init__(self, x, y, z, dx, dy, dz):
            self.position = (x, y, z)
            self.velocity = (dx, dy, dz)

    class Level(soya.World):
        def __init__(self, bodies, *a, **kw):
            soya.World.__init__(self, *a, **kw)
            self.bodies = bodies

        def advance_time(self, proportion):
            for b in self.bodies:
                b.position = [c + dc for (c, dc) in zip(b.position, b.velocity)]

    bodies = [B(10, 0, 0, -0.01, 0.01, 0.0),
              B(0, 0, 10, 0, 0, 0),
              B(-10, 0, 0, 0.01, 0.01, 0.0),
              B(10, 0, 10, 0.01, 0.0, -0.02)]
    scene = soya.World()
    level = Level(bodies, scene)

    camera = soya.Camera(level)
    soya.set_root_widget(soya.widget.Group())
    soya.root_widget.add(camera)
    soya.root_widget.add(Overlay(10, 10, 80, 80, (1.0, 0.0, 0.0, 0.5)))

    ro = RadarOverlay(710, 510, 80, 80, (0.7, 0.7, 0.7, 0.7))
    ro.setBodies(bodies)
    soya.root_widget.add(ro)

    soya.Idler(scene).idle()

if __name__ == '__main__':
    test()
