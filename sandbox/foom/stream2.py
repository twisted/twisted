"""
def flen(f):
    f.seek(0, 2)
    return f.tell()

f=open('/etc/resolv.conf')
s=stream2.FileStream(f, 0, flen(f))
c=stream2.CompoundStream()
c.addStream(s)
c.addStr("***************")
a,b=c.split()
"""
  
"""
IPullProducer:
 - resumeProducing() is really read, with a consumer.write() callback.
 - consumer.registerProducer/unregisterProducer unnecessary.

IPushProducer:
 - resumeProducing() says to start writing data. read()
 - pauseProducing() stop writing data

PullStream:
 - passive, has read() method, which returns data, or a deferred if no data available.

PushStream:
 - active, has beginProducing(consumer) method, and then write()s to consumer.
 - resumeProducing() says to start writing data.
 - pauseProducing() stop writing data

StreamProducer: 
 - converts a pull stream into a producer
 - calls push.write(pull.read()) until pauseProducing is called.

ProducerStream
 - converts producers into a pull stream
 - when read() is called, returns a deferred, and calls producer.resumeProducing() and waits for a write() call.
"""

import copy
from zope.interface import Interface, Attribute
from twisted.internet.defer import Deferred

class IStream(Interface):
    length = Attribute("""How much data is in this stream. Can be None if unknown.""")
    
    def read():
        """Read some data.
        Returns an object conforming to the buffer interface, or
        else a Deferred.
        """
    def split(point):
        """Split this stream into two, at byte position 'point'.

        Returns a tuple of (before, after). A stream should not be used
        after calling split on it.

        If you cannot be implement this trivially, try return fallbackSplit(self, point).
        """

    def close():
        """Prematurely close."""

def fallbackSplit(stream, point):
    after = PostTruncaterStream(stream, point)
    before = TruncaterStream(stream, point, after)
    return (before, after)


class SimpleStream:
    implements(IStream)
    
    length = None
    start = None
    
    def read(self):
        return None

    def close(self):
        self.length = 0
    
    def split(self, point):
        if point > self.length:
            raise InvalidArgumentException("split point > length")
        b = copy.copy(self)
        self.length = point
        b.length -= point
        b.start += point
        return (self, b)
        
# maximum mmap size
MMAP_LIMIT = 4*1024*1024
# minimum mmap size
MMAP_THRESHOLD = 8*1024

class FileStream(SimpleStream):
    """A producer that produces data from a file"""
    # 65K, minus some slack
    CHUNK_SIZE = 2 ** 2 ** 2 ** 2 - 32

    f = None
    def __init__(self, f, start=0, length=None):
        self.f = f
        self.start = start
        self.length = length
        
    def read(self):
        if self.f is None:
            return None
        
        readSize = self.CHUNK_SIZE
        if self.length is not None:
            readSize = min(self.length, readSize)
        
        self.f.seek(self.start)
        b = self.f.read(readSize)
        bytesRead = len(b)
        if not bytesRead:
            self.f = None
            return None
        else:
            if self.length is not None:
                self.length -= bytesRead
            self.start += bytesRead
            return b

    def close(self):
        self.f = None
        SimpleStream.close(self)
        
class MemoryStream(SimpleStream):
    def __init__(self, mem, start=0, length=None):
        self.mem = mem
        self.start = start
        if length is None:
            self.length = len(mem)
        else:
            self.length = length

    def read(self):
        mem = self.mem
        if mem is None:
            return None
        self.mem = None
        return buffer(mem, self.start, self.length)

    def close(self):
        self.mem = None
        SimpleStream.close(self)
        
class CompoundStream:
    """An IStream which is composed of a bunch of substreams."""
    
    implements(IStream)
    deferred = None
    length = None
    
    def __init__(self):
        self.buckets = []
        
    def addStream(self, bucket):
        """Add a stream to the output"""
        self.buckets.append(bucket)
        if self.length is not None:
            if bucket.length is None:
                self.length = None
            else:
                self.length += bucket.length

    def addStr(self, s):
        """Shortcut to add a string to the output. 
        Simply calls self.addStream(MemoryStream(s))
        """
        self.addStream(MemoryStream(s))

    def read(self):
        if self.deferred is not None:
            raise RuntimeError("Call to read while read is already outstanding")

        if not self.buckets:
            return None
        
        result = self.buckets[0].read()
        if isinstance(result, Deferred):
            self.deferred = result
            result.addCallback(self._gotRead)
            return result
        
        return self._gotRead(result)
        
    def _gotRead(self, result):
        if result is None:
            del self.buckets[0]
            # Next bucket
            return self.read()
        
        if self.length is not None:
            self.length -= len(result)
        self.deferred = None
        return result
    
    def split(self, point):
        num = 0
        origPoint = point
        for bucket in self.buckets:
            num+=1

            if point == 0:
                b = CompoundStream()
                b.buckets = self.buckets[num:]
                del self.buckets[num:]
                return self,b
            
            if bucket.length is None:
                # Indeterminate length bucket.
                # give up and use fallback splitter.
                return fallbackSplit(self, origPoint)
            
            if point < bucket.length:
                before,after = bucket.split(point)
                b = CompoundStream()
                b.buckets = self.buckets[num:]
                b.buckets[0] = after
                
                del self.buckets[num+1:]
                self.buckets[num] = before
                return self,b
            
            point -= bucket.length
    
    def close(self):
        for bucket in self.buckets:
            bucket.close()
        self.buckets = []
        self.length = 0

