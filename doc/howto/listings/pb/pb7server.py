#! /usr/bin/python

from twisted.spread import pb
from twisted.cred.authorizer import DefaultAuthorizer
import twisted.internet.app

class MyPerspective(pb.Perspective):
    def perspective_foo(self, arg):
        print "pname", self.perspectiveName, \
              "of servicename", self.getService().serviceName, \
              ":", arg
class MyService(pb.Service):
    def __init__(self, serviceName, serviceParent, authorizer=None):
        pb.Service.__init__(self, serviceName, serviceParent, authorizer)
        self.perspectiveClass = MyPerspective
    def getPerspectiveNamed(self, name):
        # create them on the fly if necessary
        p = self.perspectives.get(name, None)
        if not p:
            p = self.createPerspective(name)
        return p
    
        
# much of the following is magic
app = twisted.internet.app.Application("pb7server")

# create three services: one and two share an Authorizer (auth1).
multi = twisted.internet.app.MultiService("shared", app)
auth1 = DefaultAuthorizer(multi)
s1 = MyService("service1", multi, auth1)
s2 = MyService("service2", multi, auth1)

auth2 = DefaultAuthorizer(app)
s3 = MyService("service3", app, auth2)

# create user1 and user2 on the shared authorizer auth1. Both are allowed
# access to a perspective on both services
i1 = auth1.createIdentity("user1")
i1.setPassword("pass1")
i1.addKeyByString("service1", "perspective1.1")
i1.addKeyByString("service2", "perspective2.1")
auth1.addIdentity(i1)
i2 = auth1.createIdentity("user2")
i2.setPassword("pass2")
i2.addKeyByString("service1", "perspective1.2")
i2.addKeyByString("service2", "perspective2.2")
auth1.addIdentity(i2)

# create user3 on the non-shared auth2 Authorizer
i3 = auth2.createIdentity("user3")
i3.setPassword("pass3")
i3.addKeyByString("service3", "perspective3.3")
auth2.addIdentity(i3)

# start the application. auth1 listens on 8800, auth2 on 8801
app.listenTCP(8800, pb.BrokerFactory(pb.AuthRoot(auth1)))
app.listenTCP(8801, pb.BrokerFactory(pb.AuthRoot(auth2)))
app.run(save=0)
