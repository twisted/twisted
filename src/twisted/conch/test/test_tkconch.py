# -*- test-case-name: twisted.conch.test.test_tkconch -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.
"""
Tests for the in-process logic of L{twisted.conch.scripts.tkconch}.

The GUI and reactor-driven entry points are exercised by the functional
tests; here we cover the option parsing and the SSH connection and session
handling that can run without a display.
"""
from __future__ import annotations

import struct
import sys
from io import BytesIO

from twisted.conch.error import ConchError
from twisted.python.reflect import requireModule
from twisted.trial.unittest import TestCase

tkconch = requireModule("twisted.conch.scripts.tkconch")

_tkconchSkip = "tkconch is not importable" if tkconch is None else None


class _FakeOptions(dict[str, object]):
    """
    Minimal stand-in for L{tkconch.GeneralOptions} supporting attribute access
    for the forward lists and C{__getitem__} for option flags.
    """

    def __init__(self, **flags):
        super().__init__(flags)
        self.localForwards = []
        self.remoteForwards = []


class _FakeReactor:
    """A stand-in reactor recording C{listenTCP} and C{stop} calls."""

    def __init__(self):
        self.listened = []
        self.stopped = 0

    def listenTCP(self, port, factory, interface=""):
        self.listened.append((port, interface))

    def stop(self):
        self.stopped += 1


class TkConchOptionsForwardingTests(TestCase):
    """
    Tests for forward-spec parsing in L{tkconch.GeneralOptions}.
    """

    skip = _tkconchSkip

    def _options(self):
        options = tkconch.GeneralOptions()
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

    def test_parseForwardSpecInvalid(self):
        """
        Specs with too many parts or non-numeric ports are invalid.
        """
        options = self._options()
        self.assertIsNone(options._parseForwardSpec("a:b:8080:dest:90"))
        self.assertIsNone(options._parseForwardSpec("xx:dest:90"))
        self.assertIsNone(options._parseForwardSpec("8080:dest:yy"))

    def test_optLocalforward(self):
        """
        A valid local forward is recorded; an invalid one exits.
        """
        options = self._options()
        options.opt_localforward("8080:dest:90")
        self.assertEqual(options.localForwards, [(("127.0.0.1", 8080), ("dest", 90))])
        self.assertRaises(SystemExit, options.opt_localforward, "x:dest:90")

    def test_optRemoteforward(self):
        """
        A valid remote forward is recorded; an invalid one exits.
        """
        options = self._options()
        options.opt_remoteforward("8080:dest:90")
        self.assertEqual(options.remoteForwards, [(("127.0.0.1", 8080), ("dest", 90))])
        self.assertRaises(SystemExit, options.opt_remoteforward, "x:dest:90")


class TkConchSSHConnectionTests(TestCase):
    """
    Tests for L{tkconch.SSHConnection}.
    """

    skip = _tkconchSkip

    def test_serviceStartedSetsUpForwarding(self):
        """
        C{serviceStarted} listens for local forwards and asks for remote ones.
        """
        connection = tkconch.SSHConnection()
        sent = []
        connection.sendGlobalRequest = lambda request, data: sent.append(request)

        options = _FakeOptions(noshell=True)
        options.localForwards = [(("127.0.0.1", 8080), ("dest", 90))]
        options.remoteForwards = [(("127.0.0.1", 9090), ("dest2", 91))]
        reactor = _FakeReactor()
        self.patch(tkconch, "options", options)
        self.patch(tkconch, "reactor", reactor)

        connection.serviceStarted()

        self.assertEqual(reactor.listened, [(8080, "127.0.0.1")])
        self.assertEqual(sent, [b"tcpip-forward"])
        self.assertEqual(connection.remoteForwards[("127.0.0.1", 9090)], ("dest2", 91))

    def test_channelForwardedTcpipKnown(self):
        """
        A forwarded-tcpip channel for a known address opens a connecting
        channel.
        """
        connection = tkconch.SSHConnection()
        connection.remoteForwards = {("127.0.0.1", 8080): ("dest", 90)}
        data = tkconch.forwarding.packOpen_forwarded_tcpip(
            ("127.0.0.1", 8080), ("orig", 5)
        )
        channel = connection.channel_forwarded_tcpip(2**15, 2**15, data)
        self.assertIsInstance(channel, tkconch.forwarding.SSHConnectForwardingChannel)

    def test_channelForwardedTcpipUnknown(self):
        """
        A forwarded-tcpip channel for an unknown address is rejected.
        """
        connection = tkconch.SSHConnection()
        connection.remoteForwards = {}
        data = tkconch.forwarding.packOpen_forwarded_tcpip(
            ("127.0.0.1", 8080), ("orig", 5)
        )
        self.assertRaises(
            ConchError, connection.channel_forwarded_tcpip, 2**15, 2**15, data
        )


