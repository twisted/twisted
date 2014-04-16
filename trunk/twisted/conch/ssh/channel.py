# -*- test-case-name: twisted.conch.test.test_channel -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

#
"""
The parent class for all the SSH Channels.  Currently implemented channels
are session. direct-tcp, and forwarded-tcp.

Maintainer: Paul Swartz
"""

from twisted.python import log
from twisted.internet import interfaces
from zope.interface import implements


class SSHChannel(log.Logger):
    """
    A class that represents a multiplexed channel over an SSH connection.
    The channel has a local window which is the maximum amount of data it will
    receive, and a remote which is the maximum amount of data the remote side
    will accept.  There is also a maximum packet size for any individual data
    packet going each way.

    @ivar name: the name of the channel.
    @type name: C{str}
    @ivar localWindowSize: the maximum size of the local window in bytes.
    @type localWindowSize: C{int}
    @ivar localWindowLeft: how many bytes are left in the local window.
    @type localWindowLeft: C{int}
    @ivar localMaxPacket: the maximum size of packet we will accept in bytes.
    @type localMaxPacket: C{int}
    @ivar remoteWindowLeft: how many bytes are left in the remote window.
    @type remoteWindowLeft: C{int}
    @ivar remoteMaxPacket: the maximum size of a packet the remote side will
        accept in bytes.
    @type remoteMaxPacket: C{int}
    @ivar conn: the connection this channel is multiplexed through.
    @type conn: L{SSHConnection}
    @ivar data: any data to send to the other size when the channel is
        requested.
    @type data: C{str}
    @ivar avatar: an avatar for the logged-in user (if a server channel)
    @ivar localClosed: True if we aren't accepting more data.
    @type localClosed: C{bool}
    @ivar remoteClosed: True if the other size isn't accepting more data.
    @type remoteClosed: C{bool}
    """

    implements(interfaces.ITransport)

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
        return '<SSHChannel %s (lw %i rw %i)>' % (self.name,
                self.localWindowLeft, self.remoteWindowLeft)

    def logPrefix(self):
        id = (self.id is not None and str(self.id)) or "unknown"
        return "SSHChannel %s (%s) on %s" % (self.name, id,
                self.conn.logPrefix())

    def channelOpen(self, specificData):
        """
        Called when the channel is opened.  specificData is any data that the
        other side sent us when opening the channel.

        @type specificData: C{str}
        """
        log.msg('channel open')

    def openFailed(self, reason):
        """
        Called when the the open failed for some reason.
        reason.desc is a string descrption, reason.code the the SSH error code.

        @type reason: L{error.ConchError}
        """
        log.msg('other side refused open\nreason: %s'% reason)

    def addWindowBytes(self, bytes):
        """
        Called when bytes are added to the remote window.  By default it clears
        the data buffers.

        @type bytes:    C{int}
        """
        self.remoteWindowLeft = self.remoteWindowLeft+bytes
        if not self.areWriting and not self.closing:
            self.areWriting = True
            self.startWriting()
        if self.buf:
            b = self.buf
            self.buf = ''
            self.write(b)
        if self.extBuf:
            b = self.extBuf
            self.extBuf = []
            for (type, data) in b:
                self.writeExtended(type, data)

    def requestReceived(self, requestType, data):
        """
        Called when a request is sent to this channel.  By default it delegates
        to self.request_<requestType>.
        If this function returns true, the request succeeded, otherwise it
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
        log.msg('remote eof')

    def closeReceived(self):
        """
        Called when the other side has closed the channel.
        """
        log.msg('remote close')
        self.loseConnection()

    def closed(self):
        """
        Called when the channel is closed.  This means that both our side and
        the remote side have closed the channel.
        """
        log.msg('closed')

    # transport stuff
    def write(self, data):
        """
        Write some data to the channel.  If there is not enough remote window
        available, buffer until it is.  Otherwise, split the data into
        packets of length remoteMaxPacket and send them.

        @type data: C{str}
        """
        if self.buf:
            self.buf += data
            return
        top = len(data)
        if top > self.remoteWindowLeft:
            data, self.buf = (data[:self.remoteWindowLeft],
                data[self.remoteWindowLeft:])
            self.areWriting = 0
            self.stopWriting()
            top = self.remoteWindowLeft
        rmp = self.remoteMaxPacket
        write = self.conn.sendData
        r = range(0, top, rmp)
        for offset in r:
            write(self, data[offset: offset+rmp])
        self.remoteWindowLeft -= top
        if self.closing and not self.buf:
            self.loseConnection() # try again

    def writeExtended(self, dataType, data):
        """
        Send extended data to this channel.  If there is not enough remote
        window available, buffer until there is.  Otherwise, split the data
        into packets of length remoteMaxPacket and send them.

        @type dataType: C{int}
        @type data:     C{str}
        """
        if self.extBuf:
            if self.extBuf[-1][0] == dataType:
                self.extBuf[-1][1] += data
            else:
                self.extBuf.append([dataType, data])
            return
        if len(data) > self.remoteWindowLeft:
            data, self.extBuf = (data[:self.remoteWindowLeft],
                                [[dataType, data[self.remoteWindowLeft:]]])
            self.areWriting = 0
            self.stopWriting()
        while len(data) > self.remoteMaxPacket:
            self.conn.sendExtendedData(self, dataType,
                                             data[:self.remoteMaxPacket])
            data = data[self.remoteMaxPacket:]
            self.remoteWindowLeft -= self.remoteMaxPacket
        if data:
            self.conn.sendExtendedData(self, dataType, data)
            self.remoteWindowLeft -= len(data)
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
        Close the channel if there is no buferred data.  Otherwise, note the
        request and return.
        """
        self.closing = 1
        if not self.buf and not self.extBuf:
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
