from functools import partial

from zope.interface.verify import verifyObject
from zope.interface import implementer

from twisted.python.failure import Failure
from twisted.trial.unittest import TestCase
from twisted.internet.interfaces import IStreamClientEndpoint
from twisted.internet.protocol import Factory, Protocol
from twisted.internet.defer import Deferred
from twisted.internet.error import ConnectionDone, ConnectionRefusedError

from twisted.cred.portal import Portal
from twisted.cred.checkers import InMemoryUsernamePasswordDatabaseDontUse

from twisted.conch.ssh.factory import SSHFactory
from twisted.conch.ssh.userauth import SSHUserAuthServer
from twisted.conch.ssh.connection import SSHConnection
from twisted.conch.ssh.keys import Key
from twisted.conch.error import ConchError

from twisted.internet.task import Clock
from twisted.test.proto_helpers import StringTransport
from twisted.test.iosim import connectedServerAndClient
from twisted.conch.test.keydata import publicRSA_openssh, privateRSA_openssh

from twisted.conch.endpoints import AuthenticationFailed, SSHCommandEndpoint


class NullRealm(object):
    def requestAvatar(self, avatarId, mind, *interfaces):
        raise NotImplementedError("NullRealm cannot create avatars")



class FakeClockSSHUserAuthServer(SSHUserAuthServer):
    # Simplify the tests by disconnecting after the first authentication
    # failure.  One should attempt should be sufficient to test authentication
    # success and failure.  There is an off-by-one in the implementation of
    # this feature in Conch, so set it to 0 in order to allow 1 attempt.
    attemptsBeforeDisconnect = 0

    @property
    def clock(self):
        """
        Use the reactor defined by the factory, rather than the default global
        reactor, to simplify testing (by allowing an alternate implementation
        to be supplied by tests).
        """
        return self.transport.factory.reactor



class CommandFactory(SSHFactory):
    publicKeys = {
        'ssh-rsa': Key.fromString(data=publicRSA_openssh)
    }
    privateKeys = {
        'ssh-rsa': Key.fromString(data=privateRSA_openssh)
    }
    services = {
        'ssh-userauth': FakeClockSSHUserAuthServer,
        'ssh-connection': SSHConnection
    }

# factory = _SSHSecureConnectionFactory()
# secure = factory.getSecureConnection()
# authenticated = secure.getAuthenticatedConnection()
# command = authenticated.getCommandChannel()
# transport = command.getTransport()
# clientProtocol.makeConnection(transport)


@implementer(IStreamClientEndpoint)
class SpyClientEndpoint(object):
    def connect(self, factory):
        self.result = Deferred()
        self.factory = factory
        return self.result



class SSHCommandEndpointTests(TestCase):
    """
    Tests for L{SSHCommandEndpoint}, an L{IStreamClientEndpoint}
    implementations which connects a protocol with the stdin and stdout of a
    command running in an SSH session.
    """
    def setUp(self):
        """
        Configure an SSH server with password authentication enabled for a
        well-known (to the tests) account.
        """
        self.user = b"user"
        self.password = b"password"
        self.reactor = Clock()
        self.portal = Portal(NullRealm())
        self.passwdDB = InMemoryUsernamePasswordDatabaseDontUse()
        self.passwdDB.addUser(self.user, self.password)
        self.portal.registerChecker(self.passwdDB)
        self.factory = CommandFactory()
        self.factory.reactor = self.reactor
        self.factory.portal = self.portal
        self.factory.doStart()
        self.addCleanup(self.factory.doStop)


    def connectedServerAndClient(self, serverFactory, clientFactory):
        client, server, pump = connectedServerAndClient(
            partial(serverFactory.buildProtocol, None),
            partial(clientFactory.buildProtocol, None),
        )
        return server, client, pump


    def test_interface(self):
        """
        L{SSHCommandEndpoint} instances provide L{IStreamClientEndpoint}.
        """
        endpoint = SSHCommandEndpoint(object(), b"dummy user", b"dummy command")
        self.assertTrue(verifyObject(IStreamClientEndpoint, endpoint))


    def test_connectionFailed(self):
        sshServer = SpyClientEndpoint()
        endpoint = SSHCommandEndpoint(sshServer, b"dummy user", b"/bin/ls -l")
        factory = Factory()
        factory.protocol = Protocol
        d = endpoint.connect(factory)

        sshServer.result.errback(Failure(ConnectionRefusedError()))

        self.failureResultOf(d).trap(ConnectionRefusedError)


    def test_connectionClosedBeforeSecure(self):
        sshServer = SpyClientEndpoint()
        endpoint = SSHCommandEndpoint(sshServer, b"dummy user", b"/bin/ls -l")

        factory = Factory()
        factory.protocol = Protocol
        d = endpoint.connect(factory)

        transport = StringTransport()
        client = sshServer.factory.buildProtocol(None)
        client.makeConnection(transport)
        sshServer.result.callback(client)

        client.connectionLost(Failure(ConnectionDone()))

        self.failureResultOf(d).trap(Exception) # TODO Be more specific


    def test_authenticationFailure(self):
        sshServer = SpyClientEndpoint()
        endpoint = SSHCommandEndpoint(
            sshServer, b"dummy user", b"/bin/ls -l", b"dummy password")

        factory = Factory()
        factory.protocol = Protocol
        connected = endpoint.connect(factory)

        server, client, pump = self.connectedServerAndClient(
            self.factory, sshServer.factory)

        sshServer.result.callback(client)

        # For security, the server delays password authentication failure
        # response.  Advance the simulation clock so the client sees the
        # failure.
        self.reactor.advance(server.service.passwordDelay)

        # Let the failure response traverse the "network"
        pump.flush()

        f = self.failureResultOf(connected)
        f.trap(AuthenticationFailed)
        # XXX Should assert something specific about the arguments of the
        # exception


    def test_channelOpenFailure(self):
        sshServer = SpyClientEndpoint()
        endpoint = SSHCommandEndpoint(
            sshServer, self.user, b"/bin/ls -l", password=self.password)

        factory = Factory()
        factory.protocol = Protocol
        connected = endpoint.connect(factory)

        server, client, pump = self.connectedServerAndClient(
            self.factory, sshServer.factory)

        sshServer.result.callback(client)




    def test_connect(self):
        """
        L{SSHCommandEndpoint} establishes an SSH connection, creates a channel
        in it, runs a command in that channel, and directs output from that
        command to a protocol and output from the protocol to the command.
        """
        sshServer = SpyClientEndpoint()
        endpoint = SSHCommandEndpoint(sshServer, self.user, b"/bin/ls -l")
        factory = Factory()
        factory.protocol = Protocol
        d = endpoint.connect(factory)

        client, server, pump = self.connectedServerAndClient(
            self.factory, sshServer.factory)

        print d
        print d.result
        print d.result.transport
