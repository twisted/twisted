#! /usr/bin/python

from twisted.spread import pb
import twisted.internet.app

class Two(pb.Referenceable):
    def remote_three(self, arg):
        print "Two.three was given", arg
        
class One(pb.Root):
    def remote_getTwo(self):
        two = Two()
        print "returning a Two called", two
        return two

app = twisted.internet.app.Application("pb1server")
app.listenTCP(8800, pb.BrokerFactory(One()))
app.run(save=0)
