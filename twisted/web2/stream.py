"""
def flen(f):
    f.seek(0, 2)
    return f.tell()

f=open('/etc/resolv.conf')
s=stream2.FileStream(f, 0, flen(f))
c=stream2.CompoundStream()
c.addStream(s)
c.addStr("***************")
a,b=c.split(10)
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

import copy,os
from zope.interface import Interface, Attribute, implements
from twisted.internet.defer import Deferred
from twisted.internet import interfaces as ti_interfaces, defer

import mmap

class IStream(Interface):
    """A stream of arbitrary data."""
    
    def read():
        """Read some data.
        Returns some object or else a Deferred.
        """
        
    def close():
        """Prematurely close."""

class IByteStream(IStream):
    """A stream which is of bytes."""
    
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

class ISendfileableStream(Interface):
    def read(sendfile=False):
        """
        Read some data.
        If sendfile == False, returns an object conforming to the buffer
        interface, or else a Deferred.

        If sendfile == True, returns either the above, or a SendfileBuffer.
        """
        
class SimpleStream:
    implements(IByteStream)
    
    length = None
    start = None
    
    def read(self):
        return None

    def close(self):
        self.length = 0
    
    def split(self, point):
        if self.length is not None:
            if point > self.length:
                raise ValueError("split point (%d) > length (%d)" % (point, self.length))
        b = copy.copy(self)
        self.length = point
        if b.length is not None:
            b.length -= point
        b.start += point
        return (self, b)
        
# maximum mmap size
MMAP_LIMIT = 4*1024*1024
# minimum mmap size
MMAP_THRESHOLD = 8*1024

# maximum sendfile length
SENDFILE_LIMIT = 16777216
# minimum sendfile size
SENDFILE_THRESHOLD = 256

def mmapwrapper(*args, **kwargs):
    """
    Python's mmap call sucks and ommitted the "offset" argument for no
    discernable reason. Replace this with a mmap module that has offset.
    """
    
    offset = kwargs.get('offset', None)
    if offset == 0:
        del kwargs['offset']
    else:
        raise mmap.error("mmap: Python sucks and does not support offset.")
    return mmap.mmap(*args, **kwargs)

class FileStream(SimpleStream):
    implements(ISendfileableStream)
    """A producer that produces data from a file. File must be a normal
    file that supports seek or this won't work."""
    # 65K, minus some slack
    CHUNK_SIZE = 2 ** 2 ** 2 ** 2 - 32

    f = None
    def __init__(self, f, start=0, length=None, useMMap=True):
        self.f = f
        self.start = start
        if length is None:
            self.length = os.fstat(f.fileno()).st_size
        else:
            self.length = length
        self.useMMap = useMMap
        
    def read(self, sendfile=False):
        if self.f is None:
            return None

        length = self.length
        if length == 0:
            self.f = None
            return None

        if sendfile and length > SENDFILE_THRESHOLD:
            # XXX: Yay using non-existent sendfile support!
            # FIXME: if we return a SendfileBuffer, and then sendfile
            #        fails, then what? Or, what if file is too short?
            readSize = min(length, SENDFILE_LIMIT)
            res = SendfileBuffer(self.f, self.start, readSize)
            self.length -= readSize
            self.start += readSize
            return res

        if self.useMMap and length > MMAP_THRESHOLD:
            readSize = min(length, MMAP_LIMIT)
            try:
                res = mmapwrapper(self.f.fileno(), readSize,
                                  access=mmap.ACCESS_READ, offset=self.start)
                #madvise(res, MADV_SEQUENTIAL)
                self.length -= readSize
                self.start += readSize
                return res
            except mmap.error:
                pass

        # Fall back to standard read.
        readSize = min(length, self.CHUNK_SIZE)

        self.f.seek(self.start)
        b = self.f.read(readSize)
        bytesRead = len(b)
        if not bytesRead:
            raise RuntimeError("Ran out of data reading file %r, expected %d more bytes" % (self.f, length))
        else:
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
            self.length = len(mem) - start
        else:
            if len(mem) < length:
                raise ValueError("len(mem) < start + length")
            self.length = length

    def read(self):
        if self.mem is None:
            return None
        if self.length == 0:
            result = None
        else:
            result = buffer(self.mem, self.start, self.length)
        self.mem = None
        self.length = 0
        return result

    def close(self):
        self.mem = None
        SimpleStream.close(self)
        
class CompoundStream:
    """An IByteStream which is composed of a bunch of substreams."""
    
    implements(IByteStream, ISendfileableStream)
    deferred = None
    length = 0
    
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

    def read(self, sendfile=False):
        if self.deferred is not None:
            raise RuntimeError("Call to read while read is already outstanding")

        if not self.buckets:
            return None
        
        if sendfile and ISendfileableStream.providedBy(self.buckets[0]):
            result = self.buckets[0].read(sendfile)
        else:
            result = self.buckets[0].read()
        
        if isinstance(result, Deferred):
            self.deferred = result
            result.addCallback(self._gotRead, sendfile)
            return result
        
        return self._gotRead(result, sendfile)
        
    def _gotRead(self, result, sendfile):
        if result is None:
            del self.buckets[0]
            # Next bucket
            return self.read(sendfile)
        
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
            # FIXME: what about errback?
            result.addCallback(_gotData)
            break

