# -*- coding: Latin-1 -*-

import iovec

import tempfile
import socket
from cStringIO import StringIO

from twisted.trial import unittest

def arith(x):
    return (x * (x + 1)) // 2

HARD_CHUNK_SIZE = 37

class IOVectorTestCase(unittest.TestCase):
    def testAllocDealloc(self):
        v = iovec.iovec()
        del v
    
    def testAppend(self):
        v = iovec.iovec()
        for s in [chr(i + ord('a')) * i for i in range(1, HARD_CHUNK_SIZE+1)]:
            v.append(s)
        self.assertEquals(arith(HARD_CHUNK_SIZE), v.bytes)

    def testExtend(self):
        v = iovec.iovec()
        v.extend([chr(i + ord('a')) * i for i in range(1, HARD_CHUNK_SIZE+1)])
        self.assertEquals(arith(HARD_CHUNK_SIZE), v.bytes)
        
    def testWriteToFile(self):
        v = iovec.iovec()
        for s in [chr(i + ord('a')) * i for i in range(1, HARD_CHUNK_SIZE+1)]:
            v.append(s)

        self.assertEquals(arith(HARD_CHUNK_SIZE), v.bytes)
        f = tempfile.TemporaryFile('w+')
        self.assertEquals(arith(HARD_CHUNK_SIZE), v.write(f))
        self.assertEquals(0, v.bytes)
        
        f.seek(0, 0)
        self.assertEquals(f.read(), ''.join([chr(i + ord('a')) * i for i in range(1, HARD_CHUNK_SIZE+1)]))

    def testWriteToFileDescriptor(self):
        v = iovec.iovec()
        for s in [chr(i + ord('a')) * i for i in range(1, HARD_CHUNK_SIZE+1)]:
            v.append(s)
        self.assertEquals(arith(HARD_CHUNK_SIZE), v.bytes)
        f = tempfile.TemporaryFile('w+')
        
        self.assertEquals(arith(HARD_CHUNK_SIZE), v.write(f.fileno()))
        
        f.seek(0, 0)
        self.assertEquals(f.read(), ''.join([chr(i + ord('a')) * i for i in range(1, HARD_CHUNK_SIZE+1)]))

    def testIllegalWrites(self):
        v = iovec.iovec()
        for s in ['x' * i for i in range(1, 101)]:
            v.append(s)
        self.assertEquals(v.bytes, arith(100))

        class Pah:
            def fileno(self):
                return 'a string'

        self.assertRaises(iovec.error, v.write, Pah())
        
        del Pah.fileno
        self.assertRaises(AttributeError, v.write, Pah())
        self.assertRaises(AttributeError, v.write, 'a string')
        self.assertEquals(v.bytes, arith(100))

    def testIncompleteWrites(self):
        server = socket.socket()
        server.setblocking(0)
        server.bind(('', 0))
        server.listen(5)
        
        port = server.getsockname()[1]
        
        client = socket.socket()
        client.setblocking(0)
        try:
            client.connect(('', port))
        except:
            pass
        
        s, _ = server.accept()
        
        v = iovec.iovec()
        for i in range(1000, 2000):
            v.append(chr(ord('a') + i % 26) * i)
        self.assertEquals(v.bytes, arith(1999)-arith(999))
        
        written = v.write(client)
        # print
        # print written
        # print

    def testRead(self):
        v = iovec.iovec()
        v.extend(map(str, range(100)))
        expect = StringIO()
        expect.write(''.join(map(str, range(100))))
        expect.seek(0)
        self.assertEquals(v.read(120), expect.read(120))
        self.assertEquals(v.read(500), None)
        self.assertEquals(v.bytes, 70)
        self.assertEquals(v.read(69), expect.read(69))
        self.assertEquals(v.bytes, 1)
        self.assertEquals(v.read(2), None)
        self.assertEquals(v.read(1), expect.read(1))
        self.assertEquals(v.read(), expect.read())
        self.assertEquals(v.read(1), None)
        self.assertEquals(v.bytes, 0)
        v.extend(map(str, range(100)))
        expect.seek(0)
        self.assertEquals(v.read(120), expect.read(120))
        self.assertEquals(v.read(500), None)
        self.assertEquals(v.bytes, 70)
        self.assertEquals(v.read(69), expect.read(69))
        self.assertEquals(v.bytes, 1)
        self.assertEquals(v.read(2), None)
        self.assertEquals(v.read(1), expect.read(1))
        self.assertEquals(v.read(), expect.read())
        self.assertEquals(v.read(1), None)
        self.assertEquals(v.bytes, 0)
