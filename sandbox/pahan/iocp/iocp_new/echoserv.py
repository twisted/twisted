from twisted.internet.protocol import Protocol, Factory
import proactor
proactor.install()
from twisted.internet import reactor

### Protocol Implementation

# This is just about the simplest possible protocol
class Echo(Protocol):
    def dataReceived(self, data):
        """As soon as any data is received, write it back."""
        print "echoing %r" % (data,)
        self.transport.write(data)

def main():
    f = Factory()
    f.protocol = Echo
    reactor.listenTCP(8000, f)
    reactor.run()

if __name__ == '__main__':
    main()
