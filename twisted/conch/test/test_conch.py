# -*- test-case-name: twisted.conch.test.test_conch -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

import os, sys, socket
from itertools import count

from zope.interface import implementer

from twisted.cred import portal
from twisted.internet import reactor, defer, protocol
from twisted.internet.error import ProcessExitedAlready
from twisted.internet.task import LoopingCall
from twisted.python import log, runtime
from twisted.trial import unittest
from twisted.conch.error import ConchError
from twisted.conch.avatar import ConchUser
from twisted.conch.ssh.session import ISession, SSHSession, wrapProtocol

try:
    from twisted.conch.scripts.conch import SSHSession as StdioInteractingSession
except ImportError, e:
    StdioInteractingSession = None
    _reason = str(e)
    del e

from twisted.conch.test.test_ssh import ConchTestRealm
from twisted.python.procutils import which

from twisted.conch.test.keydata import publicRSA_openssh, privateRSA_openssh
from twisted.conch.test.keydata import publicDSA_openssh, privateDSA_openssh

from twisted.conch.test.test_ssh import Crypto, pyasn1
try:
    from twisted.conch.test.test_ssh import ConchTestServerFactory, \
        conchTestPublicKeyChecker
except ImportError:
    pass



class FakeStdio(object):
    """
    A fake for testing L{twisted.conch.scripts.conch.SSHSession.eofReceived} and
    L{twisted.conch.scripts.cftp.SSHSession.eofReceived}.

    @ivar writeConnLost: A flag which records whether L{loserWriteConnection}
        has been called.
    """
    writeConnLost = False

    def loseWriteConnection(self):
        """
        Record the call to loseWriteConnection.
        """
        self.writeConnLost = True



class StdioInteractingSessionTests(unittest.TestCase):
    """
    Tests for L{twisted.conch.scripts.conch.SSHSession}.
    """
    if StdioInteractingSession is None:
        skip = _reason

    def test_eofReceived(self):
        """
        L{twisted.conch.scripts.conch.SSHSession.eofReceived} loses the
        write half of its stdio connection.
        """
        stdio = FakeStdio()
        channel = StdioInteractingSession()
        channel.stdio = stdio
        channel.eofReceived()
        self.assertTrue(stdio.writeConnLost)



class Echo(protocol.Protocol):
    def connectionMade(self):
        log.msg('ECHO CONNECTION MADE')


    def connectionLost(self, reason):
        log.msg('ECHO CONNECTION DONE')


    def dataReceived(self, data):
        self.transport.write(data)
        if '\n' in data:
            self.transport.loseConnection()



class EchoFactory(protocol.Factory):
    protocol = Echo



class ConchTestOpenSSHProcess(protocol.ProcessProtocol):
    """
    Test protocol for launching an OpenSSH client process.

    @ivar deferred: Set by whatever uses this object. Accessed using
    L{_getDeferred}, which destroys the value so the Deferred is not
    fired twice. Fires when the process is terminated.
    """

    deferred = None
    buf = ''

    def _getDeferred(self):
        d, self.deferred = self.deferred, None
        return d


    def outReceived(self, data):
        self.buf += data


    def processEnded(self, reason):
        """
        Called when the process has ended.

        @param reason: a Failure giving the reason for the process' end.
        """
        if reason.value.exitCode != 0:
            self._getDeferred().errback(
                ConchError("exit code was not 0: %s" %
                                 reason.value.exitCode))
        else:
            buf = self.buf.replace('\r\n', '\n')
            self._getDeferred().callback(buf)



