#!/usr/bin/env python

# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.


from twisted.internet import reactor
from twisted.spread import pb


class One(pb.Root):
    def remote_takeTwo(self, two):
        print("received a Two called", two)
        print("telling it to print(12)")
        two.callRemote("print", 12)


reactor.listenTCP(8800, pb.PBServerFactory(One()))
reactor.run()
