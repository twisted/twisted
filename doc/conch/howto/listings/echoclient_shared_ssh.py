#!/usr/bin/env python
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

if __name__ == '__main__':
    import sys
    import echoclient_shared_ssh
    from twisted.internet.task import react

    # from twisted.python.log import startLogging
    # startLogging(sys.stderr)

    react(echoclient_shared_ssh.main, sys.argv[1:])

from twisted.internet.defer import Deferred, gatherResults, inlineCallbacks
from twisted.internet.protocol import Factory, Protocol

from twisted.conch.endpoints import SSHCommandEndpoint

from echoclient_ssh import ConnectionParameters

class PrinterProtocol(Protocol):
    def dataReceived(self, data):
        print "Got some data:", data,


    def connectionLost(self, reason):
        print "Lost my connection"
        self.factory.done.callback(None)



def main(reactor, *argv):
    parameters = ConnectionParameters.fromCommandLine(reactor, argv)
    endpoint = parameters.endpointForCommand(b"/bin/cat")

    done = []
    factory = Factory()
    factory.protocol = Protocol
    d = endpoint.connect(factory)
    @inlineCallbacks
    def gotConnection(proto):
        conn = proto.transport.conn

        for i in range(50):
            factory = Factory()
            factory.protocol = PrinterProtocol
            factory.done = Deferred()
            done.append(factory.done)

            e = SSHCommandEndpoint.existingConnection(conn, b"/bin/echo %d" % (i,))
            yield e.connect(factory)

    d.addCallback(gotConnection)
    d.addCallback(lambda ignored: gatherResults(done))

    return d