class ConchTestForwardingProcess(protocol.ProcessProtocol):
    """
    Manages a third-party process which launches a server.

    Uses L{ConchTestForwardingPort} to connect to the third-party server.
    Once L{ConchTestForwardingPort} has disconnected, kill the process and fire
    a Deferred with the data received by the L{ConchTestForwardingPort}.

    @ivar deferred: Set by whatever uses this object. Accessed using
    L{_getDeferred}, which destroys the value so the Deferred is not
    fired twice. Fires when the process is terminated.
    """

    deferred = None

    def __init__(self, port, data):
        """
        @type port: C{int}
        @param port: The port on which the third-party server is listening.
        (it is assumed that the server is running on localhost).

        @type data: C{str}
        @param data: This is sent to the third-party server. Must end with '\n'
        in order to trigger a disconnect.
        """
        self.port = port
        self.buffer = None
        self.data = data


    def _getDeferred(self):
        d, self.deferred = self.deferred, None
        return d


    def connectionMade(self):
        self._connect()


    def _connect(self):
        """
        Connect to the server, which is often a third-party process.
        Tries to reconnect if it fails because we have no way of determining
        exactly when the port becomes available for listening -- we can only
        know when the process starts.
        """
        cc = protocol.ClientCreator(reactor, ConchTestForwardingPort, self,
                                    self.data)
        d = cc.connectTCP('127.0.0.1', self.port)
        d.addErrback(self._ebConnect)
        return d


    def _ebConnect(self, f):
        reactor.callLater(.1, self._connect)


    def forwardingPortDisconnected(self, buffer):
        """
        The network connection has died; save the buffer of output
        from the network and attempt to quit the process gracefully,
        and then (after the reactor has spun) send it a KILL signal.
        """
        self.buffer = buffer
        self.transport.write('\x03')
        self.transport.loseConnection()
        reactor.callLater(0, self._reallyDie)


    def _reallyDie(self):
        try:
            self.transport.signalProcess('KILL')
        except ProcessExitedAlready:
            pass


    def processEnded(self, reason):
        """
        Fire the Deferred at self.deferred with the data collected
        from the L{ConchTestForwardingPort} connection, if any.
        """
        self._getDeferred().callback(self.buffer)



class ConchTestForwardingPort(protocol.Protocol):
    """
    Connects to server launched by a third-party process (managed by
    L{ConchTestForwardingProcess}) sends data, then reports whatever it
    received back to the L{ConchTestForwardingProcess} once the connection
    is ended.
    """


    def __init__(self, protocol, data):
        """
        @type protocol: L{ConchTestForwardingProcess}
        @param protocol: The L{ProcessProtocol} which made this connection.

        @type data: str
        @param data: The data to be sent to the third-party server.
        """
        self.protocol = protocol
        self.data = data


    def connectionMade(self):
        self.buffer = ''
        self.transport.write(self.data)


    def dataReceived(self, data):
        self.buffer += data


    def connectionLost(self, reason):
        self.protocol.forwardingPortDisconnected(self.buffer)



def _makeArgs(args, mod="conch"):
    start = [sys.executable, '-c'
"""
### Twisted Preamble
import sys, os
path = os.path.abspath(sys.argv[0])
while os.path.dirname(path) != path:
    if os.path.basename(path).startswith('Twisted'):
        sys.path.insert(0, path)
        break
    path = os.path.dirname(path)

from twisted.conch.scripts.%s import run
run()""" % mod]
    return start + list(args)



class ConchServerSetupMixin:
    if not Crypto:
        skip = "can't run w/o PyCrypto"

    if not pyasn1:
        skip = "Cannot run without PyASN1"

    realmFactory = staticmethod(lambda: ConchTestRealm('testuser'))

    def _createFiles(self):
        for f in ['rsa_test','rsa_test.pub','dsa_test','dsa_test.pub',
                  'kh_test']:
            if os.path.exists(f):
                os.remove(f)
        open('rsa_test','w').write(privateRSA_openssh)
        open('rsa_test.pub','w').write(publicRSA_openssh)
        open('dsa_test.pub','w').write(publicDSA_openssh)
        open('dsa_test','w').write(privateDSA_openssh)
        os.chmod('dsa_test', 33152)
        os.chmod('rsa_test', 33152)
        open('kh_test','w').write('127.0.0.1 '+publicRSA_openssh)


    def _getFreePort(self):
        s = socket.socket()
        s.bind(('', 0))
        port = s.getsockname()[1]
        s.close()
        return port


    def _makeConchFactory(self):
        """
        Make a L{ConchTestServerFactory}, which allows us to start a
        L{ConchTestServer} -- i.e. an actually listening conch.
        """
        realm = self.realmFactory()
        p = portal.Portal(realm)
        p.registerChecker(conchTestPublicKeyChecker())
        factory = ConchTestServerFactory()
        factory.portal = p
        return factory


    def setUp(self):
        self._createFiles()
        self.conchFactory = self._makeConchFactory()
        self.conchFactory.expectedLoseConnection = 1
        self.conchServer = reactor.listenTCP(0, self.conchFactory,
                                             interface="127.0.0.1")
        self.echoServer = reactor.listenTCP(0, EchoFactory())
        self.echoPort = self.echoServer.getHost().port
        self.echoServerV6 = reactor.listenTCP(0, EchoFactory(), interface="::1")
        self.echoPortV6 = self.echoServerV6.getHost().port


    def tearDown(self):
        try:
            self.conchFactory.proto.done = 1
        except AttributeError:
            pass
        else:
            self.conchFactory.proto.transport.loseConnection()
        return defer.gatherResults([
                defer.maybeDeferred(self.conchServer.stopListening),
                defer.maybeDeferred(self.echoServer.stopListening),
                defer.maybeDeferred(self.echoServerV6.stopListening)])



