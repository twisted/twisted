#!/usr/bin/env python

# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.


import copy2_classes  # needed to get ReceiverPond registered with Jelly

from twisted.application import internet, service
from twisted.internet import reactor
from twisted.spread import pb


class Receiver(pb.Root):
    def remote_takePond(self, pond):
        print(" got pond:", pond)
        print(" count %d" % pond.count())
        return "safe and sound"  # positive acknowledgement

    def remote_shutdown(self):
        reactor.stop()


application = service.Application("copy_receiver")
internet.TCPServer(8800, pb.PBServerFactory(Receiver())).setServiceParent(
    service.IServiceCollection(application)
)
