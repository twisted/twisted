# Port of Game-Skel4.py from Soya 0.5 or 0.6 to Soya 0.7
# By Vito, vito_gameskel4port@perilith.com

import os
import soya, soya.sphere

import point, vis, moon as config

def makeSystem():
    s = point.Space()
    bodies = []
    for (mass, pos, vel) in config.config:
        b = point.Body(s, mass, pos, vel)
        bodies.append(b)
    s.bodies = bodies
    return s

class Level(soya.World):
    pass

class System(soya.World):
    def __init__(self, parent, light, space):
        soya.World.__init__(self, parent)

        self.space = space

        self.star = space.bodies[0]
        sunsphere = soya.sphere.Sphere(self)
        sunsphere.scale(1.0, 1.0, 1.0)
        self.bodies = [Body(self, self.star, light), Body(self, self.star, sunsphere)]

        for b in space.bodies[1:]:
            bodysphere = soya.sphere.Sphere(self)
            bodysphere.scale(0.3, 0.3, 0.3)
            self.bodies.append(Body(self, b, bodysphere))

    def advance_time(self, proportion):
        self.space.update()

class Body(soya.World):
    def __init__(self, parent, body, volume):
        soya.World.__init__(self, parent)

        self.body = body
        self.volume = volume
        self.volume.scale(0.1, 0.1, 0.1)

    def begin_round(self):
        p = [c / 1000 for c in self.body.position]
        self.volume.set_xyz(*p)
        soya.World.begin_round(self)
        print p

def main():
    soya.init("vis3d.py", 640, 480, 0, 0)
    soya.path.append(os.path.join(os.getcwd(), "vis3d-data"))

    s = makeSystem()

    scene = soya.World()
    level = Level(scene)

    light = soya.Light(scene)
    light.set_xyz(1, 1, 1)

    camera = soya.Camera(scene)
    camera.set_xyz(0, 0, 4.0)
    soya.set_root_widget(camera)

    system = System(level, light, s)

    soya.Idler(scene).idle()

if __name__ == '__main__':
    main()


