# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.


from twisted.internet import _threadedselect
_threadedselect.install()

from twisted.internet.defer import Deferred
from twisted.python.failure import Failure
from twisted.internet import reactor
from twisted.python.runtime import seconds
from itertools import count
from Queue import Queue, Empty

class TwistedManager(object):
    def __init__(self):
        self.twistedQueue = Queue()
        self.key = count()
        self.results = {}

    def getKey(self):
        # get a unique identifier
        return self.key.next()

    def start(self):
        # start the reactor
        reactor.interleave(self.twistedQueue.put)

    def _stopIterating(self, value, key):
        self.results[key] = value

    def stop(self):
        # stop the reactor
        key = self.getKey()
        reactor.addSystemEventTrigger('after', 'shutdown',
            self._stopIterating, True, key)
        reactor.stop()
        self.iterate(key)

    def getDeferred(self, d):
        # get the result of a deferred or raise if it failed
        key = self.getKey()
        d.addBoth(self._stopIterating, key)
        res = self.iterate(key)
        if isinstance(res, Failure):
            res.raiseException()
        return res
    
    def poll(self, noLongerThan=1.0):
        # poll the reactor for up to noLongerThan seconds
        base = seconds()
        try:
            while (seconds() - base) <= noLongerThan:
                callback = self.twistedQueue.get_nowait()
                callback()
        except Empty:
            pass
    
    def iterate(self, key=None):
        # iterate the reactor until it has the result we're looking for
        while key not in self.results:
            callback = self.twistedQueue.get()
            callback()
        return self.results.pop(key)

def fakeDeferred(msg):
    d = Deferred()
    def cb():
        print "deferred called back"
        d.callback(msg)
    reactor.callLater(2, cb)
    return d

def fakeCallback():
    print "twisted is still running"

def main():
    m = TwistedManager()
    print "starting"
    m.start()
    print "setting up a 1sec callback"
    reactor.callLater(1, fakeCallback)
    print "getting a deferred"
    res = m.getDeferred(fakeDeferred("got it!"))
    print "got the deferred:", res
    print "stopping"
    m.stop()
    print "stopped"


if __name__ == '__main__':
    main()
