# -*- test-case-name: twisted.conch.test.test_endpoints -*-

from zope.interface import implementer

from twisted.python.failure import Failure
from twisted.internet.error import ConnectionDone
from twisted.internet.interfaces import IStreamClientEndpoint
from twisted.internet.protocol import Factory
from twisted.internet.defer import Deferred, succeed

from twisted.conch.ssh.common import NS
from twisted.conch.ssh.transport import SSHClientTransport
from twisted.conch.ssh.connection import SSHConnection
from twisted.conch.ssh.userauth import SSHUserAuthClient
from twisted.conch.ssh.channel import SSHChannel


class AuthenticationFailed(Exception):
    pass



class SSHCommandAddress(object):
    def __init__(self, server, username, command):
        self.server = server
        self.username = username
        self.command = command



class _CommandChannel(SSHChannel):
    name = 'session'

    def __init__(self, command, protocolFactory, commandConnected):
        SSHChannel.__init__(self)
        self._command = command
        self._protocolFactory = protocolFactory
        self._commandConnected = commandConnected


    def openFailed(self, reason):
        self._commandConnected.errback(reason)


    def channelOpen(self, ignored):
        command = self.conn.sendRequest(
            self, 'exec', NS(self._command), wantReply=True)
        command.addCallbacks(self._execSuccess, self._execFailure)


    def _execFailure(self, reason):
        self._commandConnected.errback(reason)


    def _execSuccess(self, result):
        self._protocol = self._protocolFactory.buildProtocol(
            SSHCommandAddress(
                self.conn.transport.transport.getHost(),
                self.conn.transport.factory.username,
                self.conn.transport.factory.command))
        self._protocol.makeConnection(self)
        self._commandConnected.callback(self._protocol)


    def dataReceived(self, bytes):
        self._protocol.dataReceived(bytes)


    def closed(self):
        self._protocol.connectionLost(
            Failure(ConnectionDone("ssh channel closed")))



class _CommandConnection(SSHConnection):
    def __init__(self, command, protocolFactory, commandConnected):
        SSHConnection.__init__(self)
        self._command = command
        self._protocolFactory = protocolFactory
        self._commandConnected = commandConnected


    def serviceStarted(self):
        channel = _CommandChannel(
            self._command, self._protocolFactory, self._commandConnected)
        self.openChannel(channel)



class UserAuth(SSHUserAuthClient):
    password = None
    key = None

    def getPassword(self):
        return succeed(self.password)


    def ssh_USERAUTH_SUCCESS(self, packet):
        self.transport._state = b'CHANNELLING'
        return SSHUserAuthClient.ssh_USERAUTH_SUCCESS(self, packet)



class _CommandTransport(SSHClientTransport):
    _state = b'SECURING' # -> b'AUTHENTICATING' -> b'CHANNELLING' -> b'RUNNING'

    def verifyHostKey(self, hostKey, fingerprint):
        # XXX Should actually verify something, and add tests for this failing
        return succeed(True)


    def _disconnect(self, passthrough):
        self.transport.loseConnection()
        return passthrough


    def connectionSecure(self):
        self._state = b'AUTHENTICATING'

        self.factory.commandConnected.addErrback(self._disconnect)

        command = _CommandConnection(
            self.factory.command,
            self.factory.commandProtocolFactory,
            self.factory.commandConnected)
        userauth = UserAuth(self.factory.username, command)
        userauth.password = self.factory.password
        self.requestService(userauth)


    def connectionLost(self, reason):
        if self._state == b'RUNNING' or self.factory.commandConnected is None:
            return
        if self._state == b'AUTHENTICATING':
            reason = Failure(AuthenticationFailed("Doh"))
        # elif self._state == b'CHANNELLING':
        #     reason = Failure(ChannelOpenFailed("What"))
        self.factory.commandConnected.errback(reason)



@implementer(IStreamClientEndpoint)
class SSHCommandEndpoint(object):
    """
    """
    def __init__(self, sshClient, username, command, password=None):
        """
        @param sshClient: An L{IStreamClientEndpoint} to use to establish a
            connection to the SSH server.
        @type sshClient: L{IStreamClientEndpoint} provider

        @param username: The username with which to authenticate to the SSH
            server.
        @type username: L{bytes}

        @param command: The command line to execute on the SSH server.
        @type command: L{bytes}

        @param password: The password with which to authenticate to the SSH
            server, if password authentication is to be attempted (otherwise
            C{None}).
        @type password: L{bytes} or L{NoneType}
        """
        self.sshClient = sshClient
        self.username = username
        self.command = command
        self.password = password


    def connect(self, protocolFactory):
        """
        Set up an SSH connection, use a channel from that connection to launch
        a command, and hook the stdin and stdout of that command up as a
        transport for a protocol created by the given factory.

        @param protocolFactory: A L{Factory} to use to create the protocol
            which will be connected to the stdin and stdout of the command on
            the SSH server.

        @return: A L{Deferred} which will fire with an error if the connection
            cannot be set up for any reason or with the protocol instance
            created by C{protocolFactory} once it has been connected to the
            command.
        """
        factory = Factory()
        factory.protocol = _CommandTransport
        factory.username = self.username
        factory.password = self.password
        factory.command = self.command
        factory.commandProtocolFactory = protocolFactory
        factory.commandConnected = Deferred()
        factory.commandConnected.addBoth(self._clearConnected, factory)

        d = self.sshClient.connect(factory)
        d.addErrback(factory.commandConnected.errback)
        return factory.commandConnected


    def _clearConnected(self, passthrough, factory):
        factory.commandConnected = None
        return passthrough
