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

import struct, fcntl, tty, os

from twisted.internet import protocol, reactor
from twisted.python import log

import common, connection, ttymodes

class SSHSession(connection.SSHChannel):

    name = 'session'
    def __init__(self, *args, **kw):
        connection.SSHChannel.__init__(self, *args, **kw)
        self. environ = {}
        self.buf = '' 

    def request_subsystem(self, data):
        subsystem = common.getNS(data)[0]
        f = getattr(self, 'subsystem_%s'%subsystem, None)
        if f:
            client = f()
            if client:
                log.msg('starting subsystem %s'%subsystem)
                self.client = client
                return 1
            else:
                return 0
        elif self.conn.factory.authorizer.clients.has_key(subsytem):
            # we have a client for a pb service
            pass # for now
        log.msg('failed to get subsystem %s'%subsystem)
        return 0

    def request_shell(self, data):
        if not self.environ.has_key('TERM'): # we didn't get a pty-req
            log.msg('tried to get shell without pty, failing')
            return 0
        user = self.conn.transport.authenticatedUser
        #homeDir = user.getHomeDir()
        #self.environ['USER'] = user.name
        #self.environ['HOME'] = homeDir
        #self.environ['SHELL'] = shell
        peerHP = tuple(self.conn.transport.transport.getPeer()[1:])
        hostP = (self.conn.transport.transport.getHost()[2],)
        self.environ['SSH_CLIENT'] = '%s %s %s' % (peerHP+hostP)
        try:
            self.client = SSHSessionClient()
            pty = reactor.spawnProcess(SSHSessionProtocol(self, self.client), \
                  'login', ['login','-p', '-f', user.name], self.environ,  
                   usePTY = 1)
            fcntl.ioctl(pty.fileno(), tty.TIOCSWINSZ, 
                        struct.pack('4H', *self.winSize))
        except OSError, e:
            log.msg('failed to get pty')
            log.msg('reason:')
            log.deferr()
            return 0
        else:
            self.pty = pty
            if self.modes:
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
            self.conn.transport.transport.setTcpNoDelay(1)
            return 1

    def request_exec(self, data):
        command = common.getNS(data)[0]
        command = ['/bin/sh', '-c', command]
        user = self.conn.transport.authenticatedUser
        uid, gid = user.getUserGroupID()
        homeDir = user.getHomeDir()
        try:
            self.client = SSHSessionClient()
            pty = reactor.spawnProcess(SSHSessionProtocol(self, self.client), \
                    '/bin/sh', command, self.environ, homeDir,
                    uid, gid, usePTY = 1)
        except OSError, e:
            log.msg('failed to exec %s' % command)
            log.msg('reason:')
            log.deferr()
            return 0
        else:
            self.pty = pty
            tty.setraw(pty.fileno())
            self.conn.transport.transport.setTcpNoDelay(1)
            if self.buf:
                self.client.dataReceived(self.buf)
                self.buf = ''
            return 1
        return 0

    def request_pty_req(self, data):
        self.environ['TERM'], self.winSize, self.modes =  \
                             parseRequest_pty_req(data)
        return 1

    def request_window_change(self, data):
        parseRequest_window_change(data)
        fcntl.ioctl(self.pty.fileno(), tty.TIOCSWINSZ, 
                    struct.pack('4H', *self.winSize))
        return 1

    def subsystem_python(self):
        """This is disabled by default, because it allows access to a
        python shell running as the owner of the process.
        """
        return 0
        # XXX hack hack hack
        # this should be refacted into the 'interface to pb service' part
        from twisted.manhole import telnet
        pyshell = telnet.Shell()
        pyshell.connectionMade = lambda*args: None
        pyshell.lineBuffer = []
        self.namespace = {
        'session': self, 
            'connection': self.conn, 
            'transport': self.conn.transport, 
         }
        pyshell.factory = self # we need pyshell.factory.namespace
        pyshell.delimiters.append('\n')
        pyshell.mode = 'Command'
        pyshell.makeConnection(self) # because we're the transport
        pyshell.loggedIn() # since we've logged in by the time we make it here
        self.receiveEOF = self.loseConnection
        return pyshell

    def dataReceived(self, data):
        if not hasattr(self, 'client'):
            #self.conn.sendClose(self)
            self.buf += data
            return
        if hasattr(self, 'pty'):
            attr = tty.tcgetattr(self.pty.fileno())[3]
            if not attr & tty.ECHO and attr & tty.ICANON: # no echo
                self.conn.transport.sendIgnore('\x00' * (8+len(data)))
        self.client.dataReceived(data)

    def extReceived(self, dataType, data):
        if dataType == connection.EXTENDED_DATA_STDERR:
            if hasattr(self.client, 'errReceieved'):
                self.client.errReceived(data)
        else:
            log.msg('weird extended data: %s'%dataType)

    def eofReceived(self):
        self.loseConnection() # don't know what to do with this

    def closed(self):
        try:
            del self.client
        except AttributeError:
            pass # we didn't have a client
        connection.SSHChannel.closed(self)

class SSHSessionProtocol(protocol.Protocol, protocol.ProcessProtocol):
    def __init__(self, session, client):
        self.session = session
        self.client = client

    def connectionMade(self):
        self.client.transport = self.transport

    def dataReceived(self, data):
        self.session.write(data)

    outReceived = dataReceived

    def errReceived(self, err):
        self.session.conn.sendExtendedData(self.session, connection.EXTENDED_DATA_STDERR, err)

    def connectionLost(self, reason = None):
        self.session.loseConnection()

    def processEnded(self, reason = None):
        if reason and hasattr(reason.value, 'exitCode'): self.session.conn.sendRequest(self.session, 'exit-status', struct.pack('!L', reason.value.exitCode))
        self.session.loseConnection()

class SSHSessionClient(protocol.Protocol):

    def dataReceived(self, data):
        if self.transport:
            self.transport.write(data)

# methods factored out to make live easier on server writers
def parseRequest_pty_req(data):
    """Parse the data from a pty-req request into usable data.

    @returns a tuple of (terminal type, (rows, cols, xpixel, ypixel), modes)
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

    @returns a tuple of (rows, cols, xpixel, ypixel)
    """
    cols, rows, xpixel, ypixel = struct.unpack('>4L', data)
    return rows, cols, xpixel, ypixel

def packRequest_window_change((rows, cols, xpixel, ypixel)):
    """Pack a window-change request so that it is suitable for sending.
    """
    return struct.pack('>4L', cols, rows, xpixel, ypixel)
