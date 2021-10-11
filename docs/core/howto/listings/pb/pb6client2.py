#!/usr/bin/env python

# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.


from twisted.cred import credentials
from twisted.internet import reactor
from twisted.spread import pb


def main():
    factory = pb.PBClientFactory()
    reactor.connectTCP("localhost", 8800, factory)
    def1 = factory.login(credentials.UsernamePassword("user2", "pass2"))
    def1.addCallback(connected)
    reactor.run()


def connected(perspective):
    print("got perspective2 ref:", perspective)
    print("asking it to foo(14)")
    perspective.callRemote("foo", 14)


main()
