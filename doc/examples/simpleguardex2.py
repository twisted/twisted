from twisted.cred import checkers
from twisted.internet import reactor
from twisted.web import server, resource
from twisted.web.woven import simpleguard

class SimpleResource(resource.Resource):

    def getChild(self, path, request):
        return self

    def render_GET(self, request):
        name = request.getComponent(simpleguard.Authenticated).name
        return "hello my friend "+name

class HaHa(resource.Resource):

    def getChild(self, path, request):
        return self

    def render_GET(self, request):
        return """I don't know you!<br />
        <a href='perspective-init'>login</a>
        """


checker = checkers.InMemoryUsernamePasswordDatabaseDontUse()
checker.addUser("bob", "12345")

reactor.listenTCP(8889, server.Site(
      simpleguard.guardResource(SimpleResource(), [checker],
                                nonauthenticated=HaHa())))
reactor.run()
