#! /usr/bin/python

from twisted.spread import pb
from twisted.cred.authorizer import DefaultAuthorizer
import twisted.internet.app

class MyPerspective(pb.Perspective):
    def perspective_foo(self, arg):
        print "I am", self.myname, "perspective_foo(",arg,") called on", self

# much of the following is magic
app = twisted.internet.app.Application("pb5server")
auth = DefaultAuthorizer(app)
# create the service, tell it to generate MyPerspective objects when asked
s = pb.Service("myservice", app, auth)
s.perspectiveClass = MyPerspective

#  create a MyPerspective
p1 = s.createPerspective("perspective1")
p1.myname = "p1"
# create an Identity, give it a name and password, and allow it access to
# the MyPerspective we created before
i1 = auth.createIdentity("user1")
i1.setPassword("pass1")
i1.addKeyByString("myservice", "perspective1")
auth.addIdentity(i1)


# start the application
app.listenTCP(8800, pb.BrokerFactory(pb.AuthRoot(auth)))
app.run(save=0)
