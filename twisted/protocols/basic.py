# -*- test-case-name: twisted.test.test_protocols -*-

# Twisted, the Framework of Your Internet
# Copyright (C) 2001 Matthew W. Lefkowitz
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

"""Basic protocols, such as line-oriented, netstring, and 32-bit-int prefixed strings.

API Stability: semi-stable.

Maintainer: U{Itamar Shtull-Trauring<mailto:twisted@itamarst.org>}
"""

# System imports
import re
import struct

# Twisted imports
from twisted.internet import protocol, defer, interfaces, error
from twisted.python import log


LENGTH, DATA, COMMA = range(3)
NUMBER = re.compile('(\d*)(:?)')
DEBUG = 0

class NetstringParseError(ValueError):
    """The incoming data is not in valid Netstring format."""
    pass


class NetstringReceiver(protocol.Protocol):
    """This uses djb's Netstrings protocol to break up the input into strings.

    Each string makes a callback to stringReceived, with a single
    argument of that string.

    Security features:
        1. Messages are limited in size, useful if you don't want someone
           sending you a 500MB netstring (change MAX_LENGTH to the maximum
           length you wish to accept).
        2. The connection is lost if an illegal message is received.
    """

    MAX_LENGTH = 99999
    brokenPeer = 0
    _readerState = LENGTH
    _readerLength = 0

    def stringReceived(self, line):
        """
        Override this.
        """
        raise NotImplementedError

    def doData(self):
        buffer,self.__data = self.__data[:int(self._readerLength)],self.__data[int(self._readerLength):]
        self._readerLength = self._readerLength - len(buffer)
        self.__buffer = self.__buffer + buffer
        if self._readerLength != 0:
            return
        self.stringReceived(self.__buffer)
        self._readerState = COMMA

    def doComma(self):
        self._readerState = LENGTH
        if self.__data[0] != ',':
            if DEBUG:
                raise NetstringParseError(repr(self.__data))
            else:
                raise NetstringParseError
        self.__data = self.__data[1:]


    def doLength(self):
        m = NUMBER.match(self.__data)
        if not m.end():
            if DEBUG:
                raise NetstringParseError(repr(self.__data))
            else:
                raise NetstringParseError
        self.__data = self.__data[m.end():]
        if m.group(1):
            try:
                self._readerLength = self._readerLength * (10**len(m.group(1))) + long(m.group(1))
            except OverflowError:
                raise NetstringParseError, "netstring too long"
            if self._readerLength > self.MAX_LENGTH:
                raise NetstringParseError, "netstring too long"
        if m.group(2):
            self.__buffer = ''
            self._readerState = DATA

    def dataReceived(self, data):
        self.__data = data
        try:
            while self.__data:
                if self._readerState == DATA:
                    self.doData()
                elif self._readerState == COMMA:
                    self.doComma()
                elif self._readerState == LENGTH:
                    self.doLength()
                else:
                    raise RuntimeError, "mode is not DATA, COMMA or LENGTH"
        except NetstringParseError:
            self.transport.loseConnection()
            self.brokenPeer = 1

    def sendString(self, data):
        self.transport.write('%d:%s,' % (len(data), data))


class SafeNetstringReceiver(NetstringReceiver):
    """This class is deprecated, use NetstringReceiver instead.
    """


class LineOnlyReceiver(protocol.Protocol):
    """A protocol that receives only lines.
    
    This is purely a speed optimisation over LineReceiver, for the cases that raw mode is known to be unnecessary.
    """
    _buffer = ''
    delimiter = '\r\n'
    MAX_LENGTH = 16384
    
    def dataReceived(self, data):
        """Protocol.dataReceived.
        Translates bytes into lines, and calls lineReceived.
        """
        
        lines  = (self._buffer+data).split(self.delimiter)
        self._buffer = lines[-1]
        for line in lines[:-1]:
            if self.transport.disconnecting:
                # this is necessary because the transport may be told to lose
                # the connection by a line within a larger packet, and it is
                # important to disregard all the lines in that packet following
                # the one that told it to close.
                return
            if len(line) > self.MAX_LENGTH:
                return self.lineLengthExceeded(line)                
            else:
                self.lineReceived(line)
        if len(self._buffer) > self.MAX_LENGTH:
            return self.lineLengthExceeded(self._buffer)                

    def lineReceived(self, line):
        """Override this for when each line is received.
        """
        raise NotImplementedError

    def sendLine(self, line):
        """Sends a line to the other end of the connection.
        """
        return self.transport.writeSequence((line,self.delimiter))

    def lineLengthExceeded(self, line):
        """Called when the maximum line length has been reached.
        Override if it needs to be dealt with in some special way.
        """
        return error.ConnectionLost('Line length exceeded')
    


