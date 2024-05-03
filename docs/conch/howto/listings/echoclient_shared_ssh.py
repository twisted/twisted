#!/usr/bin/env python
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

if __name__ == "__main__":
    import sys

    import echoclient_shared_ssh

    from twisted.internet.task import react

    react(echoclient_shared_ssh.main, sys.argv[1:])

from echoclient_ssh import ConnectionParameters

from twisted.conch.endpoints import SSHCommandClientEndpoint
from twisted.internet.defer import Deferred, gatherResults
from twisted.internet.protocol import Factory, Protocol
from twisted.internet.task import cooperate


class PrinterProtocol(Protocol):
    def dataReceived(self, data):
        print("Got some data:", data, end=" ")

    def connectionLost(self, reason):
        print("Lost my connection")
        self.factory.done.callback(None)


def main(reactor, *argv):
    parameters = ConnectionParameters.fromCommandLine(reactor, argv)
    endpoint = parameters.endpointForCommand(b"/bin/cat")

    done = []
    factory = Factory()
    factory.protocol = Protocol
    d = endpoint.connect(factory)

    def gotConnection(proto):
        conn = proto.transport.conn

        for i in range(50):
            factory = Factory()
            factory.protocol = PrinterProtocol
            factory.done = Deferred()
            done.append(factory.done)

            e = SSHCommandClientEndpoint.existingConnection(
                conn, b"/bin/echo %d" % (i,)
            )
            yield e.connect(factory)

    d.addCallback(gotConnection)
    d.addCallback(lambda work: cooperate(work).whenDone())
    d.addCallback(lambda ignored: gatherResults(done))

    return d
