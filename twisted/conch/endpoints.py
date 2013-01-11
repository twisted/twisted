# -*- test-case-name: twisted.conch.test.test_endpoints -*-

from zope.interface import implementer

from twisted.python.failure import Failure
from twisted.internet.interfaces import IStreamClientEndpoint
from twisted.internet.protocol import Factory
from twisted.internet.defer import Deferred, succeed

from twisted.conch.ssh.transport import SSHClientTransport
from twisted.conch.ssh.connection import SSHConnection
from twisted.conch.ssh.userauth import SSHUserAuthClient


class AuthenticationFailed(Exception):
    pass



class UserAuth(SSHUserAuthClient):
    password = None
    key = None

    def getPassword(self):
        return succeed(self.password)


class _CommandTransport(SSHClientTransport):
    _state = b'SECURING' # -> b'AUTHENTICATING' -> b'READY'

    def verifyHostKey(self, hostKey, fingerprint):
        # XXX Should actually verify something, and add tests for this failing
        return succeed(True)


    def connectionSecure(self):
        self._state = b'AUTHENTICATING'
        # command = _CommandConnection(
        #     self.factory.command,
        #     self.factory.commandProtocolFactory,
        #     self.factory.commandConnected)
        user = b'alice'
        command = SSHConnection()
        userauth = UserAuth(user, command)
        userauth.password = b'password'
        self.requestService(userauth)


    def connectionLost(self, reason):
        if self._state == b'READY':
            return

        if self._state == b'AUTHENTICATING':
            reason = Failure(AuthenticationFailed("Doh"))
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
        factory.command = self.command
        factory.commandProtocolFactory = protocolFactory
        factory.commandConnected = Deferred()

        d = self.sshClient.connect(factory)
        d.addErrback(factory.commandConnected.errback)
        return factory.commandConnected

