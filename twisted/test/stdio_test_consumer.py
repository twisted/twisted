# -*- test-case-name: twisted.test.test_stdio.StandardInputOutputTestCase.testConsumer -*-
# Copyright (c) 2006 Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Main program for the child process run by
L{twisted.test.test_stdio.StandardInputOutputTestCase.testConsumer} to test
that process transports implement IConsumer properly.
"""

import sys

from twisted.python import log
from twisted.internet import stdio, protocol, reactor
from twisted.protocols import basic

def failed(err):
    log.startLogging(sys.stderr)
    log.err(err)

class ConsumerChild(protocol.Protocol):
    def __init__(self, junkPath):
        self.junkPath = junkPath

    def connectionMade(self):
        d = basic.FileSender().beginFileTransfer(file(self.junkPath), self.transport)
        d.addErrback(failed)
        d.addCallback(lambda ign: self.transport.loseConnection())


    def connectionLost(self, reason):
        reactor.stop()


if __name__ == '__main__':
    stdio.StandardIO(ConsumerChild(sys.argv[1]))
    reactor.run()
