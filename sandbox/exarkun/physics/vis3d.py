# Port of Game-Skel4.py from Soya 0.5 or 0.6 to Soya 0.7
# By Vito, vito_gameskel4port@perilith.com

import os
import soya, soya.widget, soyasdlconst as SC
from PIL import PngImagePlugin # for py2exe

soya.init("vis3d.py", 640, 480, 0, 0)
soya.path.append(os.path.join(os.getcwd(), "vis3d-data"))

class Level(soya.World):
    pass

# Things we care about colliding with. bleh global.
colliders = {}

def create_level():

    level = Level()
    level_static = soya.World(level)

    # Lighting
    light = soya.Light(level_static)
    light.directional = 1
    light.diffuse = (1.0, 0.8, 0.4, 1.0)
    light.rotate_vertical(-45.0)

    # Creates the darkness of space.  Well, a bit brighter than that.
    atmosphere = soya.Atmosphere()
    atmosphere.ambient = (0.3, 0.3, 0.4, 1.0)
    atmosphere.sky_color = (0.1, 0.1, 0.1, 1.0)

    # Set the atmosphere to the level
    level.atmosphere = atmosphere

    level_static.filename = level.name = "level_demo_static"
    level_static.save()
    level.filename = level.name = "level_demo"
    level.save()


def spacePosToSoyaCoords(c):
    return c[0] / 10 + 20., c[2] - 60, c[1] / 10 + 100

# Actors classes in the Unreal sense are Worlds
# Models or meshes are Shapes
# Volumes are the actual spawned and rendered Actor
class Character(soya.World):

    def __init__(self, system, scene, parent, controller):
        soya.World.__init__(self, parent)

        self.system = system
        self.scene = scene

        cal3dshape = soya.Cal3dShape.get("balazar")
        self.volume = soya.Cal3dVolume(self, cal3dshape)
        self.volume.animate_blend_cycle("attente")
        self.current_animation = "attente"

        self.solid = 0

        self.controller = controller
        self.speed = soya.Vector(self)
        self.rotation_speed = 0.0

        self.radius = 0.5
        self.radius_y = 1.0
        self.center = soya.Point(self, 0.0, self.radius_y, 0.0)

        self.left = soya.Vector(self, -1.0, 0.0, 0.0)
        self.right = soya.Vector(self, 1.0, 0.0, 0.0)
        self.down = soya.Vector(self, 0.0, -1.0, 0.0)
        self.up = soya.Vector(self, 0.0, 1.0, 0.0)
        self.front = soya.Vector(self, 0.0, 0.0, -1.0)
        self.back = soya.Vector(self, 0.0, 0.0, 1.0)

        self.inventory = []
        self.right_hand = soya.World(self)
        self.volume.attach_to_bone(self.right_hand, 'mainD')

    def play_animation(self, animation):
        if self.current_animation != animation:
            self.volume.animate_clear_cycle(self.current_animation, 0.2)
            self.volume.animate_blend_cycle(animation, 1.0, 0.2)
            self.current_animation = animation

    def space_update(self):
        self.system.update()
        for (sb, b) in self.system.soya_bodies:
            sb.set_xyz(*spacePosToSoyaCoords(b.position))

    def begin_round(self):
        self.space_update()
        self.controller.next()
        self.begin_action()
        soya.World.begin_round(self)

    def begin_action(self):
        self.speed.x = self.speed.z = self.rotation_speed = 0.0
        if self.speed.y > 0.0:
            self.speed.y = 0.0
        animation = "attente"

        if self.controller.turnleft_pressed:
            self.rotation_speed = 4.0
            animation = "tourneG"
        elif self.controller.turnright_pressed:
            self.rotation_speed = -4.0
            animation = "tourneD"

        if self.controller.forward_pressed:
            self.speed.z = -0.25
            animation = "marche"
        elif self.controller.back_pressed:
            self.speed.z = 0.06
            animation = "recule"

        new_center = self.center + self.speed

        context = self.scene.RaypickContext(new_center,
                                            max(self.radius, 0.1 + self.radius_y))

        ## Collision detection
        # Probably horribly inefficient :\
        for vec in (self.left, self.right, self.front, self.back, self.up, self.down):
            r = context.raypick(new_center, vec, self.radius, 3)
            if r:
                collision, wall_normal = r
                shape = r[0].parent
                collider = colliders.get(shape, None)
                if collider is not None:
                    self.collidedWith(collider)
                hypo = (vec.length()
                        * self.radius
                        - (new_center >> collision).length())
                correction = wall_normal * hypo
                correction.y = 0

                self.speed += correction
                new_center += correction

        self.play_animation(animation)

    def advance_time(self, proportion):
        soya.World.advance_time(self, proportion)

        self.add_mul_vector(proportion, self.speed)
        self.rotate_lateral(proportion * self.rotation_speed)

    def collidedWith(self, thingy):
        print "THWANG"
        self.inventory.append(thingy)
        thingy.takenBy(self)


class KeyboardController:
    def __init__(self):
        self.events = {
            SC.K_LEFT: 'turnleft_pressed',
            SC.K_RIGHT: 'turnright_pressed',
            SC.K_UP: 'forward_pressed',
            SC.K_DOWN: 'back_pressed',
            SC.K_PAGEUP: 'flyup_pressed',
            SC.K_PAGEDOWN: 'flydown_pressed'}
        self.toggles = {
            SC.K_HOME: 'fly_on'}

        for attr in self.events.values() + self.toggles.values():
            setattr(self, attr, False)

    def next(self):
        for event in soya.process_event():
            if event[0] in (SC.KEYUP, SC.KEYDOWN):
                key = self.events.get(event[1], None)
            if event[0] == SC.KEYDOWN:
                if event[1] in (SC.K_q, SC.K_ESCAPE):
                    soya.IDLER.stop()
                if key is not None:
                    setattr(self, key, True)
                togglekey = self.toggles.get(event[1], None)
                if togglekey is not None:
                    setattr(self, togglekey, not getattr(self, togglekey))
            if event[0] == SC.KEYUP:
                if key is not None:
                    setattr(self, key, False)

# Someone should draw me nice pictures
BODY = 'farm'

def main(system):
    # you can comment this out after you've created it for the first time
    create_level()

    scene = soya.World()
    level = soya.World.get("level_demo")
    scene.add(level)

    bodies = []
    for b in system.bodies:
        tmpl = soya.Shape.get(BODY)
        body = soya.Volume(level, tmpl)
        body.set_xyz(*spacePosToSoyaCoords(b.position))
        body.scale(1, 1, 1)
        bodies.append((body, b))
    system.soya_bodies = bodies

    character = Character(system, level, scene, KeyboardController())

    character.set_xyz(10, -25, 10.000001)
    character.rotate_lateral(180)

    camera = soya.TravelingCamera(scene)
    traveling = soya.ThirdPersonTraveling(character)
    traveling.distance = 5.0
    camera.add_traveling(traveling)
    camera.zap()
    camera.back = 1000.0

    soya.set_root_widget(soya.widget.Group())
    soya.root_widget.add(camera)
    soya.root_widget.add(soya.widget.FPSLabel())

    soya.Idler(scene).idle()

import point, vis, moon as config
def make_system():
    s = point.Space()
    bodies = []
    for (mass, pos, vel) in config.config:
        b = point.Body(s, mass, pos, vel)
        bodies.append(b)
    s.bodies = bodies
    return s

if __name__ == '__main__':
    main(make_system())
