#! /usr/bin/python

from twisted.application import service
from twisted.internet import reactor
from twisted.pb import pb

class Calculator(pb.Referenceable):
    def __init__(self):
        self.stack = []
        self.observers = []
    def remote_addObserver(self, observer):
        self.observers.append(observer)
    def log(self, msg):
        for o in self.observers:
            o.callRemote("event", msg=msg)
    def remote_removeObserver(self, observer):
        self.observers.remove(observer)
        
    def remote_push(self, num):
        self.log("push(%d)" % num)
        self.stack.append(num)
    def remote_add(self):
        self.log("add")
        arg1, arg2 = self.stack.pop(), self.stack.pop()
        self.stack.append(arg1 + arg2)
    def remote_subtract(self):
        self.log("subtract")
        arg1, arg2 = self.stack.pop(), self.stack.pop()
        self.stack.append(arg2 - arg1)
    def remote_pop(self):
        self.log("pop")
        return self.stack.pop()

tub = pb.PBService(tubID="ABCD")
tub.listenOn("tcp:12345")
tub.setLocation("localhost:12345")
url = tub.registerReference(Calculator(), "calculator")
print "the object is available at:", url

application = service.Application("pb2calculator")
tub.setServiceParent(application)
