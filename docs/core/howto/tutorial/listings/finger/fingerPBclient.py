# test the PB finger on port 8889
# this code is essentially the same as
# the first example in howto/pb-usage

from __future__ import print_function

from twisted.spread import pb
from twisted.internet import reactor, endpoints

def gotObject(object):
    print("got object:", object)
    object.callRemote("getUser","moshez").addCallback(gotData)
# or
#   object.callRemote("getUsers").addCallback(gotData)

def gotData(data):
    print('server sent:', data)
    reactor.stop()

def gotNoObject(reason):
    print("no object:",reason)
    reactor.stop()

factory = pb.PBClientFactory()
clientEndpoint = endpoints.clientFromString("tcp:127.0.0.1:8889")
clientEndpoint.connect(factory)
factory.getRootObject().addCallbacks(gotObject,gotNoObject)
reactor.run()