def readAndDiscard(stream):
    def _gotData(data):
        if data is not None:
            readAndDiscard(stream)
    
    while True:
        result = stream.read()
        if result is None:
            break
        if isinstance(result, Deferred):
            result.addCallback(_gotData)
            break

class TruncaterStream:
    def __init__(self, stream, point, postTruncater):
        self.stream = stream
        self.length = point
        self.postTruncater = postTruncater
        
    def read(self):
        if self.length == 0:
            if self.postTruncater is not None:
                self.postTruncater.sendInitialSegment('')
            return None
        
        result = self.stream.read()
        if isinstance(result, Deferred):
            return result.addCallback(self._gotRead)
        else:
            return self._gotRead(result)
        
    def _gotRead(self, data):
        if data is None:
            raise InvalidArgumentException("Ran out of data for a split of a indeterminate length source")
        if self.length > len(data):
            self.length -= len(data)
            return data
        else:
            before = buffer(data, 0, self.length)
            after = buffer(data, self.length)
            self.length = 0
            if self.postTruncater is not None:
                self.postTruncater.sendInitialSegment(after)
                self.postTruncater = None
            return before
    
    def split(self, point):
        if point > self.length:
            raise InvalidArgumentException("split point > length")
        
        post = PostTruncaterStream(TruncaterStream(stream, self.length - point, self.postTruncater))
        self.length = point
        self.postTruncater = post
        return self, post
    
    def close(self):
        if self.postTruncater is not None:
            self.postTruncater.notifyClosed(self)
        else:
            # Nothing cares about the rest of the stream
            self.stream.close()
            self.stream = None
            self.length = 0
            

class PostTruncaterStream:
    deferred = None
    sentInitialSegment = False
    truncaterClosed = None
    
    length = None
    
    def __init__(self, stream, point):
        self.stream = stream
        self.deferred = Deferred()
        if stream.length is not None:
            self.length = stream.length - point

    def read(self):
        if not self.sentInititalSegment:
            self.sentInitialSegment = True
            if self.truncaterClosed is not None:
                readAndDiscard(truncaterClosed)
                truncaterClosed = None
            return self.deferred
        
        return self.stream.read()
    
    def split(self, point):
        XXX
        
    def close(self):
        
        
    def sendInitialSegment(self, data):
        self.deferred.callback(data)

    def notifyClosed(self, truncater):
        if self.sentInitialSegment:
            readAndDiscard(self, truncater)
        else:
            self.truncaterClosed = truncater

            
class ProducerStream:
    """Turns producers into a IStream.
    Thus, implements IConsumer and IStream."""

    implements(IStream, IConsumer)
    length = None
    closed = False
    bufferSize = 5
    
    def __init__(self):
        self.buffer = []

    # IStream implementation
    def read(self):
        if self.buffer:
            result = self.buffer[0]
            del self.buffer[0]
            return result
        else:
            deferred = self.deferred = Deferred()
            if self.producer is not None and (not self.streamingProducer
                                              or self.producerPaused):
                self.producerPaused = False
                self.producer.resumeProducing()
                
            return deferred
        
    def split(self, point):
        return fallbackSplit(self, point)
    
    def close(self):
        self.closed = True
        if self.producer is not None:
            self.producer.stopProducing()
            self.producer = None
            self.deferred = None
    
    # IConsumer implementation
    def write(self, data):
        if self.closed:
            return
        
        if self.deferred:
            deferred = self.deferred
            self.deferred = None
            deferred.callback(data)
        else:
            self.buffer.append(data)
            if(self.producer is not None and self.streamingProducer
               and len(self.buffer) > self.bufferSize):
                producer.pauseProducing()
                self.producerPaused = True
    
    def registerProducer(self, producer, streaming):
        if self.producer is not None:
            raise RuntimeError("Cannot register producer %s, because producer %s was never unregistered." % (producer, self.producer))
        
        if self.closed:
            producer.stopProducing()
        else:
            self.producer = producer
            self.streamingProducer = streaming
            if not streaming:
                producer.resumeProducing()

    def unregisterProducer(self):
        self.producer = None
        
class StreamProducer:
    """A push producer which gets its data by reading a stream."""
    implements(IPushProducer)

    def __init__(self, stream):
        self.stream = stream

    def beginProducing(self, consumer):
        self.consumer = consumer
        self.consumer.registerProducer(self, True)

    def resumeProducing(self):
        self.paused = False
        if self.deferred is not None:
            return
        
        data = self.stream.read()
        
        if isinstance(data, Deferred):
            # FIXME: what about errback?
            self.deferred = data.addCallback(self._doWrite)
        else:
            self._doWrite(data)

    def _doWrite(self, data):
        if data is None:
            # The end.
            self.consumer.unregisterProducer(self)
        self.deferred = None
        self.consumer.write(data)
        
        if not self.paused:
            self.resumeProducing()
        
    def pauseProducing(self):
        self.paused = True

    def stopProducing(self):
        self.paused = True
        self.stream.close()
        self.stream = None
