#!/usr/bin/env python

# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

from __future__ import print_function

from twisted.spread import pb, jelly
from twisted.python import log
from twisted.internet import reactor
from copy2_classes import SenderPond

class Sender:
    def __init__(self, pond):
        self.pond = pond

    def got_obj(self, obj):
        d = obj.callRemote("takePond", self.pond)
        d.addCallback(self.ok).addErrback(self.notOk)

    def ok(self, response):
        print("pond arrived", response)
        reactor.stop()
    def notOk(self, failure):
        print("error during takePond:")
        if failure.type == jelly.InsecureJelly:
            print(" InsecureJelly")
        else:
            print(failure)
        reactor.stop()
        return None

def main():
    pond = SenderPond(3, 4)
    print("count %d" % pond.count())

    sender = Sender(pond)
    factory = pb.PBClientFactory()
    reactor.connectTCP("localhost", 8800, factory)
    deferred = factory.getRootObject()
    deferred.addCallback(sender.got_obj)
    reactor.run()

if __name__ == '__main__':
    main()

