# Twisted, the Framework of Your Internet
# Copyright (C) 2001-2002 Matthew W. Lefkowitz
# 
# This library is free software; you can redistribute it and/or
# modify it under the terms of version 2.1 of the GNU Lesser General Public
# License as published by the Free Software Foundation.
# 
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
# 
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
# 

"""This module contains the implementation of SSHSession, which (by default)
allows access to a shell and a python interpreter over SSH.

This module is unstable.

Maintainer: U{Paul Swartz<mailto:z3p@twistedmatrix.com>}
"""

import struct

from twisted.internet import protocol, reactor
from twisted.python import log
from twisted.conch.interfaces import ISession
import common, channel

class SSHSession(channel.SSHChannel):

    name = 'session'
    def __init__(self, *args, **kw):
        channel.SSHChannel.__init__(self, *args, **kw)
        self.buf = ''
        self.session = ISession(self.avatar)

    def request_subsystem(self, data):
        subsystem = common.getNS(data)[0]
        client = self.avatar.lookupSubsystem(subsystem, data)
        if client:
            pp = SSHSessionProcessProtocol(self)
            proto = wrapProcessProtocol(pp)
            client.makeConnection(proto)
            pp.makeConnection(wrapProtocol(client))
            log.msg('starting subsystem %s'%subsystem)
            self.client = pp
            return 1
        else:
            log.msg('failed to get subsystem %s'%subsystem)
            return 0

    def request_shell(self, data):
        try:
            self.client = SSHSessionProcessProtocol(self)
            self.session.openShell(self.client)
        except:
            log.msg('error getting shell:')
            log.deferr()
            return 0
        else:
            return 1

    def request_exec(self, data):
        f,data = common.getNS(data)
        try:
            self.client = SSHSessionProcessProtocol(self)
            self.session.execCommand(self.client, f)
        except:
            log.msg('error executing command: %s' % f)
            log.deferr()
            return 0
        else:
            return 1

    def request_pty_req(self, data):
        term, windowSize, modes = parseRequest_pty_req(data)
        try:
            self.session.getPty(term, windowSize, modes) 
        except:
            log.msg('error getting pty')
            log.err()
            return 0
        else:
            return 1

    def request_window_change(self, data):
        import fcntl, tty
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
        if not hasattr(self, 'client'):
            #self.conn.sendClose(self)
            self.buf += data
            return
        self.client.transport.write(data)

    def extReceived(self, dataType, data):
        if dataType == connection.EXTENDED_DATA_STDERR:
            if hasattr(self, 'client') and hasattr(self.client.transport, 'writeErr'):
                self.client.transport.writeErr(data)
        else:
            log.msg('weird extended data: %s'%dataType)

    def closed(self):
        self.session.closed()

    def eofReceived(self):
        self.loseConnection() # don't know what to do with this

    def loseConnection(self):
        self.client.transport.loseConnection()
        channel.SSHChannel.loseConnection(self)

class _ProtocolWrapper(protocol.ProcessProtocol):
    """
    This class wraps a Protocol instance in a ProcessProtocol instance.
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
        return ProtocolWrapper(inst)
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
    modes = common.getNS(rest[16:])[0]
    winSize = (rows, cols, xpixel, ypixel)
    modes = [(ord(modes[i]), struct.unpack('>L', modes[i+1: i+5])[0])for i in range(0, len(modes)-1, 5)]
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
