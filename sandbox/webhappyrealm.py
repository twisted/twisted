
# implement a simple realm
from twisted.cred.portal import IRealm
from twisted.web.static import Data
from twisted.web.resource import Resource, IResource
from twisted.web.util import Redirect

class MyRealm:
    __implements__ = IRealm
    def requestAvatar(self, avatarId, mind, *interfaces):
        if IResource in interfaces:
            if avatarId:
                res = Resource()
                res.putChild("", Data("logged in as %s" % avatarId, "text/plain"))
                return IResource, res, lambda : None
            else:
                return IResource, Data("anonymous browsing - <a href='perspective-init'>login</a>", "text/html"), lambda : None
        else:
            raise NotImplementedError("no interface")

theRealm = MyRealm()

# get our password checker ready
from twisted.cred.checkers import InMemoryUsernamePasswordDatabaseDontUse, AllowAnonymousAccess

checker = InMemoryUsernamePasswordDatabaseDontUse()
checker.addUser("bob", "12345")

anon = AllowAnonymousAccess()

# authenticatiferize it
from twisted.cred.portal import Portal

usersOnly = Portal(theRealm)
usersOnly.registerChecker(checker)

usersAndAnon = Portal(theRealm)
usersAndAnon.registerChecker(checker)
usersAndAnon.registerChecker(anon)

# create the intarweb
from twisted.web.server import Site
res = Resource()
sit = Site(res)
res.putChild("", Data("<html><a href='site1'>site1</a><br/><a href='site2'>site2</a></html>", "text/html"))

def redir(foo):
    return Redirect('/site2')

# put our sites online
from twisted.web.woven.guard import UsernamePasswordWrapper, SessionWrapper
res.putChild("site1", SessionWrapper(UsernamePasswordWrapper(usersOnly)))
res.putChild("site2", SessionWrapper(UsernamePasswordWrapper(usersAndAnon, callback=redir)))

# and finally talk to the internat
from twisted.internet import reactor
reactor.listenTCP(8080, sit)
reactor.run()