class LineReceiver(protocol.Protocol):
    """A protocol that receives lines and/or raw data, depending on mode.
    
    In line mode, each line that's received becomes a callback to
    L{lineReceived}.  In raw data mode, each chunk of raw data becomes a
    callback to L{rawDataReceived}.  The L{setLineMode} and L{setRawMode}
    methods switch between the two modes.
    
    This is useful for line-oriented protocols such as IRC, HTTP, POP, etc.
    
    @cvar delimiter: The line-ending delimiter to use. By default this is
                     '\\r\\n'.
    @cvar MAX_LENGTH: The maximum length of a line to allow (If a
                      sent line is longer than this, the connection is dropped).
                      Default is 16384.
    """
    line_mode = 1
    __buffer = ''
    delimiter = '\r\n'
    MAX_LENGTH = 16384

    def clearLineBuffer(self):
        """Clear buffered data."""
        self.__buffer = ""
    
    def dataReceived(self, data):
        """Protocol.dataReceived.
        Translates bytes into lines, and calls lineReceived (or
        rawDataReceived, depending on mode.)
        """
        self.__buffer = self.__buffer+data
        while self.line_mode:
            try:
                line, self.__buffer = self.__buffer.split(self.delimiter, 1)
            except ValueError:
                if len(self.__buffer) > self.MAX_LENGTH:
                    line, self.__buffer = self.__buffer, ''
                    return self.lineLengthExceeded(line)
                break
            else:
                linelength = len(line)
                if linelength > self.MAX_LENGTH:
                    line, self.__buffer = self.__buffer, ''
                    return self.lineLengthExceeded(line)
                why = self.lineReceived(line)
                if why or self.transport and self.transport.disconnecting:
                    return why
        else:
            data, self.__buffer = self.__buffer, ''
            if data:
                return self.rawDataReceived(data)

    def setLineMode(self, extra=''):
        """Sets the line-mode of this receiver.

        If you are calling this from a rawDataReceived callback,
        you can pass in extra unhandled data, and that data will
        be parsed for lines.  Further data received will be sent
        to lineReceived rather than rawDataReceived.
        """
        self.line_mode = 1
        return self.dataReceived(extra)

    def setRawMode(self):
        """Sets the raw mode of this receiver.
        Further data received will be sent to rawDataReceived rather
        than lineReceived.
        """
        self.line_mode = 0

    def rawDataReceived(self, data):
        """Override this for when raw data is received.
        """
        raise NotImplementedError

    def lineReceived(self, line):
        """Override this for when each line is received.
        """
        raise NotImplementedError

    def sendLine(self, line):
        """Sends a line to the other end of the connection.
        """
        return self.transport.write(line + self.delimiter)

    def lineLengthExceeded(self, line):
        """Called when the maximum line length has been reached.
        Override if it needs to be dealt with in some special way.
        """
        return self.transport.loseConnection()


class Int32StringReceiver(protocol.Protocol):
    """A receiver for int32-prefixed strings.

    An int32 string is a string prefixed by 4 bytes, the 32-bit length of
    the string encoded in network byte order.

    This class publishes the same interface as NetstringReceiver.
    """

    MAX_LENGTH = 99999
    recvd = ""

    def stringReceived(self, msg):
        """Override this.
        """
        raise NotImplementedError

    def dataReceived(self, recd):
        """Convert int32 prefixed strings into calls to stringReceived.
        """
        self.recvd = self.recvd + recd
        while len(self.recvd) > 3:
            length ,= struct.unpack("!i",self.recvd[:4])
            if length > self.MAX_LENGTH:
                self.transport.loseConnection()
                return
            if len(self.recvd) < length+4:
                break
            packet = self.recvd[4:length+4]
            self.recvd = self.recvd[length+4:]
            self.stringReceived(packet)

    def sendString(self, data):
        """Send an int32-prefixed string to the other end of the connection.
        """
        self.transport.write(struct.pack("!i",len(data))+data)


