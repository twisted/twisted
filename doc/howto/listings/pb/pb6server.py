#! /usr/bin/python

from twisted.spread import pb
from twisted.cred.authorizer import DefaultAuthorizer
import twisted.internet.app

class MyPerspective(pb.Perspective):
    def attached(self, clientref, identity):
        print "client attached! they are:", identity
        return self
    def detached(self, ref, identity):
        print "client detached! they were:", identity
    def perspective_foo(self, arg):
        print "I am", self.myname, "perspective_foo(",arg,") called on", self

# much of the following is magic
app = twisted.internet.app.Application("pb6server")
auth = DefaultAuthorizer(app)
# create the service, tell it to generate MyPerspective objects when asked
s = pb.Service("myservice", app, auth)
s.perspectiveClass = MyPerspective

#  create one MyPerspective
p1 = s.createPerspective("perspective1")
p1.myname = "p1"
# create an Identity, give it a name and password, and allow it access to
# the MyPerspective we created before
i1 = auth.createIdentity("user1")
i1.setPassword("pass1")
i1.addKeyByString("myservice", "perspective1")
auth.addIdentity(i1)

#  create another MyPerspective
p2 = s.createPerspective("perspective2")
p2.myname = "p2"
i2 = auth.createIdentity("user2")
i2.setPassword("pass2")
i2.addKeyByString("myservice", "perspective2")
auth.addIdentity(i2)


# start the application
app.listenTCP(8800, pb.BrokerFactory(pb.AuthRoot(auth)))
app.run()
