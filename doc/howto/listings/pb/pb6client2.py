#! /usr/bin/python

from twisted.spread import pb
from twisted.internet import reactor

def main():
    def1 = pb.connect("localhost", 8800,
                      "user2", "pass2",
                      "myservice", "perspective2",
                      30)
    def1.addCallbacks(connected)
    reactor.run()

def connected(perspective):
    print "got perspective2 ref:", perspective
    print "asking it to foo(14)"
    perspective.callRemote("foo", 14)

main()
