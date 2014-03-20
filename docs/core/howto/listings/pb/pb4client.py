#!/usr/bin/env python

# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

from twisted.spread import pb
from twisted.internet import reactor

def main():
    rootobj_def = pb.getObjectAt("localhost", 8800, 30)
    rootobj_def.addCallbacks(got_rootobj)
    obj2_def = getSomeObjectAt("localhost", 8800, 30, "two")
    obj2_def.addCallbacks(got_obj2)
    obj3_def = getSomeObjectAt("localhost", 8800, 30, "three")
    obj3_def.addCallbacks(got_obj3)
    reactor.run()

def got_rootobj(rootobj):
    print "got root object:", rootobj
    print "telling root object to do foo(A)"
    rootobj.callRemote("foo", "A")

def got_obj2(obj2):
    print "got second object:", obj2
    print "telling second object to do foo(B)"
    obj2.callRemote("foo", "B")

def got_obj3(obj3):
    print "got third object:", obj3
    print "telling third object to do foo(C)"
    obj3.callRemote("foo", "C")

class my_ObjectRetrieval(pb._ObjectRetrieval):
    def __init__(self, broker, d, objname):
        pb._ObjectRetrieval.__init__(self, broker, d)
        self.objname = objname
    def connectionMade(self):
        assert not self.term, "How did this get called?"
        x = self.broker.remoteForName(self.objname)
        del self.broker
        self.term = 1
        self.deferred.callback(x)
        
def getSomeObjectAt(host, port, timeout=None, objname="root"):
    from twisted.internet import defer
    from twisted.spread.pb import Broker, BrokerClientFactory
    d = defer.Deferred()
    b = Broker(1)
    bf = BrokerClientFactory(b)
    my_ObjectRetrieval(b, d, objname)
    if host == "unix":
        # every time you use this, God kills a kitten
        reactor.connectUNIX(port, bf, timeout)
    else:
        reactor.connectTCP(host, port, bf, timeout)
    return d

main()
