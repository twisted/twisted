from twisted.cred import checkers
from twisted.internet import reactor
from twisted.web import server, resource
from twisted.web.woven import simpleguard

class SimpleResource(resource.Resource):

    def getChild(self, path, request):
        return self

    def render_GET(self, request):
        auth = request.getComponent(simpleguard.Authenticated)
        if auth:
            return "hello my friend "+auth.name
        else:
            return """
                I don't think we've met
        <a href="perspective-init">login</a>
            """

checker = checkers.InMemoryUsernamePasswordDatabaseDontUse()
checker.addUser("bob", "12345")

reactor.listenTCP(8889, server.Site(
      resource = simpleguard.guardResource(SimpleResource(), [checker])))
reactor.run()
