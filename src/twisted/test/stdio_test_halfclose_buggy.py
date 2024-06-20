# -*- test-case-name: twisted.test.test_stdio.StandardInputOutputTests.test_buggyReadConnectionLost -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Main program for the child process run by
L{twisted.test.test_stdio.StandardInputOutputTests.test_readConnectionLost} to
test that IHalfCloseableProtocol.readConnectionLost works for stdio transports.
"""


import sys

from zope.interface import implementer

from twisted.internet import protocol, stdio
from twisted.internet.interfaces import IHalfCloseableProtocol, IReactorCore, ITransport
from twisted.python import log, reflect


@implementer(IHalfCloseableProtocol)
class HalfCloseProtocol(protocol.Protocol):
    """
    A protocol to hook up to stdio and observe its transport being
    half-closed.  If all goes as expected, C{exitCode} will be set to C{0};
    otherwise it will be set to C{1} to indicate failure.
    """

    exitCode = None
    transport: ITransport

    def connectionMade(self) -> None:
        """
        Signal the parent process that we're ready.
        """
        self.transport.write(b"x")

    def readConnectionLost(self) -> None:
        """
        This is the desired event.  Once it has happened, stop the reactor so
        the process will exit.
        """
        raise ValueError("something went wrong")

    def connectionLost(self, reason: object = None) -> None:
        """
        This may only be invoked after C{readConnectionLost}.  If it happens
        otherwise, mark it as an error and shut down.
        """
        self.exitCode = 0
        reactor.stop()

    def writeConnectionLost(self) -> None:
        # IHalfCloseableProtocol.writeConnectionLost
        pass


if __name__ == "__main__":  # pragma: no branch
    reflect.namedAny(sys.argv[1]).install()
    log.startLogging(open(sys.argv[2], "w"))
    reactor: IReactorCore
    from twisted.internet import reactor  # type:ignore[assignment]

    halfCloseProtocol = HalfCloseProtocol()
    stdio.StandardIO(halfCloseProtocol)
    reactor.run()
    sys.exit(halfCloseProtocol.exitCode)
