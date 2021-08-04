# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.


"""
An example client. Run simpleserv.py first before running this.
"""
from zope.interface import implementer

from twisted.internet import reactor, protocol
from twisted.internet.interfaces import IProtocol


# a client protocol


@implementer(IProtocol)
class EchoClient:
    """Once connected, send a message, then print the result."""

    def makeConnection(self, transport):
        """
        Called when a new connection is made.

        C{transport} is used to send data to the remote peer.
        """
        self._transport = transport
        print(f"New connection from remote peer {transport}")
        self._transport.write(b"hello, world!")

    def connectionMade(self):
        """
        Part of IProtocol interface, but not used for non-inheritance
        based implementations.
        """

    def dataReceived(self, data):
        "As soon as any data is received, write it back."
        print("Server said:", data)
        self._transport.loseConnection()

    def connectionLost(self, reason):
        print("connection lost")


class EchoFactory(protocol.ClientFactory):
    protocol = EchoClient

    def clientConnectionFailed(self, connector, reason):
        print("Connection failed - goodbye!")
        reactor.stop()

    def clientConnectionLost(self, connector, reason):
        print("Connection lost - goodbye!")
        reactor.stop()


# this connects the protocol to a server running on port 8000
def main():
    f = EchoFactory()
    reactor.connectTCP("localhost", 8000, f)
    reactor.run()


# this only runs if the module was *not* imported
if __name__ == "__main__":
    main()
