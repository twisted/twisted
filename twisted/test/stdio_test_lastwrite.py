# -*- test-case-name: twisted.test.test_stdio.StandardInputOutputTestCase.test_lastWriteReceived -*-
# Copyright (c) 2007 Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Main program for the child process run by
L{twisted.test.test_stdio.StandardInputOutputTestCase.test_lastWriteReceived}
to test that L{os.write} can be reliably used after
L{twisted.internet.stdio.StandardIO} has finished.
"""

from twisted.internet.protocol import Protocol
from twisted.internet.stdio import StandardIO
from twisted.internet import reactor


class LastWriteChild(Protocol):
    def __init__(self, reactor):
        self.reactor = reactor


    def connectionMade(self):
        self.transport.write('x')
        self.transport.loseConnection()


    def connectionLost(self, reason):
        self.reactor.stop()



def main():
    p = LastWriteChild(reactor)
    StandardIO(p)
    reactor.run()


if __name__ == '__main__':
    main()
