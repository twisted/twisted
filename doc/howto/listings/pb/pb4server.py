#! /usr/bin/python

from twisted.application import service, internet
from twisted.spread import pb
        
class Echo1(pb.Root):
    def remote_foo(self, arg):
        print "Echo1.foo() got:", arg
class EchoN(pb.Referenceable):
    def __init__(self, which):
        #pb.Referenceable.__init__(self)
        self.which = which
    def remote_foo(self, arg):
        print "EchoN[%d].foo() got:" % self.which, arg

class MyBrokerFactory(pb.BrokerFactory):
    def __init__(self, objectToBroker, objectDict):
        pb.BrokerFactory.__init__(self, objectToBroker)
        self.objects = objectDict
    def buildProtocol(self, addr):
        proto = pb.BrokerFactory.buildProtocol(self, addr)
        # that added the "root" object. Now lets add the others.
        for name in self.objects.keys():
            proto.setNameForLocal(name, self.objects[name])
        return proto
        
rootobject = Echo1()
objects = {
    "one": EchoN(1),
    "two": EchoN(2),
    "three": EchoN(3),
    }
application = service.Application("pb4server")
internet.TCPServer(8800, MyBrokerFactory(rootobject,
    objects)).setServiceParent( service.IServiceCollection(application))
