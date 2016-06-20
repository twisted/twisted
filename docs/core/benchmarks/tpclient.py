"""Throughput test."""
from __future__ import print_function

import time, sys
from twisted.internet import reactor, protocol
from twisted.python import log

TIMES = 10000
S = "0123456789" * 1240

toReceive = len(S) * TIMES

class Sender(protocol.Protocol):

    def connectionMade(self):
        start()
        self.numSent = 0
        self.received = 0
        self.transport.registerProducer(self, 0)

    def stopProducing(self):
        pass

    def pauseProducing(self):
        pass
    
    def resumeProducing(self):
        self.numSent += 1
        self.transport.write(S)
        if self.numSent == TIMES:
            self.transport.unregisterProducer()
            self.transport.loseConnection()

    def connectionLost(self, reason):
        shutdown(self.numSent == TIMES)


started = None

def start():
    global started
    started = time.time()

def shutdown(success):
    if not success:
        raise SystemExit("failure or something")
    passed = time.time() - started
    print("Throughput (send): %s kbytes/sec" % ((toReceive / passed) / 1024))
    reactor.stop()


def main():
    f = protocol.ClientFactory()
    f.protocol = Sender
    reactor.connectTCP(sys.argv[1], int(sys.argv[2]), f)
    reactor.run()


if __name__ == '__main__':
    #log.startLogging(sys.stdout)
    main()
