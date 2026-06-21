# -*- test-case-name: twisted.conch.test.test_conch -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.
from __future__ import annotations

import os
import socket
import subprocess
import sys
from itertools import count
from typing import Any

from zope.interface import implementer

from twisted.conch.error import ConchError
from twisted.conch.test.keydata import privateRSA_openssh, publicRSA_openssh
from twisted.conch.test.test_ssh import ConchTestRealm
from twisted.cred import portal
from twisted.internet import protocol, reactor
from twisted.internet.defer import Deferred, gatherResults, maybeDeferred
from twisted.internet.error import ProcessExitedAlready
from twisted.internet.interfaces import IReactorProcess
from twisted.internet.task import LoopingCall
from twisted.python import filepath, log, runtime
from twisted.python.filepath import FilePath
from twisted.python.procutils import which
from twisted.python.reflect import requireModule
from twisted.test.testutils import HAS_IPV6, skipWithoutIPv6
from twisted.trial.unittest import SkipTest, TestCase

try:
    from twisted.conch.test.test_ssh import (
        ConchTestServerFactory,
        conchTestPublicKeyChecker,
    )
except ImportError:
    pass

cryptography = requireModule("cryptography")

if cryptography:
    from twisted.conch.avatar import ConchUser
    from twisted.conch.ssh.session import ISession, SSHSession, wrapProtocol
else:
    from twisted.conch.interfaces import ISession

    class ConchUser:  # type: ignore[no-redef]
        pass


try:
    from twisted.conch.scripts.conch import SSHSession as _StdioInteractingSession
except ImportError as e:
    StdioInteractingSession = None
    _reason = str(e)
    del e
else:
    StdioInteractingSession = _StdioInteractingSession


_conchScript = requireModule("twisted.conch.scripts.conch")

_conchSkip = "conch is importable only on POSIX" if _conchScript is None else None


class FakeStdio:
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


class StdioInteractingSessionTests(TestCase):
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
        log.msg("ECHO CONNECTION MADE")

    def connectionLost(self, reason):
        log.msg("ECHO CONNECTION DONE")

    def dataReceived(self, data):
        self.transport.write(data)
        if b"\n" in data:
            self.transport.loseConnection()


class EchoFactory(protocol.Factory):
    protocol = Echo


class ConchTestOpenSSHProcess(protocol.ProcessProtocol):
    """
    Test protocol for launching an OpenSSH client process.

    @ivar deferred: Set by whatever uses this object. Accessed using
    L{_getDeferred}, which destroys the value so the Deferred is not
    fired twice. Fires when the process is terminated.

    @ivar expectedExitCode: If the process exit code is not C{expectedExitCode}
    the set C{deferred} will by triggerd with a failure.
    """

    deferred: Deferred[None] | None = None
    buf = b""
    problems = b""
    expectedExitCode: int = 0

    def _getDeferred(self):
        d, self.deferred = self.deferred, None
        return d

    def outReceived(self, data):
        self.buf += data

    def errReceived(self, data):
        self.problems += data

    def processEnded(self, reason):
        """
        Called when the process has ended.

        @param reason: a Failure giving the reason for the process' end.
        """
        if reason.value.exitCode != self.expectedExitCode:
            self._getDeferred().errback(
                ConchError(
                    "exit code was not {}: {} ({})".format(
                        self.expectedExitCode,
                        reason.value.exitCode,
                        self.problems.decode("charmap"),
                    )
                )
            )
        else:
            buf = self.buf.replace(b"\r\n", b"\n")
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
        @type port: L{int}
        @param port: The port on which the third-party server is listening.
        (it is assumed that the server is running on localhost).

        @type data: L{str}
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
        cc = protocol.ClientCreator(reactor, ConchTestForwardingPort, self, self.data)
        d = cc.connectTCP("127.0.0.1", self.port)
        d.addErrback(self._ebConnect)
        return d

    def _ebConnect(self, f):
        reactor.callLater(0.1, self._connect)

    def forwardingPortDisconnected(self, buffer):
        """
        The network connection has died; save the buffer of output
        from the network and attempt to quit the process gracefully,
        and then (after the reactor has spun) send it a KILL signal.
        """
        self.buffer = buffer
        self.transport.write(b"\x03")
        self.transport.loseConnection()
        reactor.callLater(0, self._reallyDie)

    def _reallyDie(self):
        try:
            self.transport.signalProcess("KILL")
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
        self.buffer = b""
        self.transport.write(self.data)

    def dataReceived(self, data):
        self.buffer += data

    def connectionLost(self, reason):
        self.protocol.forwardingPortDisconnected(self.buffer)