class Int16StringReceiver(protocol.Protocol):
    """A receiver for int16-prefixed strings.

    An int16 string is a string prefixed by 2 bytes, the 16-bit length of
    the string encoded in network byte order.

    This class publishes the same interface as NetstringReceiver.
    """

    recvd = ""

    def stringReceived(self, msg):
        """Override this.
        """
        raise NotImplementedError

    def dataReceived(self, recd):
        """Convert int16 prefixed strings into calls to stringReceived.
        """
        self.recvd = self.recvd + recd
        while len(self.recvd) > 1:
            length = (ord(self.recvd[0]) * 256) + ord(self.recvd[1])
            if len(self.recvd) < length+2:
                break
            packet = self.recvd[2:length+2]
            self.recvd = self.recvd[length+2:]
            self.stringReceived(packet)

    def sendString(self, data):
        """Send an int16-prefixed string to the other end of the connection.
        """
        assert len(data) < 65536, "message too long"
        self.transport.write(struct.pack("!h",len(data)) + data)


class StatefulStringProtocol:
    """A stateful string protocol.

    This is a mixin for string protocols (Int32StringReceiver,
    NetstringReceiver) which translates stringReceived into a callback
    (prefixed with 'proto_') depending on state."""

    state = 'init'

    def stringReceived(self,string):
        """Choose a protocol phase function and call it.

        Call back to the appropriate protocol phase; this begins with
        the function proto_init and moves on to proto_* depending on
        what each proto_* function returns.  (For example, if
        self.proto_init returns 'foo', then self.proto_foo will be the
        next function called when a protocol message is received.
        """
        try:
            pto = 'proto_'+self.state
            statehandler = getattr(self,pto)
        except AttributeError:
            log.msg('callback',self.state,'not found')
        else:
            self.state = statehandler(string)
            if self.state == 'done':
                self.transport.loseConnection()

class FileSender:
    """A producer that sends the contents of a file to a consumer.
    
    This is a helper for protocols that, at some point, will take a
    file-like object, read its contents, and write them out to the network,
    optionally performing some transformation on the bytes in between.
    
    This API is unstable.
    """
    __implements__ = (interfaces.IProducer,)
    
    CHUNK_SIZE = 2 ** 14
    
    lastSent = ''
    deferred = None

    def beginFileTransfer(self, file, consumer, transform = None):
        """Begin transferring a file
        
        @type file: Any file-like object
        @param file: The file object to read data from
        
        @type consumer: Any implementor of IConsumer
        @param consumer: The object to write data to
        
        @param transform: A callable taking one string argument and returning
        the same.  All bytes read from the file are passed through this before
        being written to the consumer.
        
        @rtype: C{Deferred}
        @return: A deferred whose callback will be invoked when the file has been
        completely written to the consumer.  The last byte written to the consumer
        is passed to the callback.
        """
        self.file = file
        self.consumer = consumer
        self.transform = transform
        
        self.consumer.registerProducer(self, False)
        self.deferred = defer.Deferred()
        return self.deferred
    
    def resumeProducing(self):
        chunk = ''
        if self.file:
            chunk = self.file.read(self.CHUNK_SIZE)
        if not chunk:
            self.file = None
            self.consumer.unregisterProducer()
            if self.deferred:
                self.deferred.callback(self.lastSent)
                self.deferred = None
            return
        
        if self.transform:
            chunk = self.transform(chunk)
        self.consumer.write(chunk)
        self.lastSent = chunk[-1]

    def pauseProducing(self):
        pass
    
    def stopProducing(self):
        if self.deferred:
            self.deferred.errback(Exception("Consumer asked us to stop producing"))
            self.deferred = None
