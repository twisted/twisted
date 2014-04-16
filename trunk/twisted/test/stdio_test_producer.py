# -*- test-case-name: twisted.test.test_stdio.StandardInputOutputTestCase.test_producer -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Main program for the child process run by
L{twisted.test.test_stdio.StandardInputOutputTestCase.test_producer} to test
that process transports implement IProducer properly.
"""

import sys, _preamble

from twisted.internet import stdio, protocol
from twisted.python import log, reflect

class ProducerChild(protocol.Protocol):
    _paused = False
    buf = ''

    def connectionLost(self, reason):
        log.msg("*****OVER*****")
        reactor.callLater(1, reactor.stop)
        # reactor.stop()


    def dataReceived(self, bytes):
        self.buf += bytes
        if self._paused:
            log.startLogging(sys.stderr)
            log.msg("dataReceived while transport paused!")
            self.transport.loseConnection()
        else:
            self.transport.write(bytes)
            if self.buf.endswith('\n0\n'):
                self.transport.loseConnection()
            else:
                self.pause()


    def pause(self):
        self._paused = True
        self.transport.pauseProducing()
        reactor.callLater(0.01, self.unpause)


    def unpause(self):
        self._paused = False
        self.transport.resumeProducing()


if __name__ == '__main__':
    reflect.namedAny(sys.argv[1]).install()
    from twisted.internet import reactor
    stdio.StandardIO(ProducerChild())
    reactor.run()
