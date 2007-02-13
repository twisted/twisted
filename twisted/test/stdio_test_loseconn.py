# -*- test-case-name: twisted.test.test_stdio.StandardInputOutputTestCase.test_loseConnection -*-
# Copyright (c) 2006-2007 Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Main program for the child process run by
L{twisted.test.test_stdio.StandardInputOutputTestCase.test_loseConnection} to
test that ITransport.loseConnection() works for process transports.
"""

import sys

from twisted.internet import stdio, protocol
from twisted.python import reflect

class LoseConnChild(protocol.Protocol):
    def connectionMade(self):
        self.transport.loseConnection()


    def connectionLost(self, reason):
        reactor.stop()


if __name__ == '__main__':
    reflect.namedAny(sys.argv[1]).install()
    from twisted.internet import reactor
    stdio.StandardIO(LoseConnChild())
    reactor.run()
