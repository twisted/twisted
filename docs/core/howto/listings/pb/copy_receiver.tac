# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
PB copy receiver example.

This is a Twisted Application Configuration (tac) file.  Run with e.g.
   twistd -ny copy_receiver.tac

See the twistd(1) man page or
http://twistedmatrix.com/documents/current/howto/application for details.
"""


import sys

if __name__ == "__main__":
    print(__doc__)
    sys.exit(1)

from copy_sender import CopyPond, LilyPond

from twisted.application import internet, service
from twisted.internet import reactor
from twisted.python import log
from twisted.spread import pb

# log.startLogging(sys.stdout)


class ReceiverPond(pb.RemoteCopy, LilyPond):
    pass


pb.setUnjellyableForClass(CopyPond, ReceiverPond)


class Receiver(pb.Root):
    def remote_takePond(self, pond):
        print(" got pond:", pond)
        pond.countFrogs()
        return "safe and sound"  # positive acknowledgement

    def remote_shutdown(self):
        reactor.stop()


application = service.Application("copy_receiver")
internet.TCPServer(8800, pb.PBServerFactory(Receiver())).setServiceParent(
    service.IServiceCollection(application)
)
