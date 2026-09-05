# -*- test-case-name: twisted.conch.test.test_session -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
This module contains the implementation of SSHSession, which (by default)
allows access to a shell and a python interpreter over SSH.

Maintainer: Paul Swartz
"""

from __future__ import annotations

import os
import signal
import struct
import sys
from collections.abc import Iterable
from functools import cached_property
from typing import Callable

from zope.interface import implementer

from twisted.conch.interfaces import (
    EnvironmentVariableNotPermitted,
    IConchUser,
    ISession,
    ISessionSetEnv,
)
from twisted.conch.ssh import channel, common, connection
from twisted.conch.ssh.connection import SSHConnection
from twisted.internet import interfaces, protocol
from twisted.internet.interfaces import IAddress, IProtocol, ITransport
from twisted.internet.protocol import Protocol
from twisted.logger import Logger
from twisted.python.compat import networkString
from twisted.python.failure import Failure

log = Logger()


class SSHSession(channel.SSHChannel):
    """
    A generalized implementation of an SSH session.

    See RFC 4254, section 6.

    The precise implementation of the various operations that the remote end
    can send is left up to the avatar, usually via an adapter to an
    interface such as L{ISession}.

    @ivar buf: a buffer for data received before making a connection to a
        client.
    @type buf: L{bytes}
    @ivar client: a protocol for communication with a shell, an application
        program, or a subsystem (see RFC 4254, section 6.5).

    @ivar session: an object providing concrete implementations of session
        operations.
    @type session: L{ISession}
    """

    name = b"session"
    client: SSHSessionProcessProtocol | None
    session: ISession | None

    def __init__(
        self,
        localWindow: int = 0,
        localMaxPacket: int = 0,
        remoteWindow: int = 0,
        remoteMaxPacket: int = 0,
        conn: SSHConnection | None = None,
        data: bytes | None = None,
        avatar: IConchUser | None = None,
    ) -> None:
        super().__init__(
            localWindow,
            localMaxPacket,
            remoteWindow,
            remoteMaxPacket,
            conn,
            data,
            avatar,
        )
        self.buf = b""
        self.client = None
        self.session = None

    @cached_property
    def _session(self) -> ISession:
        # for compatibility
        session = self.session = ISession(self.avatar)
        return session

    def _shellOrCommand(
        self,
        *,
        prepare: Callable[[], bool],
        complete: Callable[[SSHSessionProcessProtocol], None],
    ) -> int:
        """
        Dedicate this session to a specific type of shell, exec, or subsystem
        (see RFC 4254, section 6.5), of which only one may be executed per
        session.
        """
        log.info("getting")
        if not prepare():
            log.info("get fail")
            return 0
        pp = SSHSessionProcessProtocol(self)
        try:
            complete(pp)
        except Exception:
            log.failure("error getting")
            return 0
        self.client = pp
        return 1

    def request_subsystem(self, data: bytes) -> int:
        subsys: Protocol

        def prepare() -> bool:
            nonlocal subsys
            subsystem, _ = common.getNS(data)
            log.info('Asking for subsystem "{subsystem}"', subsystem=subsystem)
            assert self.avatar is not None, "should already be authenticated"
            lookup = self.avatar.lookupSubsystem(subsystem, data)
            if lookup is None:
                log.error("Failed to get subsystem")
                return False
            subsys = lookup
            return True

        def complete(pp: SSHSessionProcessProtocol) -> None:
            # was this always just broken??!
            subsys.makeConnection(wrapProcessProtocol(pp))
            pp.makeConnection(wrapProtocol(subsys))

        return self._shellOrCommand(
            prepare=prepare,
            complete=complete,
        )

    def request_shell(self, data: bytes) -> int:
        return self._shellOrCommand(
            prepare=lambda: True,
            complete=self._session.openShell,
        )

    def request_exec(self, data: bytes) -> int:
        f: bytes

        def parseNS() -> bool:
            nonlocal f
            f, _ = common.getNS(data)
            return True

        def completer(pp: SSHSessionProcessProtocol) -> None:
            log.info('Executing command "{f}"', f=f)
            self._session.execCommand(pp, f)

        return self._shellOrCommand(prepare=parseNS, complete=completer)

    def request_pty_req(self, data: bytes) -> int:
        term, windowSize, modes = parseRequest_pty_req(data)
        log.info(
            "Handling pty request: {term!r} {windowSize!r}",
            term=term,
            windowSize=windowSize,
        )
        try:
            self._session.getPty(term, windowSize, modes)
        except Exception:
            log.failure("Error handling pty request")
            return 0
        else:
            return 1

    def request_env(self, data: bytes) -> int:
        """
        Process a request to pass an environment variable.

        @param data: The environment variable name and value, each encoded
            as an SSH protocol string and concatenated.
        @type data: L{bytes}
        @return: A true value if the request to pass this environment
            variable was accepted, otherwise a false value.
        """
        hasSetEnv: ISessionSetEnv | None = ISessionSetEnv(self._session, None)
        if hasSetEnv is None:
            return 0
        name, value, data = common.getNS(data, 2)
        try:
            hasSetEnv.setEnv(name, value)
        except EnvironmentVariableNotPermitted:
            return 0
        except Exception:
            log.failure("Error setting environment variable {name}", name=name)
            return 0
        else:
            return 1

    def request_window_change(self, data: bytes) -> int:
        winSize = parseRequest_window_change(data)
        try:
            self._session.windowChanged(winSize)
        except Exception:
            log.failure("Error changing window size")
            return 0
        else:
            return 1

    def dataReceived(self, data: bytes) -> None:
        if self.client is None:
            # self.conn.sendClose(self)
            self.buf += data
            return
        # TODO: transport really might be None at runtime, if something got
        # disconnected.
        assert (
            self.client.transport is not None
        ), "client transport was no longer connected"
        self.client.transport.write(data)

    def extReceived(self, dataType: int, data: bytes) -> None:
        if dataType == connection.EXTENDED_DATA_STDERR:
            if (
                self.client
                and self.client.transport
                and hasattr(self.client.transport, "writeErr")
            ):
                self.client.transport.writeErr(data)
        else:
            log.warn("Weird extended data: {dataType}", dataType=dataType)

    def eofReceived(self) -> None:
        # If we have a session, tell it that EOF has been received and
        # expect it to send a close message (it may need to send other
        # messages such as exit-status or exit-signal first).  If we don't
        # have a session, then just send a close message directly.
        if self.session:
            self.session.eofReceived()
        elif self.client:
            assert (
                self.conn is not None
            ), "connection should be established if EOF is being received"
            self.conn.sendClose(self)

    def closed(self) -> None:
        if self.client and self.client.transport:
            self.client.transport.loseConnection()
        if self.session:
            self.session.closed()

    # def closeReceived(self):
    #    self.loseConnection() # don't know what to do with this

    def loseConnection(self) -> None:
        if self.client and self.client.transport:
            self.client.transport.loseConnection()
        channel.SSHChannel.loseConnection(self)


class _ProtocolWrapper(protocol.ProcessProtocol):
    """
    This class wraps a L{Protocol} instance in a L{ProcessProtocol} instance.
    """

    def __init__(self, proto: IProtocol):
        self.proto = proto

    def connectionMade(self) -> None:
        self.proto.connectionMade()

    def outReceived(self, data: bytes) -> None:
        self.proto.dataReceived(data)

    def processEnded(self, reason: Failure) -> None:
        self.proto.connectionLost(reason)


@implementer(ITransport)
class _DummyTransport:
    def __init__(self, proto: protocol.Protocol) -> None:
        self.proto = proto
        it = self.proto.transport
        assert it is not None, "transport must be set"
        self._transport = it

    def getHost(self) -> IAddress:
        return self._transport.getHost()

    def getPeer(self) -> IAddress:
        return self._transport.getPeer()

    def dataReceived(self, data: bytes) -> None:
        self._transport.write(data)

    def write(self, data: bytes) -> None:
        self.proto.dataReceived(data)

    def writeSequence(self, seq: Iterable[bytes]) -> None:
        self.write(b"".join(seq))

    def loseConnection(self) -> None:
        self.proto.connectionLost(protocol.connectionDone)


def wrapProcessProtocol(
    inst: IProtocol | protocol.ProcessProtocol,
) -> protocol.ProcessProtocol:
    if IProtocol.providedBy(inst):
        return _ProtocolWrapper(inst)
    else:
        return inst


def wrapProtocol(proto: protocol.Protocol) -> ITransport:
    return _DummyTransport(proto)


# SUPPORTED_SIGNALS is a list of signals that every session channel is supposed
# to accept.  See RFC 4254
SUPPORTED_SIGNALS = [
    "ABRT",
    "ALRM",
    "FPE",
    "HUP",
    "ILL",
    "INT",
    "KILL",
    "PIPE",
    "QUIT",
    "SEGV",
    "TERM",
    "USR1",
    "USR2",
]


@implementer(interfaces.ITransport)
class SSHSessionProcessProtocol(protocol.ProcessProtocol):
    """I am both an L{IProcessProtocol} and an L{ITransport}.

    I am a transport to the remote endpoint and a process protocol to the
    local subsystem.
    """

    # once initialized, a dictionary mapping signal values to strings
    # that follow RFC 4254.
    _signalValuesToNames = None

    def __init__(self, session):
        self.session = session
        self.lostOutOrErrFlag = False

    def connectionMade(self):
        if self.session.buf:
            self.transport.write(self.session.buf)
            self.session.buf = None

    def outReceived(self, data):
        self.session.write(data)

    def errReceived(self, err):
        self.session.writeExtended(connection.EXTENDED_DATA_STDERR, err)

    def outConnectionLost(self):
        """
        EOF should only be sent when both STDOUT and STDERR have been closed.
        """
        if self.lostOutOrErrFlag:
            self.session.conn.sendEOF(self.session)
        else:
            self.lostOutOrErrFlag = True

    def errConnectionLost(self):
        """
        See outConnectionLost().
        """
        self.outConnectionLost()

    def connectionLost(self, reason=None):
        self.session.loseConnection()

    def _getSignalName(self, signum):
        """
        Get a signal name given a signal number.
        """
        if self._signalValuesToNames is None:
            self._signalValuesToNames = {}
            # make sure that the POSIX ones are the defaults
            for signame in SUPPORTED_SIGNALS:
                signame = "SIG" + signame
                sigvalue = getattr(signal, signame, None)
                if sigvalue is not None:
                    self._signalValuesToNames[sigvalue] = signame
            for k, v in signal.__dict__.items():
                # Check for platform specific signals, ignoring Python specific
                # SIG_DFL and SIG_IGN
                if k.startswith("SIG") and not k.startswith("SIG_"):
                    if v not in self._signalValuesToNames:
                        self._signalValuesToNames[v] = k + "@" + sys.platform
        return self._signalValuesToNames[signum]

    def processEnded(self, reason=None):
        """
        When we are told the process ended, try to notify the other side about
        how the process ended using the exit-signal or exit-status requests.
        Also, close the channel.
        """
        if reason is not None:
            err = reason.value
            if err.signal is not None:
                signame = self._getSignalName(err.signal)
                if getattr(os, "WCOREDUMP", None) is not None and os.WCOREDUMP(
                    err.status
                ):
                    log.info("exitSignal: {signame} (core dumped)", signame=signame)
                    coreDumped = True
                else:
                    log.info("exitSignal: {}", signame=signame)
                    coreDumped = False
                self.session.conn.sendRequest(
                    self.session,
                    b"exit-signal",
                    common.NS(networkString(signame[3:]))
                    + (b"\1" if coreDumped else b"\0")
                    + common.NS(b"")
                    + common.NS(b""),
                )
            elif err.exitCode is not None:
                log.info("exitCode: {exitCode!r}", exitCode=err.exitCode)
                self.session.conn.sendRequest(
                    self.session, b"exit-status", struct.pack(">L", err.exitCode)
                )
        self.session.loseConnection()

    def getHost(self):
        """
        Return the host from my session's transport.
        """
        return self.session.conn.transport.getHost()

    def getPeer(self):
        """
        Return the peer from my session's transport.
        """
        return self.session.conn.transport.getPeer()

    def write(self, data):
        self.session.write(data)

    def writeSequence(self, seq):
        self.session.write(b"".join(seq))

    def loseConnection(self):
        self.session.loseConnection()


class SSHSessionClient(protocol.Protocol):
    def dataReceived(self, data):
        if self.transport:
            self.transport.write(data)


# methods factored out to make live easier on server writers
def parseRequest_pty_req(data):
    """Parse the data from a pty-req request into usable data.

    @returns: a tuple of (terminal type, (rows, cols, xpixel, ypixel), modes)
    """
    term, rest = common.getNS(data)
    cols, rows, xpixel, ypixel = struct.unpack(">4L", rest[:16])
    modes, ignored = common.getNS(rest[16:])
    winSize = (rows, cols, xpixel, ypixel)
    modes = [
        (ord(modes[i : i + 1]), struct.unpack(">L", modes[i + 1 : i + 5])[0])
        for i in range(0, len(modes) - 1, 5)
    ]
    return term, winSize, modes


def packRequest_pty_req(term, geometry, modes):
    """
    Pack a pty-req request so that it is suitable for sending.

    NOTE: modes must be packed before being sent here.

    @type geometry: L{tuple}
    @param geometry: A tuple of (rows, columns, xpixel, ypixel)
    """
    rows, cols, xpixel, ypixel = geometry
    termPacked = common.NS(term)
    winSizePacked = struct.pack(">4L", cols, rows, xpixel, ypixel)
    modesPacked = common.NS(modes)  # depend on the client packing modes
    return termPacked + winSizePacked + modesPacked


def parseRequest_window_change(data):
    """Parse the data from a window-change request into usuable data.

    @returns: a tuple of (rows, cols, xpixel, ypixel)
    """
    cols, rows, xpixel, ypixel = struct.unpack(">4L", data)
    return rows, cols, xpixel, ypixel


def packRequest_window_change(geometry):
    """
    Pack a window-change request so that it is suitable for sending.

    @type geometry: L{tuple}
    @param geometry: A tuple of (rows, columns, xpixel, ypixel)
    """
    rows, cols, xpixel, ypixel = geometry
    return struct.pack(">4L", cols, rows, xpixel, ypixel)
