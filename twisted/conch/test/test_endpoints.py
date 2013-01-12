# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.conch.endpoints}.
"""

from functools import partial

from zope.interface.verify import verifyObject
from zope.interface import implementer

from twisted.python.filepath import FilePath
from twisted.python.failure import Failure
from twisted.trial.unittest import TestCase
from twisted.internet.interfaces import IStreamClientEndpoint
from twisted.internet.protocol import Factory, Protocol
from twisted.internet.defer import Deferred, succeed
from twisted.internet.error import ConnectionDone, ConnectionRefusedError

from twisted.cred.portal import Portal
from twisted.cred.checkers import InMemoryUsernamePasswordDatabaseDontUse

from twisted.conch.interfaces import IConchUser
from twisted.conch.error import ConchError, UserRejectedKey
from twisted.conch.ssh.factory import SSHFactory
from twisted.conch.ssh.userauth import SSHUserAuthServer
from twisted.conch.ssh.connection import SSHConnection
from twisted.conch.ssh.keys import Key
from twisted.conch.ssh.channel import SSHChannel
from twisted.conch.client.knownhosts import KnownHostsFile

from twisted.internet.task import Clock
from twisted.test.proto_helpers import StringTransport
from twisted.test.iosim import connectedServerAndClient
from twisted.conch.test.keydata import publicRSA_openssh, privateRSA_openssh
from twisted.conch.avatar import ConchUser

from twisted.conch.endpoints import AuthenticationFailed, SSHCommandAddress, SSHCommandEndpoint


class BrokenExecSession(SSHChannel):
    def request_exec(self, data):
        return 0



class WorkingExecSession(SSHChannel):
    def request_exec(self, data):
        return 1



class TrivialRealm(object):
    def __init__(self):
        self.channelLookup = {}

    def requestAvatar(self, avatarId, mind, *interfaces):
        avatar = ConchUser()
        avatar.channelLookup = self.channelLookup
        return (IConchUser, avatar, lambda: None)



class AddressSpyFactory(Factory):
    address = None

    def buildProtocol(self, address):
        self.address = address
        return Factory.buildProtocol(self, address)



class FixedResponseUI(object):
    def __init__(self, result):
        self.result = result


    def prompt(self, text):
        return succeed(self.result)


    def warn(self, text):
        pass



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
        self.realm = TrivialRealm()
        self.portal = Portal(self.realm)
        self.passwdDB = InMemoryUsernamePasswordDatabaseDontUse()
        self.passwdDB.addUser(self.user, self.password)
        self.portal.registerChecker(self.passwdDB)
        self.factory = CommandFactory()
        self.factory.reactor = self.reactor
        self.factory.portal = self.portal
        self.factory.doStart()
        self.addCleanup(self.factory.doStop)

        # Make the server's host key available to be verified by the client.
        self.hostKeyPath = FilePath(self.mktemp())
        self.knownHosts = KnownHostsFile(self.hostKeyPath)
        self.knownHosts.addHostKey(
            b"monkey", self.factory.publicKeys['ssh-rsa'])
        self.knownHosts.save()


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
        endpoint = SSHCommandEndpoint(
            sshServer, b"dummy user", b"/bin/ls -l",
            knownHosts=self.knownHosts, ui=FixedResponseUI(False))
        factory = Factory()
        factory.protocol = Protocol
        d = endpoint.connect(factory)

        sshServer.result.errback(Failure(ConnectionRefusedError()))

        self.failureResultOf(d).trap(ConnectionRefusedError)


    def test_connectionClosedBeforeSecure(self):
        sshServer = SpyClientEndpoint()
        endpoint = SSHCommandEndpoint(
            sshServer, b"dummy user", b"/bin/ls -l",
            knownHosts=self.knownHosts, ui=FixedResponseUI(False))

        factory = Factory()
        factory.protocol = Protocol
        d = endpoint.connect(factory)

        transport = StringTransport()
        client = sshServer.factory.buildProtocol(None)
        client.makeConnection(transport)
        sshServer.result.callback(client)

        client.connectionLost(Failure(ConnectionDone()))

        self.failureResultOf(d).trap(Exception) # TODO Be more specific


    def test_hostKeyCheckFailure(self):
        sshServer = SpyClientEndpoint()
        endpoint = SSHCommandEndpoint(
            sshServer, b"dummy user", b"/bin/ls -l",
            knownHosts=KnownHostsFile(self.mktemp()), ui=FixedResponseUI(False))

        factory = Factory()
        factory.protocol = Protocol
        connected = endpoint.connect(factory)

        server, client, pump = self.connectedServerAndClient(
            self.factory, sshServer.factory)

        sshServer.result.callback(client)

        f = self.failureResultOf(connected)
        f.trap(UserRejectedKey)


    def test_authenticationFailure(self):
        sshServer = SpyClientEndpoint()
        endpoint = SSHCommandEndpoint(
            sshServer, b"dummy user", b"/bin/ls -l", b"dummy password",
            knownHosts=self.knownHosts, ui=FixedResponseUI(False))

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

        self.assertTrue(client.transport.disconnecting)


    def test_channelOpenFailure(self):
        sshServer = SpyClientEndpoint()
        endpoint = SSHCommandEndpoint(
            sshServer, self.user, b"/bin/ls -l", password=self.password,
            knownHosts=self.knownHosts, ui=FixedResponseUI(False))

        factory = Factory()
        factory.protocol = Protocol
        connected = endpoint.connect(factory)

        server, client, pump = self.connectedServerAndClient(
            self.factory, sshServer.factory)

        sshServer.result.callback(client)

        # The server logs the channel open failure - this is expected.
        errors = self.flushLoggedErrors(ConchError)
        self.assertIn(
            'unknown channel', (errors[0].value.data, errors[0].value.value))
        self.assertEqual(1, len(errors))

        # Now deal with the results on the endpoint side.
        f = self.failureResultOf(connected)
        f.trap(ConchError)
        self.assertEqual('unknown channel', f.value.value)

        self.assertTrue(client.transport.disconnecting)


    def test_execFailure(self):
        self.realm.channelLookup[b'session'] = BrokenExecSession
        sshServer = SpyClientEndpoint()
        endpoint = SSHCommandEndpoint(
            sshServer, self.user, b"/bin/ls -l", password=self.password,
            knownHosts=self.knownHosts, ui=FixedResponseUI(False))

        factory = Factory()
        factory.protocol = Protocol
        connected = endpoint.connect(factory)

        server, client, pump = self.connectedServerAndClient(
            self.factory, sshServer.factory)

        sshServer.result.callback(client)

        f = self.failureResultOf(connected)
        f.trap(ConchError)
        self.assertEqual('channel request failed', f.value.value)

        self.assertTrue(client.transport.disconnecting)


    def test_buildProtocol(self):
        """
        Once the necessary SSH actions have completed successfully,
        L{SSHCommandEndpoint.connect} uses the factory passed to it to
        construct a protocol instance by calling its C{buildProtocol} method
        with an address object representing the SSH connection and command
        executed.
        """
        self.realm.channelLookup[b'session'] = WorkingExecSession
        sshServer = SpyClientEndpoint()
        endpoint = SSHCommandEndpoint(
            sshServer, self.user, b"/bin/ls -l", password=self.password,
            knownHosts=self.knownHosts, ui=FixedResponseUI(False))

        factory = AddressSpyFactory()
        factory.protocol = Protocol
        connected = endpoint.connect(factory)

        server, client, pump = self.connectedServerAndClient(
            self.factory, sshServer.factory)

        sshServer.result.callback(client)

        self.assertIsInstance(factory.address, SSHCommandAddress)
        self.assertEqual(factory.address.server, server.transport.getHost())
        self.assertEqual(factory.address.username, self.user)
        self.assertEqual(factory.address.command, b"/bin/ls -l")


    def test_makeConnection(self):
        """
        L{SSHCommandEndpoint} establishes an SSH connection, creates a channel
        in it, runs a command in that channel, and uses the protocol's
        C{makeConnection} to associate it with a protocol representing that
        command's stdin and stdout.
        """
        self.realm.channelLookup[b'session'] = WorkingExecSession
        sshServer = SpyClientEndpoint()
        endpoint = SSHCommandEndpoint(
            sshServer, self.user, b"/bin/ls -l", password=self.password,
            knownHosts=self.knownHosts, ui=FixedResponseUI(False))

        factory = Factory()
        factory.protocol = Protocol
        connected = endpoint.connect(factory)

        server, client, pump = self.connectedServerAndClient(
            self.factory, sshServer.factory)

        sshServer.result.callback(client)

        protocol = self.successResultOf(connected)
        self.assertNotIdentical(None, protocol.transport)


    def test_dataReceived(self):
        """
        After establishing the connection, when the command on the SSH server
        produces output, it is delivered to the protocol's C{dataReceived}
        method.
        """
        self.realm.channelLookup[b'session'] = WorkingExecSession
        sshServer = SpyClientEndpoint()
        endpoint = SSHCommandEndpoint(
            sshServer, self.user, b"/bin/ls -l", password=self.password,
            knownHosts=self.knownHosts, ui=FixedResponseUI(False))

        factory = Factory()
        factory.protocol = Protocol
        connected = endpoint.connect(factory)

        server, client, pump = self.connectedServerAndClient(
            self.factory, sshServer.factory)

        sshServer.result.callback(client)

        protocol = self.successResultOf(connected)
        dataReceived = []
        protocol.dataReceived = dataReceived.append

        server.service.channels[0].write(b"hello, world")
        pump.pump()
        self.assertEqual(b"hello, world", b"".join(dataReceived))


    def test_connectionLost(self):
        """
        When the command closes the channel, the protocol's C{connectionLost}
        method is called.
        """
        self.realm.channelLookup[b'session'] = WorkingExecSession
        sshServer = SpyClientEndpoint()
        endpoint = SSHCommandEndpoint(
            sshServer, self.user, b"/bin/ls -l", password=self.password,
            knownHosts=self.knownHosts, ui=FixedResponseUI(False))

        factory = Factory()
        factory.protocol = Protocol
        connected = endpoint.connect(factory)

        server, client, pump = self.connectedServerAndClient(
            self.factory, sshServer.factory)

        sshServer.result.callback(client)

        protocol = self.successResultOf(connected)
        connectionLost = []
        protocol.connectionLost= connectionLost.append

        server.service.channels[0].loseConnection()
        pump.pump()
        connectionLost[0].trap(ConnectionDone)


    def test_write(self):
        """
        The transport connected to the protocol has a C{write} method which
        sends bytes to the input of the command executing on the SSH server.
        """
        self.realm.channelLookup[b'session'] = WorkingExecSession
        sshServer = SpyClientEndpoint()
        endpoint = SSHCommandEndpoint(
            sshServer, self.user, b"/bin/ls -l", password=self.password,
            knownHosts=self.knownHosts, ui=FixedResponseUI(False))

        factory = Factory()
        factory.protocol = Protocol
        connected = endpoint.connect(factory)

        server, client, pump = self.connectedServerAndClient(
            self.factory, sshServer.factory)

        sshServer.result.callback(client)

        protocol = self.successResultOf(connected)

        dataReceived = []
        server.service.channels[0].dataReceived = dataReceived.append
        protocol.transport.write(b"hello, world")
        pump.pump()
        self.assertEqual(b"hello, world", b"".join(dataReceived))


    def test_writeSequence(self):
        """
        The transport connected to the protocol has a C{writeSequence} method which
        sends bytes to the input of the command executing on the SSH server.
        """
        self.realm.channelLookup[b'session'] = WorkingExecSession
        sshServer = SpyClientEndpoint()
        endpoint = SSHCommandEndpoint(
            sshServer, self.user, b"/bin/ls -l", password=self.password,
            knownHosts=self.knownHosts, ui=FixedResponseUI(False))

        factory = Factory()
        factory.protocol = Protocol
        connected = endpoint.connect(factory)

        server, client, pump = self.connectedServerAndClient(
            self.factory, sshServer.factory)

        sshServer.result.callback(client)

        protocol = self.successResultOf(connected)

        dataReceived = []
        server.service.channels[0].dataReceived = dataReceived.append
        protocol.transport.writeSequence(list(b"hello, world"))
        pump.pump()
        self.assertEqual(b"hello, world", b"".join(dataReceived))


    def test_loseConnection(self):
        """
        The transport connected to the protocol has a C{loseConnection} method
        which causes the channel in which the command is running to close and
        the overall connection to be closed.
        """
        self.realm.channelLookup[b'session'] = WorkingExecSession
        sshServer = SpyClientEndpoint()
        endpoint = SSHCommandEndpoint(
            sshServer, self.user, b"/bin/ls -l", password=self.password,
            knownHosts=self.knownHosts, ui=FixedResponseUI(False))

        factory = Factory()
        factory.protocol = Protocol
        connected = endpoint.connect(factory)

        server, client, pump = self.connectedServerAndClient(
            self.factory, sshServer.factory)

        sshServer.result.callback(client)

        protocol = self.successResultOf(connected)
        closed = []
        server.service.channels[0].closed = lambda: closed.append(True)
        protocol.transport.loseConnection()
        pump.pump()
        self.assertEqual([True], closed)
