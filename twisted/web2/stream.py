from twisted.internet import defer,main,protocol
from twisted.python import components
from zope.interface import implements, Attribute

class IStream(components.Interface):
    def beginProducing(self, consumer):
        pass

    finishedCallback = Attribute("A Deferred to call when done")


class BufferedStream:
    """This lets you (a producer) write strings and streams and it will buffer
    it until a consumer has been registered with beginProducing().

    This lets you easily interleave files and text.
    """
    implements(IStream)

    registered = False
    consumer = None
    closed = False
    
    def __init__(self):
        self.buffer = []
    
    def beginProducing(self, consumer):
        self.consumer = consumer
        d = self._onDone = defer.Deferred()
        self.registered = True
        self.consumer.registerProducer(self, False)
        return d
    
    def write(self, data):
        self.buffer.append(data)

        if not self.registered and self.consumer is not None:
            self.registered = True
            self.consumer.registerProducer(self, False)
            
    def close(self):
        self.closed = True
    
        if not self.registered and self.consumer is not None:
            self._onDone.callback(None)
            
    def resumeProducing(self):
        if len(self.buffer) == 0:
            self.consumer.unregisterProducer()
            self.registered = False
            if self.closed:
                self._onDone.callback(None)
            return
        
        data = self.buffer[0]
        del self.buffer[0]
        
        if isinstance(data, str):
            self.consumer.write(data)
        else:
            try:
                self.consumer.unregisterProducer()
                d = IProducer(data).beginProducing(self.consumer)
                d.addCallbacks(lambda x: self.consumer.registerProducer(self, False),
                               lambda err: self._onDone.errback(err))
            except:
                self._onDone.errback()
        
            
    def stopProducing(self):
        self._onDone.errback(main.CONNECTION_LOST)

components.backwardsCompatImplements(BufferedStream)

# The following three classes implement sending a file to a consumer.
# It is somewhat complicated by the fact that sendfile is supported, and
# requires a slightly different set of state, and that we can't know ahead
# of time if the consumer will accept sendfile calls.

class BaseFileProducer:
    """A producer that produces data from a file"""
    CHUNK_SIZE = 2 ** 2 ** 2 ** 2

    sendfileable = True #assumed true until proven otherwise
    
    def __init__(self, f, start=None, length=None, closeWhenDone=True):
        self.f = f
        self.offset = start
        self.bytesRemaining = length
        
        self.closeWhenDone = closeWhenDone
        self.finishedCallback = defer.Deferred()
        if self.closeWhenDone:
            def _close(x):
                self.f.close()
                return x
            self.finishedCallback.addBoth(_close)
        
    def beginProducing(self, consumer):
        self.consumer = consumer
        self.consumer.registerProducer(self, False)
        return self.finishedCallback

    def stopProducing(self):
        self.finishedCallback.errback(main.CONNECTION_LOST)

class SendfileProducer(BaseFileProducer):
    def convertFromBase(self):
        # Two changes necessary:
        # - self.offset needs to be set.
        # - self.bytesRemaining needs to be set if it is None
        
        if self.offset is None:
            self.offset = self.f.tell()
        if self.bytesRemaining is None: # when no limit was specified
            self.f.seek(0, 2) # seek to end of file
            self.bytesRemaining = f.tell() - self.offset
            
        self.__class__ = SendfileProducer

    def resumeProducing(self):
        if not self.f:
            raise "resumeProducing() called but I have no file!"
        readSize = min(self.bytesRemaining, self.CHUNK_SIZE)

        try:
            amt = self.consumer.sendfile(self.f, self.offset, readSize)
            self.bytesRemaining -= amt
            self.offset += amt
            if self.bytesRemaining == 0:
                self.consumer.unregisterProducer()
                self.finishedCallback.callback('')
                self.finishedCallback = self.f = self.consumer = None
        except IOError:
            # we can't sendfile for some reason, revert to normal IO.
            self.sendfileable = False
            FileProducer.convertFromSendfile(self)
            self.resumeProducing(self)
        
class FileProducer(BaseFileProducer):
    def convertFromBase(self):
        # - Uses the file pointer, not self.offset
        # - Seek the file to self.offset.
        if self.offset is not None:
            self.f.seek(self.offset)
        
    # change the class to SendfileProducer, if possible.
    def beginProducing(self, consumer):
        if hasattr(consumer, 'sendfile'): # fixme: interface?
            try:
                SendfileProducer.convertFromBase(self)
            except IOError:
                pass
            else:
                return self.beginProducing(consumer) # redispatch to new class
        
        # otherwise:
        self.convertFromBase()
        return BaseFileProducer.beginProducing(self, consumer)
        
    def resumeProducing(self):
        if not self.f:
            raise "resumeProducing() called but I have no file!"
        readSize = self.CHUNK_SIZE
        if self.bytesRemaining is not None:
            readSize = min(self.bytesRemaining, readSize)
        
        b = self.f.read(readSize)
        if not b:
            self.consumer.unregisterProducer()
            self.finishedCallback.callback('')
            self.finishedCallback = self.f = self.consumer = None
        else:
            if self.bytesRemaining is not None:
                self.bytesRemaining -= len(b)
            self.consumer.write(b)
    
class StreamFilter:
    """A base class for stream filters. A passthrough subclass would override
       write(data) to call self.consumer.write(data).
       """
    
    def __init__(self, istream):
        """istream is the stream we're going to filter."""
        self.finishedCallback = defer.Deferred()
        self.istream = istream

    def beginProducing(self, consumer):
        self.consumer = consumer
        # This calls self.registerProducer() and thus consumer.registerProducer
        self.istream.beginProducing(self).chainDeferred(self.finishedCallback)
        
        return self.finishedCallback

