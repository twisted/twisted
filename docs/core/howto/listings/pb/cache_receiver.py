#!/usr/bin/env python

# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.


import cache_classes

from twisted.application import internet, service
from twisted.internet import reactor
from twisted.spread import pb


class Receiver(pb.Root):
    def remote_takePond(self, pond):
        self.pond = pond
        print("got pond:", pond)  # a DuckPondCache
        self.remote_checkDucks()

    def remote_checkDucks(self):
        print("[%d] ducks: " % self.pond.count(), self.pond.getDucks())

    def remote_ignorePond(self):
        # stop watching the pond
        print("dropping pond")
        # gc causes __del__ causes 'decache' msg causes stoppedObserving
        self.pond = None

    def remote_shutdown(self):
        reactor.stop()


application = service.Application("copy_receiver")
internet.TCPServer(8800, pb.PBServerFactory(Receiver())).setServiceParent(
    service.IServiceCollection(application)
)
