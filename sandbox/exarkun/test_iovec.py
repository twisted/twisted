# -*- coding: Latin-1 -*-

import iovec

import tempfile

from twisted.trial import unittest

class IOVectorTestCase(unittest.TestCase):
    def testAllocDealloc(self):
        v = iovec.IOVectorType()
        del v
    
    def testAdd(self):
        v = iovec.IOVectorType()
        for s in [chr(i + ord('a')) * i for i in range(1, 11)]:
            v.add(s)

        
    def testWriteToFile(self):
        v = iovec.IOVectorType()
        for s in [chr(i + ord('a')) * i for i in range(1, 11)]:
            v.add(s)
        
        f = tempfile.TemporaryFile('w+')
        self.assertEquals(55, v.write(f))
        
        f.seek(0, 0)
        self.assertEquals(f.read(), ''.join([chr(i + ord('a')) * i for i in range(1, 11)]))

    def testWriteToFileDescriptor(self):
        v = iovec.IOVectorType()
        for s in [chr(i + ord('a')) * i for i in range(1, 11)]:
            v.add(s)
        f = tempfile.TemporaryFile('w+')
        
        self.assertEquals(55, v.write(f.fileno()))
        
        f.seek(0, 0)
        self.assertEquals(f.read(), ''.join([chr(i + ord('a')) * i for i in range(1, 11)]))

    def testIllegalWrites(self):
        v = iovec.IOVectorType()
        for s in ['x' * i for i in range(100)]:
            v.add(s)

        class Pah:
            def fileno(self):
                return 'a string'

        self.assertRaises(iovec.error, v.write, Pah())
        
        del Pah.fileno
        self.assertRaises(AttributeError, v.write, Pah())
        self.assertRaises(AttributeError, v.write, 'a string')
