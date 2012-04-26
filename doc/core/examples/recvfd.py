# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Client-side of an example for sending file descriptors between processes over
UNIX sockets.  This client connects to a server listening on a UNIX socket and
waits for one file descriptor to arrive over the connection.  It displays the
name of the file and the first 80 bytes it contains, then exits.

To runb this example, run this program with one argument: a path giving the UNIX
socket the server side of this example is already listening on.  For example:

    $ python recvfd.py /tmp/sendfd.sock

See sendfd.py for the server side of this example.
"""

if __name__ == '__main__':
    import recvfd
    raise SystemExit(recvfd.main())

import os, sys

from zope.interface import implements

from twisted.python.log import startLogging
from twisted.python.filepath import FilePath
from twisted.internet.defer import Deferred
from twisted.internet.interfaces import IFileDescriptorReceiver
from twisted.internet.protocol import Factory
from twisted.protocols.basic import LineOnlyReceiver
from twisted.internet.endpoints import UNIXClientEndpoint
from twisted.internet import reactor

class ReceiveFDProtocol(LineOnlyReceiver):
    implements(IFileDescriptorReceiver)

    descriptor = None

    def __init__(self):
        self.whenDisconnected = Deferred()


    def fileDescriptorReceived(self, descriptor):
        # Record the descriptor sent to us
        self.descriptor = descriptor


    def lineReceived(self, line):
        if self.descriptor is None:
            print "Received %r without receiving descriptor!" % (line,)
        else:
            # Use the previously received descriptor, along with the newly
            # provided information about which file it is, to present some
            # information to the user.
            data = os.read(self.descriptor, 80)
            print "Received %r from the server." % (line,)
            print "First 80 bytes are:\n%r\n" % (data,)
        os.close(self.descriptor)
        self.transport.loseConnection()


    def connectionLost(self, reason):
        self.whenDisconnected.callback(None)



def main():
    address = FilePath(sys.argv[1])

    startLogging(sys.stdout)

    factory = Factory()
    factory.protocol = ReceiveFDProtocol
    factory.quiet = True

    endpoint = UNIXClientEndpoint(reactor, address.path)
    connected = endpoint.connect(factory)

    def succeeded(client):
        return client.whenDisconnected
    def failed(reason):
        print "Could not connect:", reason.getErrorMessage()
    def disconnected(ignored):
        reactor.stop()

    connected.addCallbacks(succeeded, failed)
    connected.addCallback(disconnected)

    reactor.run()
