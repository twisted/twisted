from twisted.protocols.basic import LineReceiver
from twisted.internet import protocol, reactor

import sample


class Py(LineReceiver):

    delimiter = '\n'
    count = 0
    
    def lineReceived(self, line):
        self.count += 1

    def connectionLost(self, reason):
        print self.count


def main(py):
    factory = protocol.ServerFactory()
    if py:
        factory.protocol = Py
    else:
        import creactor # monkey patch, lalala
        factory.buildProtocol = lambda _: sample.SampleProtocol()
    reactor.listenTCP(1234, factory)
    reactor.run()


if __name__ == '__main__':
    import sys
    main(sys.argv[1] == "py")
