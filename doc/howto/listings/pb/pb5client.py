#! /usr/bin/python

from twisted.spread import pb
from twisted.internet import reactor

def main():
    def1 = pb.connect("localhost", 8800,
                      "user1", "pass1",
                      "myservice", "perspective1",
                      30)
    def1.addCallbacks(connected)
    reactor.run()

def connected(perspective):
    print "got perspective ref:", perspective
    print "asking it to foo(12)"
    perspective.callRemote("foo", 12)

main()
