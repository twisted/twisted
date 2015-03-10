#! /usr/bin/python

from twisted.spread import pb
import twisted.internet.app
        
class ServerObject(pb.Root):
    def remote_add(self, one, two):
        answer = one + two
        print "returning result:", answer
        return answer
    def remote_subtract(self, one, two):
        return one - two
    
app = twisted.internet.app.Application("server1")
app.listenTCP(8800, pb.BrokerFactory(ServerObject()))
app.run(save=0)
