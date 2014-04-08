# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Server-side of an example for sending file descriptors between processes over
UNIX sockets.  This server accepts connections on a UNIX socket and sends one
file descriptor to them, along with the name of the file it is associated with.

To run this example, run this program with two arguments: a path giving a UNIX
socket to listen on (must not exist) and a path to a file to send to clients
which connect (must exist).  For example:

    $ python sendfd.py /tmp/sendfd.sock /etc/motd

It will listen for client connections until stopped (eg, using Control-C).  Most
interesting behavior happens on the client side.

See recvfd.py for the client side of this example.
"""

if __name__ == '__main__':
    import sendfd
    raise SystemExit(sendfd.main())

import sys

from twisted.python.log import startLogging
from twisted.python.filepath import FilePath
from twisted.internet.protocol import Factory
from twisted.protocols.basic import LineOnlyReceiver
from twisted.internet import reactor

class SendFDProtocol(LineOnlyReceiver):
    def connectionMade(self):
        # Open the desired file and keep a reference to it - keeping it open
        # until we know the other side has it.  Closing it early will prevent
        # it from actually being sent.
        self.fObj = self.factory.content.open()

        # Tell the transport to send it.  It is not necessarily sent when this
        # method returns.  The reactor may need to run for a while longer before
        # that happens.
        self.transport.sendFileDescriptor(self.fObj.fileno())

        # Send along *at least* one byte, since one file descriptor was sent.
        # In this case, send along the name of the file to let the other side
        # have some idea what they're getting.
        self.sendLine(self.factory.content.path)

        # Give the other side a minute to deal with this.  If they don't close
        # the connection by then, we will do it for them.
        self.timeoutCall = reactor.callLater(60, self.transport.loseConnection)


    def connectionLost(self, reason):
        # Clean up the file object, it is no longer needed.
        self.fObj.close()
        self.fObj = None

        # Clean up the timeout, if necessary.
        if self.timeoutCall.active():
            self.timeoutCall.cancel()
            self.timeoutCall = None


def main():
    address = FilePath(sys.argv[1])
    content = FilePath(sys.argv[2])

    if address.exists():
        raise SystemExit("Cannot listen on an existing path")

    if not content.isfile():
        raise SystemExit("Content file must exist")

    startLogging(sys.stdout)

    serverFactory = Factory()
    serverFactory.content = content
    serverFactory.protocol = SendFDProtocol

    port = reactor.listenUNIX(address.path, serverFactory)
    reactor.run()
