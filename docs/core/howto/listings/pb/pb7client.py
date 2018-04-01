#!/usr/bin/env python

# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

from __future__ import print_function

from twisted.spread import pb
from twisted.internet import reactor

def one(port, user, pw, service, perspective, number):
    factory = pb.PBClientFactory()
    reactor.connectTCP("localhost", port, factory)
    def1 = factory.getPerspective(
        user, pw, service, perspective)
    def1.addCallback(connected, number)

def connected(perspective, number):
    print("got perspective ref:", perspective)
    print("asking it to foo(%d)" % number)
    perspective.callRemote("foo", number)

def main():
    one(8800, "user1", "pass1", "service1", "perspective1.1", 10)
    one(8800, "user1", "pass1", "service2", "perspective2.1", 11)
    one(8800, "user2", "pass2", "service1", "perspective1.2", 12)
    one(8800, "user2", "pass2", "service2", "perspective2.2", 13)
    one(8801, "user3", "pass3", "service3", "perspective3.3", 14)
    reactor.run()
    
main()
