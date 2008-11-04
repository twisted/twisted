# You can run this .tac file directly with:
#    twistd -ny simple.tac

from twisted.application import service, internet
from twisted.protocols import wire
from twisted.internet import protocol
from twisted.python import util

application = service.Application('test')
factory = protocol.ServerFactory()
factory.protocol = wire.Echo
internet.TCPServer(8081, factory).setServiceParent(application)
internet.TimerService(5, util.println, "--MARK--").setServiceParent(application)

class Foo(protocol.Protocol):
    def connectionMade(self):
        self.transport.write('lalala\n')
    def dataReceived(self, data):
        print `data`

factory = protocol.ClientFactory()
factory.protocol = Foo
internet.TCPClient('localhost', 8081, factory).setServiceParent(application)

class FooService(service.Service):
    def startService(self):
        service.Service.startService(self)
        print 'lala, starting'
    def stopService(self):
        service.Service.stopService(self)
        print 'lala, stopping'
        print self.parent.getServiceNamed(self.name) is self

foo = FooService()
foo.setName('foo')
foo.setServiceParent(application)
