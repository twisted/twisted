"""Throughput server."""

#import proactor
#proactor.install()
import sys
from twisted.protocols.wire import Discard
from twisted.internet import protocol, reactor
from twisted.python import log
log.startLogging(sys.stdout, setStdout = False)

def main():
    f = protocol.ServerFactory()
    f.protocol = Discard
    reactor.listenTCP(8000, f)
    reactor.run()


if __name__ == '__main__':
    main()

