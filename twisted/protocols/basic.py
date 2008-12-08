# -*- test-case-name: twisted.test.test_protocols -*-
# Copyright (c) 2001-2008 Twisted Matrix Laboratories.
# See LICENSE for details.


"""
Basic protocols, such as line-oriented, netstring, and int prefixed strings.

Maintainer: Itamar Shtull-Trauring
"""

# System imports
import re
import struct
import warnings

from zope.interface import implements

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

    This is purely a speed optimisation over LineReceiver, for the
    cases that raw mode is known to be unnecessary.

    @cvar delimiter: The line-ending delimiter to use. By default this is
                     '\\r\\n'.
    @type delimiter: C{str}

    @cvar MAX_LENGTH: The maximum length of a line to allow (If a
                      sent line is longer than this, the connection is dropped).
                      Default is 16384.
    @type MAX_LENGTH: C{int}

    @ivar _buffer: A list of data pieces received and buffered, waiting
                   for a delimiter.
    @type _buffer: C{list} of C{str}

    @ivar _buffer_size: The amount of data stored in L{_buffer}.
    @type _buffer_size: C{int}
    """
    _buffer = None
    _buffer_size = 0
    delimiter = '\r\n'
    MAX_LENGTH = 16384

    def dataReceived(self, data):
        """Translates bytes into lines, and calls lineReceived."""
        if self._buffer is None:
            self._buffer = []
        lines = data.split(self.delimiter)
        trailing = lines.pop()

        for line in lines:
            if self.transport.disconnecting:
                # this is necessary because the transport may be told to lose
                # the connection by a line within a larger packet, and it is
                # important to disregard all the lines in that packet following
                # the one that told it to close.
                return
            self._buffer.append(line)
            line = ''.join(self._buffer)
            self._buffer, self._buffer_size = [], 0

            if len(line) > self.MAX_LENGTH:
                return self.lineLengthExceeded(line)
            else:
                self.lineReceived(line)

        self._buffer.append(trailing)
        self._buffer_size += len(trailing)
        if self._buffer_size > self.MAX_LENGTH:
            return self.lineLengthExceeded(''.join(self._buffer))

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


class _PauseableMixin:
    paused = False

    def pauseProducing(self):
        self.paused = True
        self.transport.pauseProducing()

    def resumeProducing(self):
        self.paused = False
        self.transport.resumeProducing()
        self.dataReceived('')

    def stopProducing(self):
        self.paused = True
        self.transport.stopProducing()


class LineReceiver(protocol.Protocol, _PauseableMixin):
    """A protocol that receives lines and/or raw data, depending on mode.

    In line mode, each line that's received becomes a callback to
    L{lineReceived}.  In raw data mode, each chunk of raw data becomes a
    callback to L{rawDataReceived}.  The L{setLineMode} and L{setRawMode}
    methods switch between the two modes.

    This is useful for line-oriented protocols such as IRC, HTTP, POP, etc.

    @cvar delimiter: The line-ending delimiter to use. By default this is
                     '\\r\\n'.
    @type delimiter: C{str}

    @cvar MAX_LENGTH: The maximum length of a line to allow (If a
                      sent line is longer than this, the connection is dropped).
                      Default is 16384.
    @type MAX_LENGTH: C{int}

    @ivar _buffer: A list of data pieces received and buffered. Either
                   an incomplete line, or raw data when the protocol is
                   paused.
    @type _buffer: C{list} of C{str}

    @ivar _buffer_size: The amount of data stored in L{_buffer}.
    @type _buffer_size: C{int}

    @ivar _was_paused: True if the protocol was paused the last time
                       L{dataReceived} was called. This is needed to
                       detect unpausing and trigger processing of
                       buffered data.
    @type _was_paused: C{bool}
    """
    line_mode = 1
    _buffer = None
    _buffer_size = 0
    _was_paused = False
    delimiter = '\r\n'
    MAX_LENGTH = 16384

    def _appendToLineBuffer(self, data):
        self._buffer.append(data)
        self._buffer_size += len(data)

    def clearLineBuffer(self):
        """Clear buffered data."""
        self._buffer, self._buffer_size = [], 0

    def dataReceived(self, data):
        """Protocol.dataReceived.
        Translates bytes into lines, and calls lineReceived (or
        rawDataReceived, depending on mode.)
        """
        if self._buffer is None:
            self._buffer = []

        if self.paused:
            self._was_paused = True
            self._appendToLineBuffer(data)
            return
        elif self._was_paused:
            # This is the call of dataReceived that follows an
            # unpausing. The buffer has been accumulating data without
            # processing it, so we need to send it all back through the
            # pipes.
            self._was_paused = False
            self._buffer.append(data)
            buf = self._buffer
            self.clearLineBuffer()
            for chunk in buf:
                why = self.dataReceived(chunk)
                if why or self.transport and self.transport.disconnecting:
                    return why
            return
        self._was_paused = False

        while self.line_mode and not self.paused:
            try:
                line, data = data.split(self.delimiter, 1)
            except ValueError:
                self._appendToLineBuffer(data)
                if self._buffer_size > self.MAX_LENGTH:
                    line = ''.join(self._buffer)
                    self.clearLineBuffer()
                    return self.lineLengthExceeded(line)
                break
            else:
                self._buffer.append(line)
                line = ''.join(self._buffer)
                self.clearLineBuffer()
                if len(line) > self.MAX_LENGTH:
                    return self.lineLengthExceeded(line)
                why = self.lineReceived(line)
                if why or self.transport and self.transport.disconnecting:
                    return why
                elif self.paused:
                    self._was_paused = True
                    self._appendToLineBuffer(data)
        else:
            if not self.paused:
                self._buffer.append(data)
                data = ''.join(self._buffer)
                self.clearLineBuffer()
                if data:
                    return self.rawDataReceived(data)

    def setLineMode(self, extra=''):
        """Sets the line-mode of this receiver.

        If you are calling this from a rawDataReceived callback,
        you can pass in extra unhandled data, and that data will
        be parsed for lines.  Further data received will be sent
        to lineReceived rather than rawDataReceived.

        Do not pass extra data if calling this function from
        within a lineReceived callback.
        """
        self.line_mode = 1
        if extra:
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
        return self.transport.writeSequence((line, self.delimiter))

    def lineLengthExceeded(self, line):
        """Called when the maximum line length has been reached.
        Override if it needs to be dealt with in some special way.

        The argument 'line' contains the remainder of the buffer, starting
        with (at least some part) of the line which is too long. This may
        be more than one line, or may be only the initial portion of the
        line.
        """
        return self.transport.loseConnection()


class StringTooLongError(AssertionError):
    """
    Raised when trying to send a string too long for a length prefixed
    protocol.
    """


class IntNStringReceiver(protocol.Protocol, _PauseableMixin):
    """
    Generic class for length prefixed protocols.

    @ivar structFormat: format used for struct packing/unpacking. Define it in
        subclass.
    @type structFormat: C{str}

    @ivar prefixLength: length of the prefix, in bytes. Define it in subclass,
        using C{struct.calcsize(structFormat)}
    @type prefixLength: C{int}

    @ivar _buffer: A list of data pieces received and buffered.
    @type _buffer: C{list} of C{str}

    @ivar _buffer_size: The amount of data stored in L{_buffer}.
    @type _buffer_size: C{int}

    @ivar _packet_length: The total length of the packet currently being
                          buffered up, including the prefix. The length
                          will be None until a full prefix can be
                          decoded.
    @type _packet_length: C{int} or C{None}

    @ivar recvd: A string representation of C{_buffer}. This is a
                 deprecated attribute, and will fire a
                 DeprecationWarning when accessed. Be very careful if
                 you write to this attribute, no sanity checking is
                 performed on the contents being injected into the
                 buffer.
    @type recvd: C{str}
    """
    MAX_LENGTH = 99999

    _buffer = None
    _buffer_size = 0
    _packet_length = None

    def _appendToBuffer(self, data):
        self._buffer.append(data)
        self._buffer_size += len(data)


    def _clearBuffer(self):
        """Clear buffered data."""
        self._buffer, self._buffer_size = [], 0


    def stringReceived(self, msg):
        """
        Override this.
        """
        raise NotImplementedError


    def lengthLimitExceeded(self, length):
        """
        Callback invoked when a length prefix greater than C{MAX_LENGTH} is
        received.  The default implementation disconnects the transport.
        Override this.

        @param length: The length prefix which was received.
        @type length: C{int}
        """
        self.transport.loseConnection()


    def dataReceived(self, data):
        """
        Convert int prefixed strings into calls to stringReceived.
        """
        if self._buffer is None:
            self._buffer = []
        self._appendToBuffer(data)

        while not self.paused:
            if self._packet_length is None:
                if self._buffer_size < self.prefixLength:
                    return
                data = ''.join(self._buffer)
                self._packet_length ,= struct.unpack(
                    self.structFormat, data[:self.prefixLength])
                if self._packet_length > self.MAX_LENGTH:
                    self._clearBuffer()
                    return self.lengthLimitExceeded(self._packet_length)
                self._packet_length += self.prefixLength
                self._buffer = [data]

            if self._packet_length is not None:
                if self._buffer_size < self._packet_length:
                    return
                data = ''.join(self._buffer)
                packet = data[self.prefixLength:self._packet_length]
                self._clearBuffer()
                self._appendToBuffer(data[self._packet_length:])
                self._packet_length = None
                self.stringReceived(packet)


    def sendString(self, data):
        """
        Send an prefixed string to the other end of the connection.

        @type data: C{str}
        """
        if len(data) >= 2 ** (8 * self.prefixLength):
            raise StringTooLongError(
                "Try to send %s bytes whereas maximum is %s" % (
                len(data), 2 ** (8 * self.prefixLength)))
        self.transport.writeSequence(
            (struct.pack(self.structFormat, len(data)), data))

    def _getRecvd(self):
        warnings.warn(
            "IntNStringReceiver.recvd deprecated since Twisted 8.3",
            DeprecationWarning, 2)
        if not self._buffer: # None or empty
            return ''
        elif len(self._buffer) > 1:
            self._buffer = ''.join(self._buffer)
        return self._buffer[0]

    def _setRecvd(self, data):
        warnings.warn("The recvd attribute of IntNStringReceiver is deprecated",
                      DeprecationWarning)
        self._buffer = [data]
        self._buffer_size = len(data)

    recvd = property(_getRecvd, _setRecvd)

class Int32StringReceiver(IntNStringReceiver):
    """
    A receiver for int32-prefixed strings.

    An int32 string is a string prefixed by 4 bytes, the 32-bit length of
    the string encoded in network byte order.

    This class publishes the same interface as NetstringReceiver.
    """
    structFormat = "!I"
    prefixLength = struct.calcsize(structFormat)


class Int16StringReceiver(IntNStringReceiver):
    """
    A receiver for int16-prefixed strings.

    An int16 string is a string prefixed by 2 bytes, the 16-bit length of
    the string encoded in network byte order.

    This class publishes the same interface as NetstringReceiver.
    """
    structFormat = "!H"
    prefixLength = struct.calcsize(structFormat)


class Int8StringReceiver(IntNStringReceiver):
    """
    A receiver for int8-prefixed strings.

    An int8 string is a string prefixed by 1 byte, the 8-bit length of
    the string.

    This class publishes the same interface as NetstringReceiver.
    """
    structFormat = "!B"
    prefixLength = struct.calcsize(structFormat)


class StatefulStringProtocol:
    """
    A stateful string protocol.

    This is a mixin for string protocols (Int32StringReceiver,
    NetstringReceiver) which translates stringReceived into a callback
    (prefixed with 'proto_') depending on state.

    The state 'done' is special; if a proto_* method returns it, the
    connection will be closed immediately.
    """

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
    """
    implements(interfaces.IProducer)

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

        self.deferred = deferred = defer.Deferred()
        self.consumer.registerProducer(self, False)
        return deferred

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
