import os

from twisted.internet.protocol import Factory

from twisted.protocols.wire import Echo

from twisted.web.server import Site
from twisted.web.static import File
from twisted.web.resource import Resource
from twisted.web.websockets import WebSocketsResource


class EchoFactory(Factory):
    protocol = Echo


if __name__ == '__main__':
    from twisted.internet import reactor
    resource = WebSocketsResource(EchoFactory())
    root = Resource()
    root.putChild("ws", resource)
    path = os.path.join(os.path.dirname(__file__), "websockets_echo.html")
    root.putChild("echo", File(path))
    reactor.listenTCP(7080, Site(root))
    reactor.run()
