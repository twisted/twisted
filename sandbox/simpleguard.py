from twisted.cred import portal
from twisted.web import resource
from twisted.web.woven.guard import UsernamePasswordWrapper, SessionWrapper


class Authenticated:
    def __init__(self, name=None):
        self.name = name

    def __nonzero__(self):
        return bool(self.name)

class MarkAuthenticatedResource:

    __implements__ = resource.IResource,

    def __init__(self, resource, name):
        self.authenticated = Authenticated(name)
        self.resource = resource

    def render(self, request):
        request.setComponent(Authenticated, self.authenticated)
        return self.resource.render(request)

    def getChildWithDefault(self, path, request):
        request.setComponent(Authenticated, self.authenticated)
        return self.resource.getChildWithDefault(path, request)

class MarkingRealm:

    __implements__ = portal.IRealm
    def __init__(self, resource):
        self.resource = resource
        self.nonauthenticated = MarkAuthenticatedResource(resource, None)

    def requestAvatar(self, avatarId, mind, *interfaces):
        if resource.IResource not in interfaces:
            raise NotImplementedError("no interface")
        if avatarId:
            return (resource.IResource,
                    MarkAuthenticatedResource(self.resource, avatarId),
                    lambda:None)
        else:
            return resource.IResource, self.nonauthenticated, lambda:None

from twisted.web import util
from twisted.python import urlpath

class ParentRedirect(resource.Resource):
    isLeaf = 1
    def render(self, request):
        return util.redirectTo(urlpath.URLPath.fromRequest(request).here(),
                               request)

    def getChild(self, request):
        return self

def guardResource(resource, checkers, callback=lambda _: ParentRedirect()):
    myPortal = portal.Portal(MarkingRealm(resource))
    for checker in checkers:
        myPortal.registerChecker(checker)
    return SessionWrapper(UsernamePasswordWrapper(myPortal, callback=callback))

# Everything below here is user code:
if __name__ == '__main__':
    from twisted.cred import checkers
    from twisted.web import server

    class SimpleResource(resource.Resource):

        def getChild(self, path, request):
            return self

        def render(self, request):
            auth = request.getComponent(Authenticated)
            if auth:
                return "hello my friend "+auth.name
            else:
                return """
                I don't think we've met
                <a href="perspective-init">login</a>
                """


    checker = checkers.InMemoryUsernamePasswordDatabaseDontUse()
    checker.addUser("bob", "12345")
    anon = checkers.AllowAnonymousAccess()
    
    from twisted.internet import reactor
    reactor.listenTCP(8889, server.Site(
               resource = guardResource(SimpleResource(), [checker, anon])))
    reactor.run()
