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

import struct, os

from twisted.internet import protocol, reactor
from twisted.python import log, components

import common, channel, filetransfer

class ISession(components.Interface):

    def getPty(self, term, windowSize, modes):
        """
        Get a psuedo-terminal for use by a shell or command.

        If a psuedo-terminal is not available, or the request otherwise
        fails, raise an exception.
        """

    def openShell(self, proto):
        """
        Open a shell and connect it to proto.

        proto should be a ProcessProtocol instance.
        """

    def execCommand(self, proto, command, *args):
        """
        Execute a command.

        proto should be a ProcessProtocol instance.
        """

    def windowChanged(self, newWindowSize):
        """
        Called when the size of the remote screen has changed.
        """

    def closed(self):
        """
        Called when the session is closed.
        """

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
            client.makeConnection(self)
            log.msg('starting subsystem %s'%subsystem)
            self.client = client
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
        l = []
        while data:
            f,data = common.getNS(data)
            l.append(f)
        try:
            self.client = SSHSessionProcessProtocol(self)
            self.session.execCommand(self.client, *l)
        except:
            log.msg('error executing command: %s' % l)
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
            log.deferr()
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
            log.deferr()
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

    def eofReceived(self):
        self.loseConnection() # don't know what to do with this

    def loseConnection(self):
        self.client.transport.loseConnection()
        channel.SSHChannel.loseConnection(self)