class ForwardingMixin(ConchServerSetupMixin):
    """
    Template class for tests of the Conch server's ability to forward arbitrary
    protocols over SSH.

    These tests are integration tests, not unit tests. They launch a Conch
    server, a custom TCP server (just an L{EchoProtocol}) and then call
    L{execute}.

    L{execute} is implemented by subclasses of L{ForwardingMixin}. It should
    cause an SSH client to connect to the Conch server, asking it to forward
    data to the custom TCP server.
    """

    def test_exec(self):
        """
        Test that we can use whatever client to send the command "echo goodbye"
        to the Conch server. Make sure we receive "goodbye" back from the
        server.
        """
        d = self.execute('echo goodbye', ConchTestOpenSSHProcess())
        return d.addCallback(self.assertEqual, 'goodbye\n')


    def test_localToRemoteForwarding(self):
        """
        Test that we can use whatever client to forward a local port to a
        specified port on the server.
        """
        localPort = self._getFreePort()
        process = ConchTestForwardingProcess(localPort, 'test\n')
        d = self.execute('', process,
                         sshArgs='-N -L%i:127.0.0.1:%i'
                         % (localPort, self.echoPort))
        d.addCallback(self.assertEqual, 'test\n')
        return d


    def test_remoteToLocalForwarding(self):
        """
        Test that we can use whatever client to forward a port from the server
        to a port locally.
        """
        localPort = self._getFreePort()
        process = ConchTestForwardingProcess(localPort, 'test\n')
        d = self.execute('', process,
                         sshArgs='-N -R %i:127.0.0.1:%i'
                         % (localPort, self.echoPort))
        d.addCallback(self.assertEqual, 'test\n')
        return d



# Conventionally there is a separate adapter object which provides ISession for
# the user, but making the user provide ISession directly works too. This isn't
# a full implementation of ISession though, just enough to make these tests
# pass.
@implementer(ISession)
class RekeyAvatar(ConchUser):
    """
    This avatar implements a shell which sends 60 numbered lines to whatever
    connects to it, then closes the session with a 0 exit status.

    60 lines is selected as being enough to send more than 2kB of traffic, the
    amount the client is configured to initiate a rekey after.
    """
    def __init__(self):
        ConchUser.__init__(self)
        self.channelLookup['session'] = SSHSession


    def openShell(self, transport):
        """
        Write 60 lines of data to the transport, then exit.
        """
        proto = protocol.Protocol()
        proto.makeConnection(transport)
        transport.makeConnection(wrapProtocol(proto))

        # Send enough bytes to the connection so that a rekey is triggered in
        # the client.
        def write(counter):
            i = counter()
            if i == 60:
                call.stop()
                transport.session.conn.sendRequest(
                    transport.session, 'exit-status', '\x00\x00\x00\x00')
                transport.loseConnection()
            else:
                transport.write("line #%02d\n" % (i,))

        # The timing for this loop is an educated guess (and/or the result of
        # experimentation) to exercise the case where a packet is generated
        # mid-rekey.  Since the other side of the connection is (so far) the
        # OpenSSH command line client, there's no easy way to determine when the
        # rekey has been initiated.  If there were, then generating a packet
        # immediately at that time would be a better way to test the
        # functionality being tested here.
        call = LoopingCall(write, count().next)
        call.start(0.01)


    def closed(self):
        """
        Ignore the close of the session.
        """



