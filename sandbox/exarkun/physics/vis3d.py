# Port of Game-Skel4.py from Soya 0.5 or 0.6 to Soya 0.7
# By Vito, vito_gameskel4port@perilith.com

import os, math
import soya, soya.widget, soya.sphere, soyasdlconst as const

import point, vis, sol as config

def makeSystem():
    s = point.Space()
    bodies = []
    for (mass, pos, vel) in config.config:
        b = point.Body(s, mass, pos, vel)
        bodies.append(b)
    s.bodies = bodies
    return s

class Controller:
    handlers = {
        const.KEYDOWN: 'KEYDOWN'}

    def iterate(self):
        for evt in soya.process_event():
            getattr(self, 'evt_' + self.handlers.get(evt[0], 'default'))(evt)

    def evt_default(self, evt):
        pass

    keydownHandlers = {
        const.K_q: 'QUIT',
        const.K_ESCAPE: 'QUIT'}

    def evt_KEYDOWN(self, evt):
        getattr(self, 'keydown_' + self.keydownHandlers.get(evt[1], 'default'))(evt)

    def keydown_default(self, evt):
        pass

    def keydown_QUIT(self, evt):
        soya.IDLER.stop()

class Level(soya.World):
    pass

class System(soya.World):
    def __init__(self, control, parent, space):
        soya.World.__init__(self, parent)

        self.control = control
        self.space = space

        biggest = max([o.mass for o in space.bodies])
        smallest = min([o.mass for o in space.bodies])

        self.bodies = []
        for i, b in enumerate(space.bodies):
            bodysphere = soya.sphere.Sphere(self)
            bodysphere.scale(15, 1, 15)
            self.bodies.append(Body(self, b, bodysphere))

    def advance_time(self, proportion):
        self.control.iterate()
        self.space.update()
        soya.World.advance_time(self, proportion)

class Body(soya.World):
    def __init__(self, parent, body, volume):
        soya.World.__init__(self, parent)

        self.body = body
        self.volume = volume

    def begin_round(self):
        x, y, z = self.body.position
        f = 10000000000000.0
        self.set_xyz(x / f, y / f, z / f)
        soya.World.begin_round(self)

def main():
    soya.init("vis3d.py", 800, 600, 0, 0)

    s = makeSystem()

    scene = soya.World()
    level = Level(scene)

    light = soya.Light(scene)
    light.set_xyz(0, 115, 0)

    camera = soya.Camera(scene)
    control = Controller()
    system = System(control, level, s)

    camera.set_xyz(0, 102, 0)
    camera.look_at(soya.Point(scene, 0, 101, 0))

    soya.set_root_widget(soya.widget.Group())
    soya.root_widget.add(camera)
    soya.root_widget.add(soya.widget.FPSLabel())

    soya.Idler(scene).idle()

if __name__ == '__main__':
    main()


