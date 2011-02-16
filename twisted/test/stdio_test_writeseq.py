# -*- test-case-name: twisted.test.test_stdio.StandardInputOutputTestCase.test_writeSequence -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Main program for the child process run by
L{twisted.test.test_stdio.StandardInputOutputTestCase.test_writeSequence} to test that
ITransport.writeSequence() works for process transports.
"""

import sys

from twisted.internet import stdio, protocol
from twisted.python import reflect

class WriteSequenceChild(protocol.Protocol):
    def connectionMade(self):
        self.transport.writeSequence(list('ok!'))
        self.transport.loseConnection()


    def connectionLost(self, reason):
        reactor.stop()


if __name__ == '__main__':
    reflect.namedAny(sys.argv[1]).install()
    from twisted.internet import reactor
    stdio.StandardIO(WriteSequenceChild())
    reactor.run()
