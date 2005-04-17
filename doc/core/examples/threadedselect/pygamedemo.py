# import Twisted and install
from twisted.internet.threadedselectreactor import install
install()
from twisted.internet import reactor

import os

import pygame
from pygame.locals import *

# You can customize this if you use your
# own events, but you must OBEY:
#
#   USEREVENT <= TWISTEDEVENT < NUMEVENTS
#
TWISTEDEVENT = USEREVENT

def postTwistedEvent(func):
    pygame.event.post(pygame.event.Event(TWISTEDEVENT, iterateTwisted=func))

def helloWorld():
    print "hello, world"
    reactor.callLater(1, helloWorld)
reactor.callLater(1, helloWorld)

def twoSecondsPassed():
    print "two seconds passed"
reactor.callLater(2, twoSecondsPassed)

def main():
    pygame.init()
    screen = pygame.display.set_mode((300, 300))

    # send an event when twisted wants attention
    reactor.interleave(postTwistedEvent)
    # make shouldQuit a True value when it's safe to quit
    # by appending a value to it.  This ensures that
    # Twisted gets to shut down properly.
    shouldQuit = []
    reactor.addSystemEventTrigger('after', 'shutdown', shouldQuit.append, True)

    while not shouldQuit:
        for event in pygame.event.get():
            if event.type == TWISTEDEVENT:
                event.iterateTwisted()
            elif event.type == QUIT:
                reactor.stop()
            elif event.type == KEYDOWN and event.key == K_ESCAPE:
                reactor.stop()
                
    pygame.quit()

if __name__ == '__main__':
    main()
