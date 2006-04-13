# -*- test-case-name: twisted.test.test_stdio.StandardInputOutputTestCase.testWrite -*-
# Copyright (c) 2006 Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Main program for the child process run by
L{twisted.test.test_stdio.StandardInputOutputTestCase.testWrite} to test that
ITransport.write() works for process transports.
"""

import sys

from twisted.internet import stdio, protocol
from twisted.python import reflect

class WriteChild(protocol.Protocol):
    def connectionMade(self):
        for ch in 'ok!':
            self.transport.write(ch)
        self.transport.loseConnection()


    def connectionLost(self, reason):
        reactor.stop()


if __name__ == '__main__':
    reflect.namedAny(sys.argv[1]).install()
    from twisted.internet import reactor
    stdio.StandardIO(WriteChild())
    reactor.run()

