
import time
import point

def getBodies(space, config):
    bodies = []
    for (mass, pos, vel) in config:
        bodies.append(point.Body(space, mass, pos, vel))
    return bodies

from sol import config
def main(iters):
    s = point.Space()
    b = getBodies(s, config)

    now = time.clock()
    for i in xrange(iters):
        s.update()
    end = time.clock()
    return end - now

if __name__ == '__main__':
    print 1000 / main(1000), 'iterations per second'
