#! /usr/bin/python

from twisted.internet.app import Application
from twisted.internet import reactor
from twisted.spread import pb
import copy2_classes # needed to get ReceiverPond registered with Jelly

class Receiver(pb.Root):
    def remote_takePond(self, pond):
        print " got pond:", pond
        print " count %d" % pond.count()
        return "safe and sound" # positive acknowledgement
    def remote_shutdown(self):
        reactor.stop()

app = Application("copy_receiver")
app.listenTCP(8800, pb.BrokerFactory(Receiver()))
app.run(save=0)
