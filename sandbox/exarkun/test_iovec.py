# -*- coding: Latin-1 -*-

import iovec

import tempfile
import socket

from twisted.trial import unittest

class IOVectorTestCase(unittest.TestCase):
    def testAllocDealloc(self):
        v = iovec.iovec()
        del v
    
    def testAdd(self):
        v = iovec.iovec()
        for s in [chr(i + ord('a')) * i for i in range(1, 11)]:
            v.add(s)

        
    def testWriteToFile(self):
        v = iovec.iovec()
        for s in [chr(i + ord('a')) * i for i in range(1, 11)]:
            v.add(s)
        
        f = tempfile.TemporaryFile('w+')
        self.assertEquals(55, v.write(f))
        
        f.seek(0, 0)
        self.assertEquals(f.read(), ''.join([chr(i + ord('a')) * i for i in range(1, 11)]))

    def testWriteToFileDescriptor(self):
        v = iovec.iovec()
        for s in [chr(i + ord('a')) * i for i in range(1, 11)]:
            v.add(s)
        f = tempfile.TemporaryFile('w+')
        
        self.assertEquals(55, v.write(f.fileno()))
        
        f.seek(0, 0)
        self.assertEquals(f.read(), ''.join([chr(i + ord('a')) * i for i in range(1, 11)]))

    def testIllegalWrites(self):
        v = iovec.iovec()
        for s in ['x' * i for i in range(100)]:
            v.add(s)

        class Pah:
            def fileno(self):
                return 'a string'

        self.assertRaises(iovec.error, v.write, Pah())
        
        del Pah.fileno
        self.assertRaises(AttributeError, v.write, Pah())
        self.assertRaises(AttributeError, v.write, 'a string')

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
            v.add(chr(ord('a') + i % 26) * i)
        
        written = v.write(client)
        # print
        # print written
        # print