# Producer methods, called from consumer.
    def resumeProducing(self):
        self.producer.resumeProducing()

    def pauseProducing(self):
        self.producer.pauseProducing()

    def stopProducing(self):
        self.producer.stopProducing()

# Consumer methods, called from producer
    def registerProducer(self, producer, push):
        self.producer = producer
        self.consumer.registerProducer(self, push)
        
    def unregisterProducer(self):
        self.consumer.unregisterProducer()
        self.producer = None
    
class SimpleStreamFilter(StreamFilter):
    """A simple stream filter that calls self.consumer.write(fun(data))
    to filter the data, with the given fun."""
    def __init__(self, istream, fun):
        StreamFilter.__init__(self, istream)
        self.write = lambda data: self.consumer.write(fun(data))



########### The rest of this file is mostly just playing around ###########
### Test Reimplementation of LineReceiver as a StreamFilter to see how this goes.
class LineReceiver(StreamFilter):
    """A stream that converts data into lines and/or raw data, depending on mode.
    
    In line mode, each line that's received calls the consumers writeLine
    method.  In raw data mode, each chunk of raw data becomes a
    call to L{writeRawData}.  The L{setLineMode} and L{setRawMode}
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
    paused = False
    
    def clearLineBuffer(self):
        """Clear buffered data."""
        self.__buffer = ""
    
    def write(self, data):
        """Protocol.dataReceived.
        Translates bytes into lines, and calls lineReceived (or
        rawDataReceived, depending on mode.)
        """
        buf = self.__buffer+data
        lastoffset=0
        while self.line_mode:
            if self.paused:
                break

            offset=buf.find(self.delimiter, lastoffset)
            if offset == -1:
                self.__buffer=buf=buf[lastoffset:]
                if len(buf) > self.MAX_LENGTH:
                    line=buf
                    self.__buffer=''
                    return self.lineLengthExceeded(line)
                break
            
            line=buf[lastoffset:offset]
            lastoffset=offset+len(self.delimiter)
            
            if len(line) > self.MAX_LENGTH:
                line=buf[lastoffset:]
                self.__buffer=''
                return self.lineLengthExceeded(line)
            why = self.consumer.writeLine(line)
            if why:
                self.__buffer = buf[lastoffset:]
                return why
        else:
            if not self.paused:
                data=buf[lastoffset:]
                self.__buffer=''
                if data:
                    return self.consumer.writeRawData(data)

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

    def lineLengthExceeded(self, line):
        """Called when the maximum line length has been reached.
        Override if it needs to be dealt with in some special way.
        """
        return self.producer.stopProducing()

    def pauseProducing(self):
        self.paused = True
        StreamFilter.pauseProducing(self)

    def resumeProducing(self):
        self.paused = False
        self.dataReceived('')
        StreamFilter.resumeProducing(self)

    def stopProducing(self):
        self.paused = True
        StreamFilter.stopProducing(self)


class StreamProtocol(protocol.Protocol):
    begun = False
    
    def __init__(self):
        self.finishedCallback = defer.Deferred()
        self.istream = self
        self.ostream = BufferedStream()
        
    def connectionMade(self):
        if self.begun:
            self.consumer.registerProducer(self.transport, True)
        else:
            self.transport.stopReading()
            
        self.ostream.beginProducing(self.transport)
        
    def beginProducing(self, consumer):
        self.consumer = consumer
        # shortcut the extra method call
        self.dataReceived = self.consumer.write

        if self.transport:
            self.transport.startReading()
            self.consumer.registerProducer(self.transport, True)
        self.begun = True
        return self.finishedCallback

    def connectionLost(self, reason):
        self.finishedCallback.callback(reason)

# Producer methods, called from consumer.
    def resumeProducing(self):
        self.transport.startReading()

    def pauseProducing(self):
        self.transport.stopReading()

    def stopProducing(self):
        self.transport.loseConnection()

    def dataReceived(self, data):
        #NOTE: this method isn't actually used, it's replaced in beginProducing
        self.consumer.write(data)


if __name__ == '__builtin__':
    # Simple test for running with twistd
    from twisted.application import service
    from twisted.application import internet

    class SimpleConsumer:
        def __init__(self, **kw):
            for k,v in kw.iteritems():
                setattr(self, k, v)

        def registerProducer(self, producer, pull):
            pass

        def unregisterProducer(self):
            pass

    class SimpleProtocol:
        def __init__(self, istream, ostream):
            self.istream, self.ostream = istream, ostream
            istream = LineReceiver(istream)
            consumer = SimpleConsumer(writeLine=lambda data: ostream.write("YoHoHo, Line=%s\n\r"%data),
                                      writeRawData=lambda data: ostream.write("YoHoHo, Raw Data=%s\r\n"%data))
            istream.beginProducing(consumer).addBoth(lambda d: ostream.close())
            
            
    class SimpleFactory(protocol.ServerFactory):
        protocol = StreamProtocol

        def buildProtocol(self, addr):
            p = protocol.ServerFactory.buildProtocol(self, addr)
            p2 = SimpleProtocol(p.istream, p.ostream)
            return p
            
    application = service.Application("simple")
    internet.TCPServer(
        8000, 
        SimpleFactory()
        ).setServiceParent(application)
