from twisted.trial import unittest
#import event_compat as event
import event_libevent as event
import os


def handler1(fd, eve, argument):
    print "Event <handler 1>: %s %s %s" % (fd, eve, argument)
    if eve & event.EV_READ:
        print "Length Read: %s" % len(os.read(fd, 1024))

def handler2(fd, eve, argument):
    print "Event <handler 2>: %s %s %s" % (fd, eve, argument)
    if eve & event.EV_READ:
        os.read(fd, 124)

class TestEventHandler(unittest.TestCase):
    def test_event(self):
        event.event_init()
        myevent = event.Event(-1, event.EV_TIMEOUT|event.EV_PERSIST, handler1, None, 1)
        myevent.go()
        file = os.open("/dev/random", os.O_NONBLOCK)
        myfileevent = event.Event(file, event.EV_READ|event.EV_PERSIST|event.EV_TIMEOUT, handler1, None, 1.5)
        myevent2 = event.Event(-1, event.EV_TIMEOUT|event.EV_PERSIST, handler2, None, 1.5)
        myfileevent.go()
        myevent2.go()
        event.dispatch()

    
