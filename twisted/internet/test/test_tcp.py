# Copyright (c) 2008 Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for implementations of L{IReactorTCP}.
"""

__metaclass__ = type

import socket

from twisted.internet.test.reactormixins import ReactorBuilder
from twisted.internet.protocol import ClientFactory


class TCPClientTestsBuilder(ReactorBuilder):
    """
    Builder defining tests relating to L{IReactorTCP.connectTCP}.
    """
    def test_clientConnectionFailedStopsReactor(self):
        """
        The reactor can be stopped by a client factory's
        C{clientConnectionFailed} method.
        """
        class Stop(ClientFactory):
            def clientConnectionFailed(self, connector, reason):
                reactor.stop()
        probe = socket.socket()
        probe.bind(('127.0.0.1', 0))
        host, port = probe.getsockname()
        probe.close()
        reactor = self.buildReactor()
        reactor.connectTCP(host, port, Stop())
        reactor.run()


globals().update(TCPClientTestsBuilder.makeTestCaseClasses())
