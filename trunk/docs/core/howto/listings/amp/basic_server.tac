from twisted.protocols.amp import AMP
from twisted.internet import reactor
from twisted.internet.protocol import Factory
from twisted.internet.endpoints import TCP4ServerEndpoint
from twisted.application.service import Application
from twisted.application.internet import StreamServerEndpointService

application = Application("basic AMP server")

endpoint = TCP4ServerEndpoint(reactor, 8750)
factory = Factory()
factory.protocol = AMP
service = StreamServerEndpointService(endpoint, factory)
service.setServiceParent(application)
