import os

from twisted.internet.protocol import Factory
from twisted.application.internet import TCPServer
from twisted.application.service import Application

from twisted.protocols.wire import Echo

from twisted.web.server import Site
from twisted.web.static import File
from twisted.web.resource import Resource
from twisted.web.websockets import WebSocketsResource, lookupProtocolForFactory


class EchoFactory(Factory):
    protocol = Echo


resource = WebSocketsResource(lookupProtocolForFactory(EchoFactory()))
root = Resource()
path = os.path.join(os.path.dirname(__file__), "websockets_echo.html")
root.putChild("", File(path))
root.putChild("ws", resource)

application = Application("websocket-echo")
server = TCPServer(7080, Site(root))
server.setServiceParent(application)
