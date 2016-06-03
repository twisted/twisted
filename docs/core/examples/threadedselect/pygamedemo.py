# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Demonstration of how L{twisted.internet._threadedselect} might be used (this is
not an example showing the best way to integrate Twisted with pygame).
"""
from __future__ import print_function

# import Twisted and install
from twisted.internet import _threadedselect
_threadedselect.install()
from twisted.internet import reactor

import os

import pygame
from pygame.locals import *

try:
    import pygame.fastevent as eventmodule
except ImportError:
    import pygame.event as eventmodule


# You can customize this if you use your
# own events, but you must OBEY:
#
#   USEREVENT <= TWISTEDEVENT < NUMEVENTS
#
TWISTEDEVENT = USEREVENT

def postTwistedEvent(func):
    # if not using pygame.fastevent, this can explode if the queue
    # fills up.. so that's bad.  Use pygame.fastevent, in pygame CVS
    # as of 2005-04-18.
    eventmodule.post(eventmodule.Event(TWISTEDEVENT, iterateTwisted=func))

def helloWorld():
    print("hello, world")
    reactor.callLater(1, helloWorld)
reactor.callLater(1, helloWorld)

def twoSecondsPassed():
    print("two seconds passed")
reactor.callLater(2, twoSecondsPassed)

def eventIterator():
    while True:
        yield eventmodule.wait()
        while True:
            event = eventmodule.poll()
            if event.type == NOEVENT:
                break
            else:
                yield event

def main():
    pygame.init()
    if hasattr(eventmodule, 'init'):
        eventmodule.init()
    screen = pygame.display.set_mode((300, 300))

    # send an event when twisted wants attention
    reactor.interleave(postTwistedEvent)
    # make shouldQuit a True value when it's safe to quit
    # by appending a value to it.  This ensures that
    # Twisted gets to shut down properly.
    shouldQuit = []
    reactor.addSystemEventTrigger('after', 'shutdown', shouldQuit.append, True)

    for event in eventIterator():
        if event.type == TWISTEDEVENT:
            event.iterateTwisted()
            if shouldQuit:
                break
        elif event.type == QUIT:
            reactor.stop()
        elif event.type == KEYDOWN and event.key == K_ESCAPE:
            reactor.stop()

    pygame.quit()

if __name__ == '__main__':
    main()
