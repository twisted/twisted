from twisted.internet import base
import warnings
from event_libevent import EventManager, Event, Timer


class EventReactor(base.ReactorBase):
    def __init__(self):
        base.ReactorBase.__init__(self)
        event.event_init()

    def doIteration(self, delay=0):
        EventManager.loop()

    def addReader(self, reader):
        pass
