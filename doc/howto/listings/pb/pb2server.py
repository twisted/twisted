#! /usr/bin/python

from twisted.spread import pb
import twisted.internet.app

class Two(pb.Referenceable):
    def remote_print(self, arg):
        print "two.print was given", arg
        
class One(pb.Root):
    def __init__(self, two):
        #pb.Root.__init__(self)   # pb.Root doesn't implement __init__
        self.two = two
    def remote_getTwo(self):
        print "One.getTwo(), returning my two called", two
        return two
    def remote_checkTwo(self, newtwo):
        print "One.checkTwo(): comparing my two", self.two
        print "One.checkTwo(): against your two", newtwo
        if two == newtwo:
            print "One.checkTwo(): our twos are the same"
        

app = twisted.internet.app.Application("pb2server")
two = Two()
root_obj = One(two)
app.listenTCP(8800, pb.BrokerFactory(root_obj))
app.run()