def fallbackSplit(stream, point):
    after = PostTruncaterStream(stream, point)
    before = TruncaterStream(stream, point, after)
    return (before, after)

class TruncaterStream:
    def __init__(self, stream, point, postTruncater):
        self.stream = stream
        self.length = point
        self.postTruncater = postTruncater
        
    def read(self):
        if self.length == 0:
            if self.postTruncater is not None:
                postTruncater = self.postTruncater
                self.postTruncater = None
                postTruncater.sendInitialSegment(self.stream.read())
            self.stream = None
            return None
        
        result = self.stream.read()
        if isinstance(result, Deferred):
            return result.addCallback(self._gotRead)
        else:
            return self._gotRead(result)
        
    def _gotRead(self, data):
        if data is None:
            raise ValueError("Ran out of data for a split of a indeterminate length source")
        if self.length >= len(data):
            self.length -= len(data)
            return data
        else:
            before = buffer(data, 0, self.length)
            after = buffer(data, self.length)
            self.length = 0
            if self.postTruncater is not None:
                postTruncater = self.postTruncater
                self.postTruncater = None
                postTruncater.sendInitialSegment(after)
                self.stream = None
            return before
    
    def split(self, point):
        if point > self.length:
            raise ValueError("split point (%d) > length (%d)" % (point, self.length))

        post = PostTruncaterStream(self.stream, point)
        trunc = TruncaterStream(post, self.length - point, self.postTruncater)
        self.length = point
        self.postTruncater = post
        return self, trunc
    
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
    closed = False
    
    length = None
    def __init__(self, stream, point):
        self.stream = stream
        self.deferred = Deferred()
        if stream.length is not None:
            self.length = stream.length - point

    def read(self):
        if not self.sentInitialSegment:
            self.sentInitialSegment = True
            if self.truncaterClosed is not None:
                readAndDiscard(self.truncaterClosed)
                self.truncaterClosed = None
            return self.deferred
        
        return self.stream.read()
    
    def split(self, point):
        return fallbackSplit(self, point)
        
    def close(self):
        self.closed = True
        if self.truncaterClosed is not None:
            # have first half close itself
            self.truncaterClosed.postTruncater = None
            self.truncaterClosed.close()
        elif self.sentInitialSegment:
            # first half already finished up
            self.stream.close()
            
        self.deferred = None
    
    # Callbacks from TruncaterStream
    def sendInitialSegment(self, data):
        if self.closed:
            # First half finished, we don't want data.
            self.stream.close()
            self.stream = None
        if self.deferred is not None:
            if isinstance(data, Deferred):
                data.chainDeferred(self.deferred)
            else:
                self.deferred.callback(data)
        
    def notifyClosed(self, truncater):
        if self.closed:
            # we are closed, have first half really close
            truncater.postTruncater = None
            truncater.close()
        elif self.sentInitialSegment:
            # We are trying to read, read up first half
            readAndDiscard(self, truncater)
        else:
            # Idle, store closed info.
            self.truncaterClosed = truncater

            
class ProducerStream:
    """Turns producers into a IByteStream.
    Thus, implements IConsumer and IByteStream."""

    implements(IByteStream, ti_interfaces.IConsumer)
    length = None
    closed = False
    producer = None
    producerPaused = False
    deferred = None
    
    bufferSize = 5
    
    def __init__(self, length=None):
        self.buffer = []

    # IByteStream implementation
    def read(self):
        if self.buffer:
            return self.buffer.pop(0)
        elif self.closed:
            self.length = 0
            return None
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
        self.buffer=[]
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

    def finish(self):
        self.closed = True
        if self.deferred is not None:
            deferred = self.deferred
            self.deferred = None
            deferred.callback(None)

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
    implements(ti_interfaces.IPushProducer)

    deferred = None
    finishedCallback = None
    paused = False
    consumer = None
    
    def __init__(self, stream, enforceStr=True):
        self.stream = stream
        self.enforceStr = enforceStr
        
    def beginProducing(self, consumer):
        if self.stream is None:
            return defer.succeed(None)
        
        self.consumer = consumer
        finishedCallback = self.finishedCallback = Deferred()
        self.consumer.registerProducer(self, True)
        self.resumeProducing()
        return finishedCallback
    
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
        if self.consumer is None:
            return
        if data is None:
            # The end.
            self.consumer.unregisterProducer()
            self.finishedCallback.callback(None)
            self.finishedCallback = self.deferred = self.consumer = self.stream = None
            return
        
        self.deferred = None
        if self.enforceStr:
            # XXX: sucks that we have to do this. make transport.write(buffer) work!
            data = str(data)
        self.consumer.write(data)
        
        if not self.paused:
            self.resumeProducing()
        
    def pauseProducing(self):
        self.paused = True

    def stopProducing(self):
        if self.finishedCallback is not None:
            from twisted.internet import main
            self.finishedCallback.callback(main.CONNECTION_LOST)
        self.paused = True
        if self.stream is not None:
            self.stream.close()
        if self.consumer is not None:
            self.consumer.unregisterProducer()
            
        self.finishedCallback = self.deferred = self.consumer = self.stream = None

__all__ = ['IStream', 'IByteStream', 'FileStream', 'MemoryStream', 'CompoundStream', 'fallbackSplit', 'ProducerStream', 'StreamProducer']
