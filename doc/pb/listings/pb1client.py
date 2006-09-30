#! /usr/bin/python

from twisted.internet import reactor
from twisted.pb import pb

def gotError1(why):
    print "unable to get the RemoteReference:", why
    reactor.stop()

def gotError2(why):
    print "unable to invoke the remote method:", why
    reactor.stop()

def gotReference(remote):
    print "got a RemoteReference"
    print "asking it to add 1+2"
    d = remote.callRemote("add", a=1, b=2)
    d.addCallbacks(gotAnswer, gotError2)

def gotAnswer(answer):
    print "the answer is", answer
    reactor.stop()

tub = pb.PBService()
d = tub.getReference("pbu://localhost:12345/math-service")
d.addCallbacks(gotReference, gotError1)

tub.startService()
reactor.run()