class SSHSessionForUnixConchUser:

    __implements__ = ISession

    def __init__(self, avatar):
        self.avatar = avatar
        self. environ = {'PATH':'/bin:/usr/bin:/usr/local/bin'}
        self.pty = None
        self.ptyTuple = 0

    def getPty(self, term, windowSize, modes):
        import pty
        self.environ['TERM'] = term
        self.winSize = windowSize
        self.modes = modes
        master, slave = pty.openpty()
        ttyname = os.ttyname(slave)
        self.environ['SSH_TTY'] = ttyname 
        self.ptyTuple = (master, slave, ttyname)

    def openShell(self, proto):
        import fcntl, tty
        if not self.ptyTuple: # we didn't get a pty-req
            log.msg('tried to get shell without pty, failing')
            raise error.ConchError("no pty")
        #proto = wrapProtocol(proto)
        uid, gid = self.avatar.getUserGroupId()
        homeDir = self.avatar.getHomeDir()
        shell = self.avatar.getShell()
        self.environ['USER'] = self.avatar.username
        self.environ['HOME'] = homeDir
        self.environ['SHELL'] = shell
        peer = self.avatar.conn.transport.transport.getPeer()
        host = self.avatar.conn.transport.transport.getHost()
        self.environ['SSH_CLIENT'] = '%s %s %s' % (peer.host, peer.port, host.port)
        self.getPtyOwnership()
        self.pty = reactor.spawnProcess(proto, \
                  shell, ['-', '-i'], self.environ, homeDir, uid, gid,
                   usePTY = self.ptyTuple)
        fcntl.ioctl(pty.fileno(), tty.TIOCSWINSZ, 
                        struct.pack('4H', *self.winSize))
        if self.modes:
            self.setModes()
        self.oldWrite = proto.transport.write
        proto.transport.write = self._writeHack
        self.avatar.conn.transport.transport.setTcpNoDelay(1)

    def execCommand(self, proto, cmd, *args):
        uid, gid = self.avatar.getUserGroupId()
        homeDir = self.avatar.getHomeDir()
        shell = self.avatar.getShell() or '/bin/sh'
        command = (shell, '-c', cmd) + args
        peer = self.avatar.conn.transport.transport.getPeer()
        host = self.avatar.conn.transport.transport.getHost()
        self.environ['SSH_CLIENT'] = '%s %s %s' % (peer.host, peer.port, host.port)
        if self.ptyTuple:
            self.getPtyOwnership()
        self.pty = reactor.spawnProcess(proto, \
                shell, command, self.environ, homeDir,
                uid, gid, usePTY = self.ptyTuple or 1)
        if self.ptyTuple:
            if self.modes:
                self.setModes()
        else:
            import tty
            tty.setraw(self.pty.fileno(), tty.TCSANOW)
        self.avatar.conn.transport.transport.setTcpNoDelay(1)

    def getPtyOwnership(self):
        ttyGid = os.stat(self.ptyTuple[2])[5]
        uid = self.avatar.getUserGroupId()[0]
        euid, egid = os.geteuid(), os.getegid()
        os.setegid(0)
        os.seteuid(0)
        try:
            os.chown(self.ptyTuple[2], uid, ttyGid)
        finally:
            os.setegid(egid)
            os.seteuid(euid)
        
    def setModes(self):
        import tty, ttymodes
        pty = self.pty
        attr = tty.tcgetattr(pty.fileno())
        for mode, modeValue in self.modes:
            if not ttymodes.TTYMODES.has_key(mode): continue
            ttyMode = ttymodes.TTYMODES[mode]
            if len(ttyMode) == 2: # flag
                flag, ttyAttr = ttyMode
                if not hasattr(tty, ttyAttr): continue
                ttyval = getattr(tty, ttyAttr)
                if modeValue:
                    attr[flag] = attr[flag]|ttyval
                else:
                    attr[flag] = attr[flag]&~ttyval
            elif ttyMode == 'OSPEED':
                attr[tty.OSPEED] = getattr(tty, 'B%s'%modeValue)
            elif ttyMode == 'ISPEED':
                attr[tty.ISPEED] = getattr(tty, 'B%s'%modeValue)
            else:
                if not hasattr(tty, ttyMode): continue
                ttyval = getattr(tty, ttyMode)
                attr[tty.CC][ttyval] = chr(modeValue)
        tty.tcsetattr(pty.fileno(), tty.TCSANOW, attr)

    def closed(self):
        if self.pty:
            import os
            self.pty.loseConnection()
            self.pty.signalProcess('HUP')
            if self.ptyTuple:
                ttyGID = os.stat(self.ptyTuple[2])[5]
                os.chown(self.ptyTuple[2], 0, ttyGID)

    def _writeHack(self, data):
        """
        Hack to send ignore messages when we aren't echoing.
        """
        if self.pty is not None:
            import tty
            attr = tty.tcgetattr(self.pty.fileno())[3]
            if not attr & tty.ECHO and attr & tty.ICANON: # no echo
                self.avatar.conn.transport.sendIgnore('\x00'*(8+len(data)))
        self.oldWrite(data)

class ProtocolWrapper(protocol.ProcessProtocol):
    """
    This class wraps a Protocol instance in a ProcessProtocol instance.
    """
    def __init__(self, proto):
        self.proto = proto

    def connectionMade(self): self.proto.connectionMade()
    
    def outReceived(self, data): self.proto.dataReceived(data)

    def processEnded(self, reason): self.proto.connectionLost(reason)
    
def wrapProtocol(inst):
    if isinstance(inst, protocol.Protocol):
        return ProtocolWrapper(inst)
    else:
        return inst

class SSHSessionProcessProtocol(protocol.ProcessProtocol):
    def __init__(self, session):
        self.session = session

    def connectionMade(self):
        if self.session.buf:
            self.transport.write(self.session.buf)
            self.session.buf = None

    def outReceived(self, data):
        self.session.write(data)

    def errReceived(self, err):
        self.session.conn.sendExtendedData(self.session, connection.EXTENDED_DATA_STDERR, err)

    def connectionLost(self, reason = None):
        self.session.loseConnection()

    def processEnded(self, reason = None):
        if reason and hasattr(reason.value, 'exitCode'): 
            log.msg('exitCode: %s' % repr(reason.value.exitCode))
            self.session.conn.sendRequest(self.session, 'exit-status', struct.pack('!L', reason.value.exitCode))
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