def _makeArgs(args: list[str], mod: str = "conch") -> list[bytes]:
    start = [
        sys.executable,
        "-c"
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
run()"""
        % mod,
    ]
    return [each.encode("utf-8") for each in [*start, *args]]


class ConchServerSetupMixin:
    if not cryptography:
        skip = "can't run without cryptography"

    @staticmethod
    def realmFactory():
        return ConchTestRealm(b"testuser")

    def _createFiles(self):
        for f in ["rsa_test", "rsa_test.pub", "kh_test"]:
            if os.path.exists(f):
                os.remove(f)
        with open("rsa_test", "wb") as f:
            f.write(privateRSA_openssh)
        with open("rsa_test.pub", "wb") as f:
            f.write(publicRSA_openssh)
        os.chmod("rsa_test", 0o600)
        permissions = FilePath("rsa_test").getPermissions()
        if permissions.group.read or permissions.other.read:
            raise SkipTest(
                "private key readable by others despite chmod;"
                " possible windows permission issue?"
                " see https://tm.tl/9767"
            )
        with open("kh_test", "wb") as f:
            f.write(b"127.0.0.1 " + publicRSA_openssh)

    def _getFreePort(self):
        s = socket.socket()
        s.bind(("", 0))
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
        self.conchServer = reactor.listenTCP(
            0, self.conchFactory, interface="127.0.0.1"
        )
        self.echoServer = reactor.listenTCP(0, EchoFactory())
        self.echoPort = self.echoServer.getHost().port
        if HAS_IPV6:
            self.echoServerV6 = reactor.listenTCP(0, EchoFactory(), interface="::1")
            self.echoPortV6 = self.echoServerV6.getHost().port

    def tearDown(self) -> Any:
        # c.f. https://github.com/twisted/twisted/issues/12417
        try:
            self.conchFactory.proto.done = 1
        except AttributeError:
            pass
        else:
            self.conchFactory.proto.transport.loseConnection()
        deferreds = [
            maybeDeferred(self.conchServer.stopListening),
            maybeDeferred(self.echoServer.stopListening),
        ]
        if HAS_IPV6:
            deferreds.append(maybeDeferred(self.echoServerV6.stopListening))
        return gatherResults(deferreds)


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
        d = self.execute("echo goodbye", ConchTestOpenSSHProcess())
        return d.addCallback(self.assertEqual, b"goodbye\n")

    def test_localToRemoteForwarding(self):
        """
        Test that we can use whatever client to forward a local port to a
        specified port on the server.
        """
        localPort = self._getFreePort()
        process = ConchTestForwardingProcess(localPort, b"test\n")
        d = self.execute(
            "", process, sshArgs="-N -L%i:127.0.0.1:%i" % (localPort, self.echoPort)
        )
        d.addCallback(self.assertEqual, b"test\n")
        return d

    def test_remoteToLocalForwarding(self):
        """
        Test that we can use whatever client to forward a port from the server
        to a port locally.
        """
        localPort = self._getFreePort()
        process = ConchTestForwardingProcess(localPort, b"test\n")
        d = self.execute(
            "", process, sshArgs="-N -R %i:127.0.0.1:%i" % (localPort, self.echoPort)
        )
        d.addCallback(self.assertEqual, b"test\n")
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
        self.channelLookup[b"session"] = SSHSession

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
            i = next(counter)
            if i == 60:
                call.stop()
                transport.session.conn.sendRequest(
                    transport.session, b"exit-status", b"\x00\x00\x00\x00"
                )
                transport.loseConnection()
            else:
                line = "line #%02d\n" % (i,)
                line = line.encode("utf-8")
                transport.write(line)

        # The timing for this loop is an educated guess (and/or the result of
        # experimentation) to exercise the case where a packet is generated
        # mid-rekey.  Since the other side of the connection is (so far) the
        # OpenSSH command line client, there's no easy way to determine when the
        # rekey has been initiated.  If there were, then generating a packet
        # immediately at that time would be a better way to test the
        # functionality being tested here.
        call = LoopingCall(write, count())
        call.start(0.01)

    def closed(self):
        """
        Ignore the close of the session.
        """

    def eofReceived(self):
        # ISession.eofReceived
        pass

    def execCommand(self, proto, command):
        # ISession.execCommand
        pass

    def getPty(self, term, windowSize, modes):
        # ISession.getPty
        pass

    def windowChanged(self, newWindowSize):
        # ISession.windowChanged
        pass


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
        d = self.execute("", process, "-o RekeyLimit=2K")

        def finished(result):
            expectedResult = "\n".join(["line #%02d" % (i,) for i in range(60)]) + "\n"
            expectedResult = expectedResult.encode("utf-8")
            self.assertEqual(result, expectedResult)

        d.addCallback(finished)
        return d


class OpenSSHClientMixin:
    if not which("ssh"):
        skip = "no ssh command-line client available"

    def execute(
        self, remoteCommand: str, process: ConchTestOpenSSHProcess, sshArgs: str = ""
    ) -> Deferred[None]:
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
        result: Deferred[None]
        result = process.deferred = Deferred()
        # Pass -F /dev/null to avoid the user's configuration file from
        # being loaded, as it may contain settings that cause our tests to
        # fail or hang.
        cmdline = (
            (
                "ssh -2 -l testuser -p %i "
                "-F /dev/null "
                "-oIdentitiesOnly=yes "
                "-oUserKnownHostsFile=kh_test "
                "-oPasswordAuthentication=no "
                # Always use the RSA key, since that's the one in kh_test.
                "-oHostKeyAlgorithms=ssh-rsa "
                "-a "
                "-i rsa_test "
            )
            + sshArgs
            + " 127.0.0.1 "
            + remoteCommand
        )
        port: int = self.conchServer.getHost().port  # type:ignore[attr-defined]
        cmds = (cmdline % port).split()
        encodedCmds = []
        for cmd in cmds:
            encodedCmds.append(cmd.encode("utf-8"))
        IReactorProcess(reactor).spawnProcess(process, which("ssh")[0], encodedCmds)
        return result


class OpenSSHKeyExchangeTests(ConchServerSetupMixin, OpenSSHClientMixin, TestCase):
    """
    Tests L{SSHTransportBase}'s key exchange algorithm compatibility with
    OpenSSH.
    """

    def assertExecuteWithKexAlgorithm(self, keyExchangeAlgo):
        """
        Call execute() method of L{OpenSSHClientMixin} with an ssh option that
        forces the exclusive use of the key exchange algorithm specified by
        keyExchangeAlgo

        @type keyExchangeAlgo: L{str}
        @param keyExchangeAlgo: The key exchange algorithm to use

        @return: L{defer.Deferred}
        """
        kexAlgorithms = []
        try:
            output = subprocess.check_output(
                [which("ssh")[0], "-Q", "kex"], stderr=subprocess.STDOUT
            )
            if not isinstance(output, str):
                output = output.decode("utf-8")
            kexAlgorithms = output.split()
        except BaseException:
            pass

        if keyExchangeAlgo not in kexAlgorithms:
            raise SkipTest(f"{keyExchangeAlgo} not supported by ssh client")

        d = self.execute(
            "echo hello",
            ConchTestOpenSSHProcess(),
            "-oKexAlgorithms=" + keyExchangeAlgo,
        )
        return d.addCallback(self.assertEqual, b"hello\n")

    def test_ECDHSHA256(self):
        """
        The ecdh-sha2-nistp256 key exchange algorithm is compatible with
        OpenSSH
        """
        return self.assertExecuteWithKexAlgorithm("ecdh-sha2-nistp256")

    def test_ECDHSHA384(self):
        """
        The ecdh-sha2-nistp384 key exchange algorithm is compatible with
        OpenSSH
        """
        return self.assertExecuteWithKexAlgorithm("ecdh-sha2-nistp384")

    def test_ECDHSHA521(self):
        """
        The ecdh-sha2-nistp521 key exchange algorithm is compatible with
        OpenSSH
        """
        return self.assertExecuteWithKexAlgorithm("ecdh-sha2-nistp521")

    def test_DH_GROUP14(self):
        """
        The diffie-hellman-group14-sha1 key exchange algorithm is compatible
        with OpenSSH.
        """
        return self.assertExecuteWithKexAlgorithm("diffie-hellman-group14-sha1")

    def test_DH_GROUP_EXCHANGE_SHA1(self):
        """
        The diffie-hellman-group-exchange-sha1 key exchange algorithm is
        compatible with OpenSSH.
        """
        return self.assertExecuteWithKexAlgorithm("diffie-hellman-group-exchange-sha1")

    def test_DH_GROUP_EXCHANGE_SHA256(self):
        """
        The diffie-hellman-group-exchange-sha256 key exchange algorithm is
        compatible with OpenSSH.
        """
        return self.assertExecuteWithKexAlgorithm(
            "diffie-hellman-group-exchange-sha256"
        )

    def test_unsupported_algorithm(self):
        """
        The list of key exchange algorithms supported
        by OpenSSH client is obtained with C{ssh -Q kex}.
        """
        self.assertRaises(
            SkipTest, self.assertExecuteWithKexAlgorithm, "unsupported-algorithm"
        )


class OpenSSHClientForwardingTests(ForwardingMixin, OpenSSHClientMixin, TestCase):
    """
    Connection forwarding tests run against the OpenSSL command line client.
    """

    @skipWithoutIPv6
    def test_localToRemoteForwardingV6(self):
        """
        Forwarding of arbitrary IPv6 TCP connections via SSH.
        """
        localPort = self._getFreePort()
        process = ConchTestForwardingProcess(localPort, b"test\n")
        d = self.execute(
            "", process, sshArgs="-N -L%i:[::1]:%i" % (localPort, self.echoPortV6)
        )
        d.addCallback(self.assertEqual, b"test\n")
        return d


class OpenSSHClientRekeyTests(RekeyTestsMixin, OpenSSHClientMixin, TestCase):
    """
    Rekeying tests run against the OpenSSL command line client.
    """


class CmdLineClientTests(ForwardingMixin, TestCase):
    """
    Connection forwarding tests run against the Conch command line client.
    """

    if runtime.platformType == "win32":
        skip = "can't run cmdline client on win32"

    def execute(
        self,
        remoteCommand: str,
        process: ConchTestOpenSSHProcess,
        sshArgs: str = "",
        conchArgs: list[str] | None = None,
        remoteHost: str = "127.0.0.1",
    ) -> Deferred[None]:
        """
        As for L{OpenSSHClientTestCase.execute}, except it runs the 'conch'
        command line tool, not 'ssh'.
        """
        if conchArgs is None:
            conchArgs = []

        process.deferred = Deferred()
        port = self.conchServer.getHost().port
        cmdtemplate = (
            "-p {} -l testuser "
            "--known-hosts kh_test "
            "--user-authentications publickey "
            "-a "
            "-i rsa_test "
            "-v ".format(port) + sshArgs + f" {remoteHost} " + remoteCommand
        )
        split = list(cmdtemplate.split())
        env = os.environ.copy()
        env["PYTHONPATH"] = os.pathsep.join(sys.path)
        IReactorProcess(reactor).spawnProcess(
            process, sys.executable, _makeArgs(conchArgs + split), env=env
        )
        return process.deferred

    def test_runWithLogFile(self):
        """
        It can store logs to a local file.
        """

        def cb_check_log(result):
            logContent = logPath.getContent()
            self.assertIn(b"twisted.conch", logContent)

        logPath = filepath.FilePath(self.mktemp())

        d = self.execute(
            remoteCommand="echo goodbye",
            process=ConchTestOpenSSHProcess(),
            conchArgs=[
                "--log",
                "--logfile",
                logPath.path,
                "--host-key-algorithms",
                "ssh-rsa",
            ],
        )

        d.addCallback(self.assertEqual, b"goodbye\n")
        d.addCallback(cb_check_log)
        return d

    def test_runWithNoHostAlgorithmsSpecified(self):
        """
        Do not use --host-key-algorithms flag on command line.
        """
        d = self.execute(
            remoteCommand="echo goodbye", process=ConchTestOpenSSHProcess()
        )

        d.addCallback(self.assertEqual, b"goodbye\n")
        return d

    def test_runWithCompressionSpecified(self) -> Deferred[None]:
        """
        Simple smoke test for '--compress' flag to ensure we can connect.
        """
        return self.execute(
            remoteCommand="echo compressed",
            process=ConchTestOpenSSHProcess(),
            conchArgs=["--compress"],
        ).addCallback(self.assertEqual, b"compressed\n")

    def test_connectToInvalidHost(self) -> Deferred[None]:
        """
        Connecting to an invalid host should fail.
        """
        expectError = ConchTestOpenSSHProcess()
        expectError.expectedExitCode = 1
        return self.execute(
            remoteCommand="echo nonfunctional",
            process=expectError,
            remoteHost="nowhere.invalid",
        )

    def test_testFailure(self) -> Deferred[None]:
        """
        L{ConchTestOpenSSHProcess} fails with a L{ConchError} if an expectation
        is not met.
        """
        expectError = ConchTestOpenSSHProcess()
        return self.assertFailure(
            self.execute(
                remoteCommand="echo checkfailure",
                process=expectError,
                remoteHost="nowhere.invalid",
            ),
            ConchError,
        )


class _FakeOptions(dict[str, object]):
    """
    Minimal stand-in for L{twisted.conch.scripts.conch.ClientOptions} that
    supports both attribute access (C{localForwards}/C{remoteForwards}) and
    C{__getitem__} for option flags.
    """

    def __init__(self, **flags):
        super().__init__(flags)
        self.localForwards = []
        self.remoteForwards = []


class _FakePort:
    """A stand-in for the object returned by C{reactor.listenTCP}."""


class _FakeTransport:
    """A stand-in transport exposing C{sendIgnore}."""

    sendIgnore = True


class _FakeForwardingConn:
    """A stand-in for the conch C{SSHConnection} used by C{onConnect}."""

    def __init__(self):
        self.transport = _FakeTransport()
        self.localForwards = []
        self.requestedRemote = []
        self.cancelledRemote = []

    def requestRemoteAddrForwarding(self, remoteAddr, connAddr):
        self.requestedRemote.append((remoteAddr, connAddr))

    def cancelRemoteAddrForwarding(self, remoteAddr):
        self.cancelledRemote.append(remoteAddr)


class ConchClientOptionsForwardingTests(TestCase):
    """
    Tests for forward-spec parsing in
    L{twisted.conch.scripts.conch.ClientOptions}.
    """

    skip = _conchSkip

    def _options(self):
        options = _conchScript.ClientOptions()
        options.localForwards = []
        options.remoteForwards = []
        return options

    def test_parseForwardSpecWithoutListenAddress(self):
        """
        A three-part spec defaults the listen address to C{127.0.0.1}.
        """
        options = self._options()
        self.assertEqual(
            options._parseForwardSpec("8080:dest:90"),
            (("127.0.0.1", 8080), ("dest", 90)),
        )

    def test_parseForwardSpecWithListenAddress(self):
        """
        A four-part spec uses the supplied listen address.
        """
        options = self._options()
        self.assertEqual(
            options._parseForwardSpec("1.2.3.4:8080:dest:90"),
            (("1.2.3.4", 8080), ("dest", 90)),
        )

    def test_parseForwardSpecTooManyParts(self):
        """
        A spec with more than one leading listen address is invalid.
        """
        options = self._options()
        self.assertIsNone(options._parseForwardSpec("a:b:8080:dest:90"))

    def test_parseForwardSpecNonNumericPorts(self):
        """
        Specs with non-numeric ports are invalid.
        """
        options = self._options()
        self.assertIsNone(options._parseForwardSpec("xx:dest:90"))
        self.assertIsNone(options._parseForwardSpec("8080:dest:yy"))

    def test_optLocalforwardValid(self):
        """
        A valid local forward spec is recorded.
        """
        options = self._options()
        options.opt_localforward("8080:dest:90")
        self.assertEqual(
            options.localForwards, [(("127.0.0.1", 8080), ("dest", 90))]
        )

    def test_optLocalforwardInvalid(self):
        """
        An invalid local forward spec exits.
        """
        options = self._options()
        self.assertRaises(SystemExit, options.opt_localforward, "x:dest:90")

    def test_optRemoteforwardValid(self):
        """
        A valid remote forward spec is recorded.
        """
        options = self._options()
        options.opt_remoteforward("8080:dest:90")
        self.assertEqual(
            options.remoteForwards, [(("127.0.0.1", 8080), ("dest", 90))]
        )

    def test_optRemoteforwardInvalid(self):
        """
        An invalid remote forward spec exits.
        """
        options = self._options()
        self.assertRaises(SystemExit, options.opt_remoteforward, "x:dest:90")


class ConchSSHConnectionForwardingTests(TestCase):
    """
    Tests for the remote-forwarding methods of
    L{twisted.conch.scripts.conch.SSHConnection}.
    """

    skip = _conchSkip

    def _makeConnection(self):
        connection = _conchScript.SSHConnection()
        connection.remoteForwards = {}
        self.sent = []
        self.deferreds = []

        def fakeSendGlobalRequest(request, data, wantReply=0):
            d = Deferred()
            self.sent.append((request, data, wantReply))
            self.deferreds.append(d)
            return d

        connection.sendGlobalRequest = fakeSendGlobalRequest
        return connection

    def test_requestRemoteAddrForwarding(self):
        """
        Requesting forwarding sends a C{tcpip-forward} global request and,
        once accepted, records the mapping keyed by the full address.
        """
        connection = self._makeConnection()
        connection.requestRemoteAddrForwarding(("127.0.0.1", 8080), ("dest", 90))
        self.assertEqual(self.sent[0][0], b"tcpip-forward")
        self.deferreds[0].callback(None)
        self.assertEqual(
            connection.remoteForwards[("127.0.0.1", 8080)], ("dest", 90)
        )

    def test_requestRemoteForwardingDelegates(self):
        """
        The legacy port-based API binds to C{127.0.0.1} and delegates.
        """
        connection = self._makeConnection()
        connection.requestRemoteForwarding(8080, ("dest", 90))
        self.assertEqual(self.sent[0][0], b"tcpip-forward")
        self.deferreds[0].callback(None)
        self.assertIn(("127.0.0.1", 8080), connection.remoteForwards)

    def test_ebRemoteForwarding(self):
        """
        A failed forwarding request is logged without raising.
        """
        from twisted.python.failure import Failure

        connection = self._makeConnection()
        connection._ebRemoteForwarding(
            Failure(ConchError("nope")), ("127.0.0.1", 8080), ("dest", 90)
        )
        self.assertNotIn(("127.0.0.1", 8080), connection.remoteForwards)

    def test_cancelRemoteAddrForwarding(self):
        """
        Cancelling sends a C{cancel-tcpip-forward} request and drops the entry.
        """
        connection = self._makeConnection()
        connection.remoteForwards = {("127.0.0.1", 8080): ("dest", 90)}
        connection.cancelRemoteAddrForwarding(("127.0.0.1", 8080))
        self.assertEqual(self.sent[0][0], b"cancel-tcpip-forward")
        self.assertNotIn(("127.0.0.1", 8080), connection.remoteForwards)

    def test_cancelRemoteForwardingDelegates(self):
        """
        The legacy port-based cancel API binds to C{127.0.0.1} and delegates.
        """
        connection = self._makeConnection()
        connection.remoteForwards = {("127.0.0.1", 8080): ("dest", 90)}
        connection.cancelRemoteForwarding(8080)
        self.assertNotIn(("127.0.0.1", 8080), connection.remoteForwards)

    def test_cancelRemoteAddrForwardingUnknown(self):
        """
        Cancelling an unknown forward is a no-op (the missing key is ignored).
        """
        connection = self._makeConnection()
        connection.remoteForwards = {}
        connection.cancelRemoteAddrForwarding(("127.0.0.1", 8080))
        self.assertEqual(self.sent[0][0], b"cancel-tcpip-forward")

    def test_channelForwardedTcpipKnown(self):
        """
        An incoming forwarded-tcpip channel for a known address opens a
        connecting channel.
        """
        connection = self._makeConnection()
        connection.remoteForwards = {("127.0.0.1", 8080): ("dest", 90)}
        data = _conchScript.forwarding.packOpen_forwarded_tcpip(
            ("127.0.0.1", 8080), ("orig", 5)
        )
        channel = connection.channel_forwarded_tcpip(2**15, 2**15, data)
        self.assertIsInstance(
            channel, _conchScript.forwarding.SSHConnectForwardingChannel
        )

    def test_channelForwardedTcpipUnknown(self):
        """
        An incoming forwarded-tcpip channel for an unknown address is rejected.
        """
        connection = self._makeConnection()
        connection.remoteForwards = {}
        data = _conchScript.forwarding.packOpen_forwarded_tcpip(
            ("127.0.0.1", 8080), ("orig", 5)
        )
        self.assertRaises(
            ConchError, connection.channel_forwarded_tcpip, 2**15, 2**15, data
        )

    def test_channelClosedStopsWhenLast(self):
        """
        When the final channel closes, the connection is stopped.
        """
        connection = self._makeConnection()
        connection.channels = {0: object()}
        self.patch(_conchScript, "options", _FakeOptions(reconnect=True))
        connection.channelClosed(object())


class ConchOnConnectTests(TestCase):
    """
    Tests for the module-level C{onConnect} and C{beforeShutdown} helpers.
    """

    skip = _conchSkip

    def test_onConnectSetsUpForwarding(self):
        """
        C{onConnect} listens for local forwards and asks for remote forwards.
        """
        conn = _FakeForwardingConn()
        options = _FakeOptions(noshell=True, agent=False, fork=False)
        options.localForwards = [(("127.0.0.1", 8080), ("dest", 90))]
        options.remoteForwards = [(("127.0.0.1", 9090), ("dest2", 91))]

        listened = []

        def fakeListenTCP(port, factory, interface=""):
            listened.append((port, interface))
            return _FakePort()

        self.patch(_conchScript, "conn", conn)
        self.patch(_conchScript, "options", options)
        self.patch(_conchScript, "_KeepAlive", lambda conn: None)
        self.patch(_conchScript.reactor, "listenTCP", fakeListenTCP)
        self.patch(
            _conchScript.reactor, "addSystemEventTrigger", lambda *a, **k: None
        )

        _conchScript.onConnect()

        self.assertEqual(listened, [(8080, "127.0.0.1")])
        self.assertEqual(len(conn.localForwards), 1)
        self.assertEqual(
            conn.requestedRemote, [(("127.0.0.1", 9090), ("dest2", 91))]
        )

    def test_beforeShutdownCancelsForwarding(self):
        """
        C{beforeShutdown} cancels each remote forward by address.
        """
        conn = _FakeForwardingConn()
        options = _FakeOptions()
        options.remoteForwards = [(("127.0.0.1", 9090), ("dest", 91))]
        self.patch(_conchScript, "conn", conn)
        self.patch(_conchScript, "options", options)

        _conchScript.beforeShutdown()

        self.assertEqual(conn.cancelledRemote, [("127.0.0.1", 9090)])


class ConchSSHSessionTests(TestCase):
    """
    Tests for L{twisted.conch.scripts.conch.SSHSession}.
    """

    skip = _conchSkip

    def test_channelOpenWithAgent(self):
        """
        With agent forwarding and no shell, C{channelOpen} requests agent
        forwarding and returns.
        """
        session = _conchScript.SSHSession()
        session.id = 0
        sent = []

        class FakeConn:
            def sendRequest(self, *args, **kwargs):
                sent.append(args)
                return Deferred()

        session.conn = FakeConn()
        self.patch(
            _conchScript, "options", _FakeOptions(agent=True, noshell=True)
        )

        session.channelOpen(None)

        self.assertEqual(len(sent), 1)

    def test_handleInputDisconnect(self):
        """
        The C{.} escape disconnects.
        """
        session = _conchScript.SSHSession()
        session.escapeMode = 2
        self.patch(
            _conchScript, "options", _FakeOptions(reconnect=True, escape=b"~")
        )

        session.handleInput(b".")

        self.assertEqual(session.escapeMode, 1)

    def test_handleInputRekey(self):
        """
        The C{R} escape triggers a rekey.
        """
        session = _conchScript.SSHSession()
        session.escapeMode = 2
        kexed = []

        class FakeTransport:
            def sendKexInit(self):
                kexed.append(True)

        class FakeConn:
            transport = FakeTransport()

        session.conn = FakeConn()
        self.patch(_conchScript, "options", _FakeOptions(escape=b"~"))

        session.handleInput(b"R")

        self.assertEqual(kexed, [True])

    def test_handleInputSuspend(self):
        """
        The C{^Z} escape schedules a suspend.
        """
        session = _conchScript.SSHSession()
        session.escapeMode = 2
        calls = []

        class FakeReactor:
            def callLater(self, *args):
                calls.append(args)

        self.patch(_conchScript, "reactor", FakeReactor())
        self.patch(_conchScript, "options", _FakeOptions(escape=b"~"))

        session.handleInput(b"\x1a")

        self.assertEqual(len(calls), 1)

    def test_extReceivedStderr(self):
        """
        Extended STDERR data is written to stderr.
        """
        from io import BytesIO

        session = _conchScript.SSHSession()
        fakeErr = BytesIO()
        self.patch(sys, "stderr", fakeErr)

        session.extReceived(
            _conchScript.connection.EXTENDED_DATA_STDERR, b"oops"
        )

        self.assertEqual(fakeErr.getvalue(), b"oops")

    def test_closed(self):
        """
        C{closed} logs without error.
        """
        session = _conchScript.SSHSession()

        class FakeConn:
            channels = {0: "channel"}

        session.conn = FakeConn()
        session.closed()

    def test_closeReceived(self):
        """
        C{closeReceived} sends a close back to the server.
        """
        session = _conchScript.SSHSession()
        closed = []

        class FakeConn:
            def sendClose(self, channel):
                closed.append(channel)

        session.conn = FakeConn()
        session.closeReceived()
        self.assertEqual(closed, [session])

    def test_requestExitStatus(self):
        """
        C{request_exit_status} records the remote exit status.
        """
        import struct

        session = _conchScript.SSHSession()
        self.patch(_conchScript, "exitStatus", 0)
        session.request_exit_status(struct.pack(">L", 7))
        self.assertEqual(_conchScript.exitStatus, 7)

    def test_enterRawModeNotATty(self):
        """
        C{_enterRawMode} warns rather than failing when stdin is not a tty.
        """

        class FakeStdin:
            def fileno(self):
                return 0

        def raiseError(fd):
            raise OSError("not a tty")

        self.patch(_conchScript, "_inRawMode", 0)
        self.patch(sys, "stdin", FakeStdin())
        self.patch(_conchScript.tty, "tcgetattr", raiseError)

        _conchScript._enterRawMode()

    def test_enterRawModeSuccess(self):
        """
        C{_enterRawMode} puts a real terminal into raw mode.
        """

        class FakeStdin:
            def fileno(self):
                return 0

        applied = []
        fakeAttrs = [0, 0, 0, 0, 0, 0, [0] * 32]

        self.patch(_conchScript, "_inRawMode", 0)
        self.patch(_conchScript, "_savedRawMode", None)
        self.patch(sys, "stdin", FakeStdin())
        self.patch(_conchScript.tty, "tcgetattr", lambda fd: fakeAttrs)
        self.patch(
            _conchScript.tty, "tcsetattr", lambda *args: applied.append(args)
        )

        _conchScript._enterRawMode()

        self.assertEqual(_conchScript._inRawMode, 1)
        self.assertEqual(len(applied), 1)


class ConchHandleErrorTests(TestCase):
    """
    Tests for the module-level C{handleError} helper.
    """

    skip = _conchSkip

    def test_handleErrorReraises(self):
        """
        C{handleError} sets the exit status, schedules a stop and re-raises.
        """
        calls = []

        class FakeReactor:
            def callLater(self, *args, **kwargs):
                calls.append(args)

        self.patch(_conchScript, "reactor", FakeReactor())
        self.patch(_conchScript, "exitStatus", 0)

        try:
            raise ValueError("boom")
        except ValueError:
            self.assertRaises(ValueError, _conchScript.handleError)

        self.assertEqual(_conchScript.exitStatus, 2)
        self.assertEqual(len(calls), 1)
        self.flushLoggedErrors(ValueError)
