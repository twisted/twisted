#! /usr/bin/python

from twisted.internet import reactor
from twisted.pb import pb

class Observer(pb.Referenceable):
    def remote_event(self, msg):
        print "event:", msg

def printResult(number):
    print "the result is", number
def gotError(err):
    print "got an error:", err
def gotRemote(remote):
    o = Observer()
    d = remote.callRemote("addObserver", observer=o)
    d.addCallback(lambda res: remote.callRemote("push", num=2))
    d.addCallback(lambda res: remote.callRemote("push", num=3))
    d.addCallback(lambda res: remote.callRemote("add"))
    d.addCallback(lambda res: remote.callRemote("pop"))
    d.addCallback(printResult)
    d.addCallback(lambda res: remote.callRemote("removeObserver", observer=o))
    d.addErrback(gotError)
    d.addCallback(lambda res: reactor.stop())
    return d

tub = pb.PBService()
d = tub.getReference("pb://ABCD@localhost:12345/calculator")
d.addCallback(gotRemote)

tub.startService()
reactor.run()
