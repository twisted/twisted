import tempfile, operator, sys, os

from twisted.trial import unittest
from twisted.trial.util import wait, spinUntil
from twisted.trial.assertions import *
from twisted.internet import reactor, defer, interfaces
from twisted.python import log
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
    implements(stream.IStream, stream.IByteStream)

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

    if interfaces.IReactorProcess(reactor, None) is None:
        skip = "Platform lacks spawnProcess support, can't test process streaming."

    def runCode(self, code, inputStream=None):
        if inputStream is None:
            inputStream = stream.MemoryStream("")
        return stream.ProcessStreamer(inputStream, sys.executable, [sys.executable, "-c", code],
                                      os.environ)

    def test_output(self):
        p = self.runCode("import sys\nfor i in range(100): sys.stdout.write('x' * 1000)")
        l = []
        d = stream.readStream(p.outStream, l.append)
        def verify(_):
            assertEquals("".join(l), ("x" * 1000) * 100)
        d2 = p.run()
        return d.addCallback(verify).addCallback(lambda _: d2)

    def test_errouput(self):
        p = self.runCode("import sys\nfor i in range(100): sys.stderr.write('x' * 1000)")
        l = []
        d = stream.readStream(p.errStream, l.append)
        def verify(_):
            assertEquals("".join(l), ("x" * 1000) * 100)
        p.run()
        return d.addCallback(verify)

    def test_input(self):
        p = self.runCode("import sys\nsys.stdout.write(sys.stdin.read())",
                         "hello world")
        l = []
        d = stream.readStream(p.outStream, l.append)
        d2 = p.run()
        def verify(_):
            assertEquals("".join(l), "hello world")
            return d2
        return d.addCallback(verify)

    def test_badexit(self):
        p = self.runCode("raise ValueError")
        l = []
        from twisted.internet.error import ProcessTerminated
        def verify(_):
            assertEquals(l, [1])
            assert_(p.outStream.closed)
            assert_(p.errStream.closed)
        return p.run().addErrback(lambda _: _.trap(ProcessTerminated) and l.append(1)).addCallback(verify)

    def test_inputerror(self):
        p = self.runCode("import sys\nsys.stdout.write(sys.stdin.read())",
                         TestStreamer(["hello", defer.fail(ZeroDivisionError())]))
        l = []
        d = stream.readStream(p.outStream, l.append)
        d2 = p.run()
        def verify(_):
            assertEquals("".join(l), "hello")
            return d2
        return d.addCallback(verify).addCallback(lambda _: log.flushErrors(ZeroDivisionError))

    def test_processclosedinput(self):
        p = self.runCode("import sys; sys.stdout.write(sys.stdin.read(3));" +
                         "sys.stdin.close(); sys.stdout.write('def')",
                         "abc123")
        l = []
        d = stream.readStream(p.outStream, l.append)
        def verify(_):
            assertEquals("".join(l), "abcdef")
        d2 = p.run()
        return d.addCallback(verify).addCallback(lambda _: d2)


class AdapterTestCase(unittest.TestCase):

    def test_adapt(self):
        fName = self.mktemp()
        f = file(fName, "w")
        f.write("test")
        f.close()
        for i in ("test", buffer("test"), file(fName)):
            s = stream.IByteStream(i)
            assertEquals(str(s.read()), "test")
            assertEquals(s.read(), None)


class ReadStreamTestCase(unittest.TestCase):

    def test_pull(self):
        l = []
        s = TestStreamer(['abcd', defer.succeed('efgh'), 'ijkl'])
        return readStream(s, l.append).addCallback(
            lambda _: assertEquals(l, ["abcd", "efgh", "ijkl"]))
        
    def test_pullFailure(self):
        l = []
        s = TestStreamer(['abcd', defer.fail(RuntimeError()), 'ijkl'])
        def test(result):
            result.trap(RuntimeError)
            assertEquals(l, ["abcd"])
        return readStream(s, l.append).addErrback(test)
    
    def test_pullException(self):
        class Failer:
            def read(self): raise RuntimeError
        return readStream(Failer(), lambda _: None).addErrback(lambda _: _.trap(RuntimeError))

    def test_processingException(self):
        s = TestStreamer(['abcd', defer.succeed('efgh'), 'ijkl'])
        return readStream(s, lambda x: 1/0).addErrback(lambda _: _.trap(ZeroDivisionError))


class ProducerStreamTestCase(unittest.TestCase):

    def test_failfinish(self):
        p = stream.ProducerStream()
        p.write("hello")
        p.finish(RuntimeError())
        assertEquals(p.read(), "hello")
        d = p.read()
        l = []
        d.addErrback(lambda _: (l.append(1), _.trap(RuntimeError))).addCallback(
            lambda _: assertEquals(l, [1]))
        return d


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

    We can also create CompoundStream more easily like so:
    >>> s = CompoundStream(['hello', MemoryStream(' world')])
    >>> str(s.read())
    'hello'
    >>> str(s.read())
    ' world'
    
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

    Error handling works using Deferreds:
    >>> m = MemoryStream("after")
    >>> s = CompoundStream([TestStreamer([defer.fail(ZeroDivisionError())]), m])
    >>> l = []; x = s.read().addErrback(lambda _: l.append(1))
    >>> l
    [1]
    >>> s.length
    0
    >>> m.length # streams after the failed one got closed
    0

	"""


__doctests__ = ['twisted.web2.test.test_stream.CompoundStreamTest', 'twisted.web2.stream.generatorToStream']
# TODO: 
# CompoundStreamTest
# more tests for ProducerStreamTest
# StreamProducerTest
