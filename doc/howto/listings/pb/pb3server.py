#! /usr/bin/python

from twisted.spread import pb
import twisted.internet.app
        
class One(pb.Root):
    def remote_takeTwo(self, two):
        print "received a Two called", two
        print "telling it to print(12)"
        two.callRemote("print", 12)

app = twisted.internet.app.Application("pb3server")
app.listenTCP(8800, pb.BrokerFactory(One()))
app.run(save=0)
