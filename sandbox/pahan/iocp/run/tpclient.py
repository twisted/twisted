"""Throughput test."""

import time, sys
from twisted.internet import protocol
from twisted.python import log

TIMES = 10000
S = "0123456789" * 1

toSend = len(S) * TIMES

log.startLogging(sys.stdout)

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
        print "didn't succeed"
    else:
        passed = time.time() - started
        print "Throughput (send): %s kbytes/sec" % ((toSend / passed) / 1024)
    from twisted.internet import reactor
    reactor.stop()


def main():
    if sys.argv[3] == "1":
        from twisted.internet import iocpreactor
        iocpreactor.install()
    f = protocol.ClientFactory()
    f.protocol = Sender
    from twisted.internet import reactor
    for i in range(1):
        reactor.connectTCP(sys.argv[1], int(sys.argv[2]), f)
    reactor.run()


if __name__ == '__main__':
    main()

