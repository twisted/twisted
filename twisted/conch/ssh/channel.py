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
"""The parent class for all the SSH Channels.  Currently implemented channels
are session. direct-tcp, and forwarded-tcp.

This module is unstable.

Maintainer: U{Paul Swartz<mailto:z3p@twistedmatrix.com>}
"""

from twisted.python import log

class SSHChannel:
    name = None # only needed for client channels
    def __init__(self, localWindow = 0, localMaxPacket = 0, 
                       remoteWindow = 0, remoteMaxPacket = 0, 
                       conn = None, data=None, avatar = None):
        self.localWindowSize = localWindow or 131072
        self.localWindowLeft = self.localWindowSize
        self.localMaxPacket = localMaxPacket or 32768
        self.remoteWindowLeft = remoteWindow
        self.remoteMaxPacket = remoteMaxPacket
        self.areWriting = 1
        self.conn = conn
        self.data = data
        self.avatar = avatar
        self.specificData = ''
        self.buf = ''
        self.extBuf = []
        self.closing = 0
        self.localClosed = 0
        self.remoteClosed = 0
        self.id = None # gets set later by SSHConnection

    def __str__(self):
        return '%s (lw %i rw %i)' % (self.name, self.localWindowLeft, self.remoteWindowLeft)

    def channelOpen(self, specificData):
        """
        Called when the channel is opened.  specificData is any data that the
        other side sent us when opening the channel.

        @type specificData: C{str}
        """
        log.msg('channel %s open'%self.id)

    def openFailed(self, reason):
        """
        Called when the the open failed for some reason.
        reason.desc is a string descrption, reason.code the the SSH error code.

        @type reason: C{error.ConchError}
        """
        log.msg('other side refused channel %s\nreason: %s'%(self.id, reason))

    def addWindowBytes(self, bytes):
        """
        Called when bytes are added to the remote window.  By default it clears
        the data buffers.

        @type bytes:    C{int}
        """
        self.remoteWindowLeft = self.remoteWindowLeft+bytes
        if not self.areWriting and not self.closing:
            self.areWriting = 0
            self.startWriting()
        if self.buf:
            b = self.buf
            self.buf = ''
            self.write(b)
        if self.extBuf:
            b = self.extBuf
            self.extBuf = []
            for i in b:
                self.writeExtended(*i)

    def requestReceived(self, requestType, data):
        """
        Called when a request is sent to this channel.  By default it delegates
        to self.request_<requestType>.
        If this functio returns true, the request succeeded, otherwise it
        failed.

        @type requestType:  C{str}
        @type data:         C{str}
        @rtype:             C{bool}
        """
        foo = requestType.replace('-', '_')
        f = getattr(self, 'request_%s'%foo, None)
        if f:
            return f(data)
        log.msg('unhandled request for %s'%requestType)
        return 0

    def dataReceived(self, data):
        """
        Called when we receive data.

        @type data: C{str}
        """
        log.msg('got data %s'%repr(data))

    def extReceived(self, dataType, data):
        """
        Called when we receive extended data (usually standard error).

        @type dataType: C{int}
        @type data:     C{str}
        """
        log.msg('got extended data %s %s'%(dataType, repr(data)))

    def eofReceived(self):
        """
        Called when the other side will send no more data.
        """
        log.msg('channel %s remote eof'%self.id)

    def closed(self):
        """
        Called when the channel is closed.
        """
        log.msg('channel %s closed'%self.id)

    # transport stuff
    def write(self, data):
        """
        Write some data to the channel.  If there is not enough remote window
        available, buffer until it is.

        @type data: C{str}
        """
        if self.buf:
            self.buf += data
            return
        if len(data) > self.remoteWindowLeft:
            data, self.buf = data[: self.remoteWindowLeft],  \
                            data[self.remoteWindowLeft:]
            self.areWriting = 0  
            self.stopWriting()
        if not data: return
        while len(data) > self.remoteMaxPacket:
            self.conn.sendData(self, data[: self.remoteMaxPacket])
            data = data[self.remoteMaxPacket:]
            self.remoteWindowLeft-=self.remoteMaxPacket
        if data:
            self.conn.sendData(self, data)
            self.remoteWindowLeft-=len(data)
        if self.closing and not self.buf:
            self.loseConnection() # try again

    def writeExtended(self, dataType, data):
        """
        Send extended data to this channel.  If there is not enough remote
        window available, buffer until there is.

        @type dataType: C{int}
        @type data:     C{str}
        """
        if self.extBuf:
            if self.extBuf[-1][0] == dataType:
                self.extBuf[-1][1]+=data
            else:
                self.extBuf.append([dataType, data])
            return
        if len(data) > self.remoteWindowLeft:
            data, self.extBuf = data[:self.remoteWindowLeft], \
                                [[dataType, data[self.remoteWindowLeft:]]]
            self.areWriting = 0
            self.stopWriting()
        if not data: return
        while len(data) > self.remoteMaxPacket:
            self.conn.sendExtendedData(self, dataType, 
                                             data[:self.remoteMaxPacket])
            data = data[self.remoteMaxPacket:]
            self.remoteWindowLeft-=self.remoteMaxPacket
        if data:
            self.conn.sendExtendedData(self, dataType, data)
            self.remoteWindowLeft-=len(data)
        if self.closing:
            self.loseConnection() # try again

    def writeSequence(self, data):
        """
        Part of the Transport interface.  Write a list of strings to the
        channel.

        @type data: C{list} of C{str}
        """
        self.write(''.join(data))

    def loseConnection(self):
        """
        Close the channel.
        """
        self.closing = 1
        if not self.buf and not self.extBuf:
            self.localClosed = 1
            self.conn.sendClose(self)

    def getPeer(self):
        """
        Return a tuple describing the other side of the connection.

        @rtype: C{tuple}
        """
        return('SSH', )+self.conn.transport.getPeer()

    def getHost(self):
        """
        Return a tuple describing our side of the connection.

        @rtype: C{tuple}
        """
        return('SSH', )+self.conn.transport.getHost()

    def stopWriting(self):
        """
        Called when the remote buffer is full, as a hint to stop writing.
        This can be ignored, but it can be helpful.
        """

    def startWriting(self):
        """
        Called when the remote buffer has more room, as a hint to continue
        writing.
        """
