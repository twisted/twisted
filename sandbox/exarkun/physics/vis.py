
import time
import pygame

import point

BLACK = (0, 0, 0)
WHITE = (255, 255, 255)

# PyGame's clock sucks nuts
class Clock:
    def tick(self, n):
        now = time.time()
        left = now % (1.0 / n)
        # time.sleep(left)

def main():
    pygame.init()
    image = pygame.image.load("circle.bmp")

    space = point.Space()

    bodies = []
##     for (mass, pos, vel) in [(1e9, (150, 150, 0), None),
##                              (1e6, (250, 150, 0), (0, -0.277, 0)),
##                              (1e6, (50, 150, 0), (0, 0.277, 0)),
##                              (1e6, (150, 50, 0), (-0.277, 0, 0)),
##                              (1e6, (150, 250, 0), (0.277, 0, 0))]:
    for (mass, pos, vel) in [(1e8, (250, 150, 0), (0, -0.0277, 0)),
                             (1e8, (50, 150, 0), (0, 0.0277, 0)),
                             (1e8, (150, 50, 0), (-0.0277, 0, 0)),
                             (1e8, (150, 250, 0), (0.0277, 0, 0))]:
        b = (point.Body(space, mass, pos, vel), image.get_rect())
        bodies.append(b)

    perFrame = 5
    size = width, height = 640, 480
    screen = pygame.display.set_mode(size)
    clock = Clock()

    count = 0
    while True:
        for evt in pygame.event.get():
            if evt.type == pygame.QUIT:
                raise SystemExit("Ran %d iterations" % (count * perFrame,))

        # clock.tick(60)
        for x in xrange(perFrame):
            space.update()

        blit = False
        for (b, r) in bodies:
            left = int(b.position[0] / 300 * width)
            top = int(b.position[1] / 300 * height)
            if left != r.left or top != r.top:
                r.left = left
                r.top = top
                blit = True

        if blit:
            screen.fill(WHITE)
            for (b, r) in bodies:
                screen.blit(image, r)
            pygame.display.flip()

        count += 1
        if count % 10000 == 9999:
            print 'tick'

if __name__ == '__main__':
    main()

