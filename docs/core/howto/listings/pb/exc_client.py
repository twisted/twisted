#!/usr/bin/env python

# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

from __future__ import print_function

from twisted.spread import pb
from twisted.internet import reactor

def main():
    factory = pb.PBClientFactory()
    reactor.connectTCP("localhost", 8800, factory)
    d = factory.getRootObject()
    d.addCallbacks(got_obj)
    reactor.run()

def got_obj(obj):
    # change "broken" into "broken2" to demonstrate an unhandled exception
    d2 = obj.callRemote("broken")
    d2.addCallback(working)
    d2.addErrback(broken)

def working():
    print("erm, it wasn't *supposed* to work..")
    
def broken(reason):
    print("got remote Exception")
    # reason should be a Failure (or subclass) holding the MyError exception
    print(" .__class__ =", reason.__class__)
    print(" .getErrorMessage() =", reason.getErrorMessage())
    print(" .type =", reason.type)
    reactor.stop()

main()
