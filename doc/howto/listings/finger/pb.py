
# testing the PB finger, this is pretty much the code from
# the first example in howto/pb-usage

from twisted.spread import pb
from twisted.internet import reactor

def gotObject(object):
    print "got object:", object
    object.callRemote("getUser","moshez").addCallback(gotData)
# or
#   object.callRemote("getUsers").addCallback(gotData)

def gotData(data):
    print 'server sent:', data
    reactor.stop()

def gotNoObject(reason):
    print "no object:",reason
    reactor.stop()
    
factory = pb.PBClientFactory()
reactor.connectTCP("127.0.0.1",8889, factory)
factory.getRootObject().addCallbacks(gotObject,gotNoObject)
reactor.run()
