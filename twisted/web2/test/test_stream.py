import tempfile, operator, sys, os

from twisted.trial import unittest
from twisted.trial.util import wait, spinUntil
from twisted.trial.assertions import *
from twisted.internet import defer

from zope.interface import Interface, Attribute, implements

from twisted.python.util import sibpath
from twisted.web2 import stream

def bufstr(data):
    try:
        return str(buffer(data))
    except TypeError:
        raise TypeError("%s doesn't conform to the buffer interface" % (data,))
    
    
class SimpleStreamTests:
    text = '1234567890'
    def test_split(self):
        for point in range(10):
            s = self.makeStream(0)
            a,b = s.split(point)
            if point > 0:
                assertEquals(bufstr(a.read()), self.text[:point])
            assertEquals(a.read(), None)
            if point < len(self.text):
                assertEquals(bufstr(b.read()), self.text[point:])
            assertEquals(b.read(), None)

        for point in range(7):
            s = self.makeStream(2, 6)
            assertEquals(s.length, 6)
            a,b = s.split(point)
            if point > 0:
                assertEquals(bufstr(a.read()), self.text[2:point+2])
            assertEquals(a.read(), None)
            if point < 6:
                assertEquals(bufstr(b.read()), self.text[point+2:8])
            assertEquals(b.read(), None)

    def test_read(self):
        s = self.makeStream()
        assertEquals(s.length, len(self.text))
        assertEquals(bufstr(s.read()), self.text)
        assertEquals(s.read(), None)

        s = self.makeStream(0, 4)
        assertEquals(s.length, 4)
        assertEquals(bufstr(s.read()), self.text[0:4])
        assertEquals(s.read(), None)
        assertEquals(s.length, 0)

        s = self.makeStream(4, 6)
        assertEquals(s.length, 6)
        assertEquals(bufstr(s.read()), self.text[4:10])
        assertEquals(s.read(), None)
        assertEquals(s.length, 0)
    
class FileStreamTest(SimpleStreamTests, unittest.TestCase):
    def makeStream(self, *args, **kw):
        return stream.FileStream(self.f, *args, **kw)
    
    def setUpClass(self):
        f = tempfile.TemporaryFile('w+')
        f.write(self.text)
        f.seek(0, 0)
        self.f = f

    def test_close(self):
        s = self.makeStream()
        s.close()

        assertEquals(s.length, 0)
        # Make sure close doesn't close file
        # would raise exception if f is closed
        self.f.seek(0, 0)

    def test_read2(self):
        s = self.makeStream(0)
        s.CHUNK_SIZE = 6
        assertEquals(s.length, 10)
        assertEquals(bufstr(s.read()), self.text[0:6])
        assertEquals(bufstr(s.read()), self.text[6:10])
        assertEquals(s.read(), None)

        s = self.makeStream(0)
        s.CHUNK_SIZE = 5
        assertEquals(s.length, 10)
        assertEquals(bufstr(s.read()), self.text[0:5])
        assertEquals(bufstr(s.read()), self.text[5:10])
        assertEquals(s.read(), None)

        s = self.makeStream(0, 20)
        assertEquals(s.length, 20)
        assertEquals(bufstr(s.read()), self.text)
        assertRaises(RuntimeError, s.read) # ran out of data

