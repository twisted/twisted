# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.
from zope.interface import implementer

from twisted.internet import reactor, protocol
from twisted.internet.interfaces import IProtocol


@implementer(IProtocol)
class Echo:
    """This is just about the simplest possible protocol"""

    def makeConnection(self, transport):
        """
        Called when a new connection is made.

        C{transport} is used to send data to the remote peer.
        """
        self._transport = transport
        print(f"New connection from remote peer {transport}")

    def connectionMade(self):
        """
        Part of IProtocol interface, but not used for non inheritance
        base implementations.
        """

    def dataReceived(self, data):
        "As soon as any data is received, write it back."
        print(f"Got: {data}")
        self._transport.write(data)

        if b"QUIT" in data:
            self._transport.loseConnection()

    def connectionLost(self, reason):
        print(f"Connection to remote peer lost. {reason}")


def main():
    """This runs the protocol on port 8000"""
    factory = protocol.ServerFactory()
    factory.protocol = Echo
    reactor.listenTCP(8000, factory)
    print("Waiting on port 8000 for new connections...")
    reactor.run()


# this only runs if the module was *not* imported
if __name__ == "__main__":
    main()