class RekeyRealm:
    """
    This realm gives out new L{RekeyAvatar} instances for any avatar request.
    """
    def requestAvatar(self, avatarID, mind, *interfaces):
        return interfaces[0], RekeyAvatar(), lambda: None



class RekeyTestsMixin(ConchServerSetupMixin):
    """
    TestCase mixin which defines tests exercising L{SSHTransportBase}'s handling
    of rekeying messages.
    """
    realmFactory = RekeyRealm

    def test_clientRekey(self):
        """
        After a client-initiated rekey is completed, application data continues
        to be passed over the SSH connection.
        """
        process = ConchTestOpenSSHProcess()
        d = self.execute("", process, '-o RekeyLimit=2K')
        def finished(result):
            self.assertEqual(
                result,
                '\n'.join(['line #%02d' % (i,) for i in range(60)]) + '\n')
        d.addCallback(finished)
        return d



class OpenSSHClientMixin:
    if not which('ssh'):
        skip = "no ssh command-line client available"

    def execute(self, remoteCommand, process, sshArgs=''):
        """
        Connects to the SSH server started in L{ConchServerSetupMixin.setUp} by
        running the 'ssh' command line tool.

        @type remoteCommand: str
        @param remoteCommand: The command (with arguments) to run on the
        remote end.

        @type process: L{ConchTestOpenSSHProcess}

        @type sshArgs: str
        @param sshArgs: Arguments to pass to the 'ssh' process.

        @return: L{defer.Deferred}
        """
        process.deferred = defer.Deferred()
        cmdline = ('ssh -2 -l testuser -p %i '
                   '-oUserKnownHostsFile=kh_test '
                   '-oPasswordAuthentication=no '
                   # Always use the RSA key, since that's the one in kh_test.
                   '-oHostKeyAlgorithms=ssh-rsa '
                   '-a '
                   '-i dsa_test ') + sshArgs + \
                   ' 127.0.0.1 ' + remoteCommand
        port = self.conchServer.getHost().port
        cmds = (cmdline % port).split()
        reactor.spawnProcess(process, "ssh", cmds)
        return process.deferred



class OpenSSHClientForwardingTests(ForwardingMixin, OpenSSHClientMixin,
                                      unittest.TestCase):
    """
    Connection forwarding tests run against the OpenSSL command line client.
    """
    def test_localToRemoteForwardingV6(self):
        """
        Forwarding of arbitrary IPv6 TCP connections via SSH.
        """
        localPort = self._getFreePort()
        process = ConchTestForwardingProcess(localPort, 'test\n')
        d = self.execute('', process,
                         sshArgs='-N -L%i:[::1]:%i'
                         % (localPort, self.echoPortV6))
        d.addCallback(self.assertEqual, 'test\n')
        return d



class OpenSSHClientRekeyTests(RekeyTestsMixin, OpenSSHClientMixin,
                                 unittest.TestCase):
    """
    Rekeying tests run against the OpenSSL command line client.
    """



class CmdLineClientTests(ForwardingMixin, unittest.TestCase):
    """
    Connection forwarding tests run against the Conch command line client.
    """
    if runtime.platformType == 'win32':
        skip = "can't run cmdline client on win32"

    def execute(self, remoteCommand, process, sshArgs=''):
        """
        As for L{OpenSSHClientTestCase.execute}, except it runs the 'conch'
        command line tool, not 'ssh'.
        """
        process.deferred = defer.Deferred()
        port = self.conchServer.getHost().port
        cmd = ('-p %i -l testuser '
               '--known-hosts kh_test '
               '--user-authentications publickey '
               '--host-key-algorithms ssh-rsa '
               '-a '
               '-i dsa_test '
               '-v ') % port + sshArgs + \
               ' 127.0.0.1 ' + remoteCommand
        cmds = _makeArgs(cmd.split())
        log.msg(str(cmds))
        env = os.environ.copy()
        env['PYTHONPATH'] = os.pathsep.join(sys.path)
        reactor.spawnProcess(process, sys.executable, cmds, env=env)
        return process.deferred
