
import time
import pygame

import point

BLACK = (0, 0, 0)
WHITE = (255, 255, 255)

# Get a configuration
from sol import config, width as WIDTH, height as HEIGHT

# PyGame's clock sucks nuts
class Clock:
    def tick(self, n):
        now = time.time()
        left = now % (1.0 / n)
        time.sleep(left)

def main():
    pygame.init()
    image = pygame.image.load("circle.bmp")

    space = point.Space()

    bodies = []
    for (mass, pos, vel) in config:
        b = (point.Body(space, mass, pos, vel), image.get_rect())
        bodies.append(b)

    perFrame = 60
    size = width, height = 800, 600
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
            left = long(b.position[0] / WIDTH * width) + (width / 2)
            top = long(b.position[1] / HEIGHT * height) + (height / 2)
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

