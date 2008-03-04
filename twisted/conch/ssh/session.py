# -*- test-case-name: twisted.conch.test.test_conch -*-
# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.

# 

"""
This module contains the implementation of SSHSession, which (by default)
allows access to a shell and a python interpreter over SSH.

Maintainer: U{Paul Swartz<mailto:z3p@twistedmatrix.com>}
"""

import struct

from twisted.internet import protocol
from twisted.python import log
from twisted.conch.interfaces import ISession
from twisted.conch.ssh import common, channel

class SSHSession(channel.SSHChannel):

    name = 'session'
    def __init__(self, *args, **kw):
        channel.SSHChannel.__init__(self, *args, **kw)
        self.buf = ''
        self.client = None
        self.session = None

    def request_subsystem(self, data):
        subsystem, ignored= common.getNS(data)
        log.msg('asking for subsystem "%s"' % subsystem)
        client = self.avatar.lookupSubsystem(subsystem, data)
        if client:
            pp = SSHSessionProcessProtocol(self)
            proto = wrapProcessProtocol(pp)
            client.makeConnection(proto)
            pp.makeConnection(wrapProtocol(client))
            self.client = pp
            return 1
        else:
            log.msg('failed to get subsystem')
            return 0

    def request_shell(self, data):
        log.msg('getting shell')
        if not self.session:
            self.session = ISession(self.avatar)
        try:
            pp = SSHSessionProcessProtocol(self)
            self.session.openShell(pp)
        except:
            log.deferr()
            return 0
        else:
            self.client = pp
            return 1

    def request_exec(self, data):
        if not self.session:
            self.session = ISession(self.avatar)
        f,data = common.getNS(data)
        log.msg('executing command "%s"' % f)
        try:
            pp = SSHSessionProcessProtocol(self)
            self.session.execCommand(pp, f)
        except:
            log.deferr()
            return 0
        else:
            self.client = pp
            return 1

    def request_pty_req(self, data):
        if not self.session:
            self.session = ISession(self.avatar)
        term, windowSize, modes = parseRequest_pty_req(data)
        log.msg('pty request: %s %s' % (term, windowSize))
        try:
            self.session.getPty(term, windowSize, modes)
        except:
            log.err()
            return 0
        else:
            return 1

    def request_window_change(self, data):
        if not self.session:
            self.session = ISession(self.avatar)
        winSize = parseRequest_window_change(data)
        try:
            self.session.windowChanged(winSize)
        except:
            log.msg('error changing window size')
            log.err()
            return 0
        else:
            return 1

    def dataReceived(self, data):
        if not self.client:
            #self.conn.sendClose(self)
            self.buf += data
            return
        self.client.transport.write(data)

    def extReceived(self, dataType, data):
        if dataType == connection.EXTENDED_DATA_STDERR:
            if self.client and hasattr(self.client.transport, 'writeErr'):
                self.client.transport.writeErr(data)
        else:
            log.msg('weird extended data: %s'%dataType)

    def eofReceived(self):
        if self.session:
            self.session.eofReceived()
        elif self.client:
            self.conn.sendClose(self)

    def closed(self):
        if self.session:
            self.session.closed()
        elif self.client:
            self.client.transport.loseConnection()

    #def closeReceived(self):
    #    self.loseConnection() # don't know what to do with this

    def loseConnection(self):
        if self.client:
            self.client.transport.loseConnection()
        channel.SSHChannel.loseConnection(self)

class _ProtocolWrapper(protocol.ProcessProtocol):
    """
    This class wraps a L{Protocol} instance in a L{ProcessProtocol} instance.
    """
    def __init__(self, proto):
        self.proto = proto

    def connectionMade(self): self.proto.connectionMade()

    def outReceived(self, data): self.proto.dataReceived(data)

    def processEnded(self, reason): self.proto.connectionLost(reason)

class _DummyTransport:

    def __init__(self, proto):
        self.proto = proto

    def dataReceived(self, data):
        self.proto.transport.write(data)

    def write(self, data):
        self.proto.dataReceived(data)

    def writeSequence(self, seq):
        self.write(''.join(seq))

    def loseConnection(self):
        self.proto.connectionLost(protocol.connectionDone)

def wrapProcessProtocol(inst):
    if isinstance(inst, protocol.Protocol):
        return _ProtocolWrapper(inst)
    else:
        return inst

def wrapProtocol(proto):
    return _DummyTransport(proto)

class SSHSessionProcessProtocol(protocol.ProcessProtocol):

#    __implements__ = I
    def __init__(self, session):
        self.session = session

    def connectionMade(self):
        if self.session.buf:
            self.transport.write(self.session.buf)
            self.session.buf = None

    def outReceived(self, data):
        self.session.write(data)

    def errReceived(self, err):
        self.session.writeExtended(connection.EXTENDED_DATA_STDERR, err)

    def inConnectionLost(self):
        self.session.conn.sendEOF(self.session)

    def connectionLost(self, reason = None):
        self.session.loseConnection()

    def processEnded(self, reason = None):
        if reason and hasattr(reason.value, 'exitCode'):
            log.msg('exitCode: %s' % repr(reason.value.exitCode))
            self.session.conn.sendRequest(self.session, 'exit-status', struct.pack('!L', reason.value.exitCode))
        self.session.loseConnection()

    # transport stuff (we are also a transport!)

    def write(self, data):
        self.session.write(data)

    def writeSequence(self, seq):
        self.session.write(''.join(seq))

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
    cols, rows, xpixel, ypixel = struct.unpack('>4L', rest[: 16])
    modes, ignored= common.getNS(rest[16:])
    winSize = (rows, cols, xpixel, ypixel)
    modes = [(ord(modes[i]), struct.unpack('>L', modes[i+1: i+5])[0]) for i in range(0, len(modes)-1, 5)]
    return term, winSize, modes

def packRequest_pty_req(term, (rows, cols, xpixel, ypixel), modes):
    """Pack a pty-req request so that it is suitable for sending.

    NOTE: modes must be packed before being sent here.
    """
    termPacked = common.NS(term)
    winSizePacked = struct.pack('>4L', cols, rows, xpixel, ypixel)
    modesPacked = common.NS(modes) # depend on the client packing modes
    return termPacked + winSizePacked + modesPacked

def parseRequest_window_change(data):
    """Parse the data from a window-change request into usuable data.

    @returns: a tuple of (rows, cols, xpixel, ypixel)
    """
    cols, rows, xpixel, ypixel = struct.unpack('>4L', data)
    return rows, cols, xpixel, ypixel

def packRequest_window_change((rows, cols, xpixel, ypixel)):
    """Pack a window-change request so that it is suitable for sending.
    """
    return struct.pack('>4L', cols, rows, xpixel, ypixel)

import connection
