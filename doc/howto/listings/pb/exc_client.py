#! /usr/bin/python

from twisted.spread import pb
from twisted.internet import reactor

def main():
    d = pb.getObjectAt("localhost", 8800, 30)
    d.addCallbacks(got_obj)
    reactor.run()

def got_obj(obj):
    d2 = obj.callRemote("broken")
    d2.addCallback(working)
    d2.addErrback(broken)

def working():
    print "erm, it wasn't *supposed* to work.."
    
def broken(reason):
    print "got remote Exception"
    # reason should be a Failure (or subclass) holding the MyError exception
    print " .__class__ =", reason.__class__
    print " .getErrorMessage() =", reason.getErrorMessage()
    print " .type =", reason.type
    reactor.stop()

main()