class MMapFileStreamTest(SimpleStreamTests, unittest.TestCase):
    def makeStream(self, *args, **kw):
        return stream.FileStream(self.f, *args, **kw)
    
    def setUpClass(self):
        f = tempfile.TemporaryFile('w+')
        self.text = self.text*(stream.MMAP_THRESHOLD//len(self.text) + 1)
        f.write(self.text)
        f.seek(0, 0)
        self.f=f
            
class MemoryStreamTest(SimpleStreamTests, unittest.TestCase):
    def makeStream(self, *args, **kw):
        return stream.MemoryStream(self.text, *args, **kw)

    def test_close(self):
        s = self.makeStream()
        s.close()
        assertEquals(s.length, 0)

    def test_read2(self):
        assertRaises(ValueError, self.makeStream, 0, 20)


class TestStreamer:
    implements(stream.IStream)

    length = None

    readCalled=0
    closeCalled=0
    
    def __init__(self, list):
        self.list = list
        
    def read(self):
        self.readCalled+=1
        if self.list:
            return self.list.pop(0)
        return None

    def close(self):
        self.closeCalled+=1
        self.list = []
        
class FallbackSplitTest(unittest.TestCase):
    def test_split(self):
        s = TestStreamer(['abcd', defer.succeed('efgh'), 'ijkl'])
        left,right = stream.fallbackSplit(s, 5)
        
        assertEquals(left.length, 5)
        assertEquals(right.length, None)
        
        assertEquals(bufstr(left.read()), 'abcd')
        assertEquals(bufstr(wait(left.read())), 'e')
        assertEquals(left.read(), None)

        assertEquals(bufstr(right.read().result), 'fgh')
        assertEquals(bufstr(right.read()), 'ijkl')
        assertEquals(right.read(), None)

    def test_split2(self):
        s = TestStreamer(['abcd', defer.succeed('efgh'), 'ijkl'])
        left,right = stream.fallbackSplit(s, 4)
        
        assertEquals(left.length, 4)
        assertEquals(right.length, None)
        
        assertEquals(bufstr(left.read()), 'abcd')
        assertEquals(left.read(), None)

        assertEquals(bufstr(right.read().result), 'efgh')
        assertEquals(bufstr(right.read()), 'ijkl')
        assertEquals(right.read(), None)

    def test_splitsplit(self):
        s = TestStreamer(['abcd', defer.succeed('efgh'), 'ijkl'])
        left,right = stream.fallbackSplit(s, 5)
        left,middle = left.split(3)
        
        assertEquals(left.length, 3)
        assertEquals(middle.length, 2)
        assertEquals(right.length, None)
        
        assertEquals(bufstr(left.read()), 'abc')
        assertEquals(left.read(), None)

        assertEquals(bufstr(middle.read().result), 'd')
        assertEquals(bufstr(middle.read().result), 'e')
        assertEquals(middle.read(), None)

        assertEquals(bufstr(right.read().result), 'fgh')
        assertEquals(bufstr(right.read()), 'ijkl')
        assertEquals(right.read(), None)

    def test_closeboth(self):
        s = TestStreamer(['abcd', defer.succeed('efgh'), 'ijkl'])
        left,right = stream.fallbackSplit(s, 5)
        left.close()
        assertEquals(s.closeCalled, 0)
        right.close()

        # Make sure nothing got read
        assertEquals(s.readCalled, 0)
        assertEquals(s.closeCalled, 1)

    def test_closeboth_rev(self):
        s = TestStreamer(['abcd', defer.succeed('efgh'), 'ijkl'])
        left,right = stream.fallbackSplit(s, 5)
        right.close()
        assertEquals(s.closeCalled, 0)
        left.close()

        # Make sure nothing got read
        assertEquals(s.readCalled, 0)
        assertEquals(s.closeCalled, 1)

    def test_closeleft(self):
        s = TestStreamer(['abcd', defer.succeed('efgh'), 'ijkl'])
        left,right = stream.fallbackSplit(s, 5)
        left.close()
        assertEquals(bufstr(wait(right.read())), 'fgh')
        assertEquals(bufstr(right.read()), 'ijkl')
        assertEquals(right.read(), None)

    def test_closeright(self):
        s = TestStreamer(['abcd', defer.succeed('efgh'), 'ijkl'])
        left,right = stream.fallbackSplit(s, 3)
        right.close()

        assertEquals(bufstr(left.read()), 'abc')
        assertEquals(left.read(), None)
        
        assertEquals(s.closeCalled, 1)


class ProcessStreamerTest(unittest.TestCase):

    def runCode(self, code, inputStream=None):
        if inputStream is None:
            inputStream = stream.MemoryStream("")
        return stream.ProcessStreamer(inputStream, sys.executable, [sys.executable, "-c", code],
                                      os.environ)

    def test_output(self):
        p = self.runCode("import sys\nfor i in range(100): sys.stdout.write('x' * 1000)")
        l = []
        d = stream.pullStream(p.outStream, l.append)
        def verify(_):
            assertEquals("".join(l), ("x" * 1000) * 100)
        p.run()
        return d.addCallback(verify)

    def test_errouput(self):
        p = self.runCode("import sys\nfor i in range(100): sys.stderr.write('x' * 1000)")
        l = []
        d = stream.pullStream(p.errStream, l.append)
        def verify(_):
            assertEquals("".join(l), ("x" * 1000) * 100)
        p.run()
        return d.addCallback(verify)

    def test_input(self):
        p = self.runCode("import sys\nsys.stdout.write(sys.stdin.read())",
                         stream.MemoryStream("hello world"))
        l = []
        d = stream.pullStream(p.outStream, l.append)
        d2 = p.run(True)
        def verify(_):
            assertEquals("".join(l), "hello world")
            return d2
        from twisted.internet import error
        return d.addCallback(verify).addErrback(lambda _: _.trap(error.ProcessDone))


class AdapterTestCase(unittest.TestCase):

    def test_adapt(self):
        f = file("foo", "w")
        f.write("test")
        f.close()
        for i in ("test", buffer("test"), file("foo")):
            s = stream.IByteStream(i)
            assertEquals(str(s.read()), "test")
            assertEquals(s.read(), None)


from twisted.web2.stream import *
class CompoundStreamTest:
    """
    CompoundStream lets you combine many streams into one continuous stream.
    For example, let's make a stream:
    >>> s = CompoundStream()
    
    Then, add a couple streams:
    >>> s.addStream(MemoryStream("Stream1"))
    >>> s.addStream(MemoryStream("Stream2"))
    
    The length is the sum of all the streams:
    >>> s.length
    14
    
    We can read data from the stream:
    >>> str(s.read())
    'Stream1'

    After having read some data, length is now smaller, as you might expect:
    >>> s.length
    7

    So, continue reading...
    >>> str(s.read())
    'Stream2'

    Now that the stream is exhausted:
    >>> s.read() is None
    True
    >>> s.length
    0

    
    For a more complicated example, let's try reading from a file:
    >>> s = CompoundStream()
    >>> s.addStream(FileStream(open(sibpath(__file__, "stream_data.txt"))))
    >>> s.addStream("================")
    >>> s.addStream(FileStream(open(sibpath(__file__, "stream_data.txt"))))

    Again, the length is the sum:
    >>> s.length
    58L
    
    >>> str(s.read())
    "We've got some text!\\n"
    >>> str(s.read())
    '================'
    
    What if you close the stream?
    >>> s.close()
    >>> s.read() is None
    True
    >>> s.length
    0
	"""

__doctests__ = ['twisted.web2.test.test_stream.CompoundStreamTest']
# TODO: 
# CompoundStreamTest
# ProducerStreamTest
# StreamProducerTest
