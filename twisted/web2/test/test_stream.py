from twisted.trial import unittest
from zope.interface import Interface, Attribute, implements
from twisted.trial.assertions import *
import tempfile

from twisted.web2 import stream

text = '1234567890'
class SimpleStreamSplitTests:
    def test_split(self):
        for point in range(11):
            s = self.makeStream(0)
            a,b = s.split(point)
            if point > 0:
                assertEquals(str(a.read()), text[:point])
            assertEquals(a.read(), None)
            if point < 10:
                assertEquals(str(b.read()), text[point:])
            assertEquals(b.read(), None)

        for point in range(7):
            s = self.makeStream(2, 6)
            assertEquals(s.length, 6)
            a,b = s.split(point)
            if point > 0:
                assertEquals(str(a.read()), text[2:point+2])
            assertEquals(a.read(), None)
            if point < 6:
                assertEquals(str(b.read()), text[point+2:8])
            assertEquals(b.read(), None)

    
class FileStreamTest(SimpleStreamSplitTests, unittest.TestCase):
    def makeStream(self, *args, **kw):
        return stream.FileStream(self.f, *args, **kw)
    
    def setUpClass(self):
        f = tempfile.TemporaryFile('w+')
        f.write(text)
        f.seek(0, 0)
        self.f = f

    def test_close(self):
        s = self.makeStream()
        s.close()

        assertEquals(s.length, 0)
        # Make sure close doesn't close file
        # would raise exception if f is closed
        self.f.seek(0, 0)
        
    def test_read(self):
        s = self.makeStream()
        assertEquals(s.length, None)
        assertEquals(str(s.read()), text)
        assertEquals(s.read(), None)

        s = self.makeStream(0)
        s.CHUNK_SIZE = 6
        assertEquals(s.length, None)
        assertEquals(str(s.read()), text[0:6])
        assertEquals(str(s.read()), text[6:10])
        assertEquals(s.read(), None)

        s = self.makeStream(0)
        s.CHUNK_SIZE = 5
        assertEquals(s.length, None)
        assertEquals(str(s.read()), text[0:5])
        assertEquals(str(s.read()), text[5:10])
        assertEquals(s.read(), None)

        s = self.makeStream(0, 4)
        assertEquals(s.length, 4)
        assertEquals(str(s.read()), text[0:4])
        assertEquals(s.read(), None)
        assertEquals(s.length, 0)

        s = self.makeStream(4, 6)
        assertEquals(s.length, 6)
        assertEquals(str(s.read()), text[4:10])
        assertEquals(s.read(), None)
        assertEquals(s.length, 0)
        
        s = self.makeStream(0, 20)
        assertEquals(s.length, 20)
        assertEquals(str(s.read()), text)
        assertRaises(RuntimeError, s.read) # ran out of data
        
        
            
class MemoryStreamTest(SimpleStreamSplitTests, unittest.TestCase):
    def makeStream(self, *args, **kw):
        return stream.MemoryStream(text, *args, **kw)

    def test_close(self):
        s = self.makeStream()
        s.close()
        assertEquals(s.length, 0)

    def test_read(self):
        s = self.makeStream()
        assertEquals(s.length, 10)
        assertEquals(str(s.read()), text)
        assertEquals(s.read(), None)

        s = self.makeStream(0, 4)
        assertEquals(s.length, 4)
        assertEquals(str(s.read()), text[0:4])
        assertEquals(s.read(), None)
        assertEquals(s.length, 0)

        s = self.makeStream(4, 6)
        assertEquals(s.length, 6)
        assertEquals(str(s.read()), text[4:10])
        assertEquals(s.read(), None)
        assertEquals(s.length, 0)
        
        assertRaises(ValueError, self.makeStream, 0, 20)


#class FallbackSplitTest(unittest.TestCase):
#    def test_split(self):
#        fallbackSplit()
