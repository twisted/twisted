#!/usr/bin/env python
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

if __name__ == '__main__':
    import sys
    import sftpclient_ssh
    from twisted.internet.task import react
    react(sftpclient_ssh.main, sys.argv[1:])

from twisted.internet.defer import Deferred
from twisted.internet.protocol import Protocol
from twisted.internet.endpoints import connectProtocol

from twisted.conch.endpoints import SSHSubsystemClientEndpoint
from twisted.conch.ssh.filetransfer import FileTransferClient

from echoclient_ssh import ConnectionParameters


class CreateADirectory(FileTransferClient):

    def __init__(self):
        FileTransferClient.__init__(self)
        self.finished = Deferred()

    def connectionMade(self):
        FileTransferClient.connectionMade(self)
        d = self.makeDirectory("/tmp/foo", {})
        d.chainDeferred(self.finished)



def main(reactor, *argv):
    parameters = ConnectionParameters.fromCommandLine(reactor, argv)
    endpoint = parameters.endpointForCommand(b"/bin/cat")

    d = connectProtocol(endpoint, Protocol())

    def gotConnection(proto):
        conn = proto.transport.conn
        transferProto = CreateADirectory()
        e = SSHSubsystemClientEndpoint.existingConnection(conn, b"sftp")
        d2 = connectProtocol(e, transferProto)
        d2.addCallback(lambda x: transferProto.finished)
        return d2

    d.addCallback(gotConnection)

    return d