class TkConchSSHSessionTests(TestCase):
    """
    Tests for L{tkconch.SSHSession}.
    """

    skip = _tkconchSkip

    def test_handleInputDisconnect(self):
        """
        The C{.} escape stops the reactor.
        """
        session = tkconch.SSHSession()
        session.escapeMode = 2
        reactor = _FakeReactor()
        self.patch(tkconch, "reactor", reactor)
        self.patch(tkconch, "options", _FakeOptions(escape="~"))

        session.handleInput(".")

        self.assertEqual(reactor.stopped, 1)

    def test_handleInputRekey(self):
        """
        The C{R} escape triggers a rekey.
        """
        session = tkconch.SSHSession()
        session.escapeMode = 2
        kexed = []

        class FakeTransport:
            def sendKexInit(self):
                kexed.append(True)

        class FakeConn:
            transport = FakeTransport()

        session.conn = FakeConn()
        self.patch(tkconch, "options", _FakeOptions(escape="~"))

        session.handleInput("R")

        self.assertEqual(kexed, [True])

    def test_extReceivedStderr(self):
        """
        Extended STDERR data is written to stderr.
        """
        session = tkconch.SSHSession()
        fakeErr = BytesIO()
        self.patch(sys, "stderr", fakeErr)

        session.extReceived(tkconch.connection.EXTENDED_DATA_STDERR, b"oops")

        self.assertEqual(fakeErr.getvalue(), b"oops")

    def test_eofReceived(self):
        """
        EOF closes stdin.
        """
        session = tkconch.SSHSession()
        closed = []

        class FakeStdin:
            def close(self):
                closed.append(True)

        self.patch(sys, "stdin", FakeStdin())

        session.eofReceived()

        self.assertEqual(closed, [True])

    def test_closedStopsWhenLast(self):
        """
        When the final channel closes, the reactor is stopped.
        """
        session = tkconch.SSHSession()
        reactor = _FakeReactor()
        self.patch(tkconch, "reactor", reactor)

        class FakeConn:
            channels = {0: "channel"}

        session.conn = FakeConn()

        session.closed()

        self.assertEqual(reactor.stopped, 1)

    def test_requestExitStatus(self):
        """
        C{request_exit_status} records the remote exit status.
        """
        session = tkconch.SSHSession()
        self.patch(tkconch, "exitStatus", 0)
        session.request_exit_status(struct.pack(">L", 7))
        self.assertEqual(tkconch.exitStatus, 7)


class TkConchHandleErrorTests(TestCase):
    """
    Tests for the module-level C{handleError} helper.
    """

    skip = _tkconchSkip

    def test_handleErrorReraises(self):
        """
        C{handleError} sets the exit status, stops the reactor and re-raises.
        """
        reactor = _FakeReactor()
        self.patch(tkconch, "reactor", reactor)
        self.patch(tkconch, "exitStatus", 0)

        try:
            raise ValueError("boom")
        except ValueError:
            self.assertRaises(ValueError, tkconch.handleError)

        self.assertEqual(tkconch.exitStatus, 2)
        self.assertEqual(reactor.stopped, 1)
        self.flushLoggedErrors(ValueError)
