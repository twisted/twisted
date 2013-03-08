#! /usr/bin/python

from twisted.spread import pb
from twisted.internet import reactor

class Client:
    def connect(self):
        deferred = pb.getObjectAt("localhost", 8800, 30)
        deferred.addCallbacks(self.got_obj, self.err_obj)
        # when the Deferred fires (i.e. when the connection is established and
        # we receive a reference to the remote object), the 'got_obj' callback
        # will be run
        
    def got_obj(self, obj):
        print "got object:", obj
        self.server = obj
        print "asking it to add"
        def2 = self.server.callRemote("add", 1, 2)
        def2.addCallbacks(self.add_done, self.err)
        # this Deferred fires when the method call is complete
        
    def err_obj(self, reason):
        print "error getting object", reason
        self.quit()

    def add_done(self, result):
        print "addition complete, result is", result
        print "now trying subtract"
        d = self.server.callRemote("subtract", 5, 12)
        d.addCallbacks(self.sub_done, self.err)

    def err(self, reason):
        print "Error running remote method", reason
        self.quit()

    def sub_done(self, result):
        print "subtraction result is", result
        self.quit()
        
    def quit(self):
        print "shutting down"
        reactor.stop()
        
c = Client()
c.connect()
reactor.run()
