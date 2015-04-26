# -*- test-case-name: twisted.test.test_stdio.StandardInputOutputTests.test_hostAndPeer -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Main program for the child process run by
L{twisted.test.test_stdio.StandardInputOutputTests.test_hostAndPeer} to test
that ITransport.getHost() and ITransport.getPeer() work for process transports.
"""

__import__('_preamble')
import sys

from twisted.internet import stdio, protocol
from twisted.python import reflect

class HostPeerChild(protocol.Protocol):
    def connectionMade(self):
        self.transport.write('\n'.join([
            str(self.transport.getHost()),
            str(self.transport.getPeer())]))
        self.transport.loseConnection()


    def connectionLost(self, reason):
        reactor.stop()


if __name__ == '__main__':
    reflect.namedAny(sys.argv[1]).install()
    from twisted.internet import reactor
    stdio.StandardIO(HostPeerChild())
    reactor.run()
