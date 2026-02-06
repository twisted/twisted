#!/usr/bin/env python

# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.


from twisted.cred import credentials
from twisted.internet import reactor
from twisted.spread import pb


def main():
    factory = pb.PBClientFactory()
    reactor.connectTCP("localhost", 8800, factory)
    def1 = factory.login(credentials.UsernamePassword("user1", "pass1"))
    def1.addCallback(connected)
    reactor.run()


def connected(perspective):
    print("got perspective1 ref:", perspective)
    print("asking it to foo(13)")
    perspective.callRemote("foo", 13)


main()
