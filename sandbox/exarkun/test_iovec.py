# -*- coding: Latin-1 -*-

import iovec
import time

import tempfile
import socket
from cStringIO import StringIO

from twisted.trial import unittest

def arith(x):
    return (x * (x + 1)) // 2

HARD_CHUNK_SIZE = 37

class IOVec(unittest.TestCase):
    def testNotASequence(self):
        self.assertRaises(iovec.error, iovec.writev, 0, 10)
        self.assertRaises(iovec.error, iovec.writev, 0, 10.0)
        self.assertRaises(iovec.error, iovec.writev, 0, 10j)
        self.assertRaises(iovec.error, iovec.writev, 0, {})
        self.assertRaises(iovec.error, iovec.writev, 0, iovec.writev)

    def testNotASequenceOfStrings(self):
        self.assertRaises(TypeError, iovec.writev, 0, ["0", 1, 2])
        self.assertRaises(TypeError, iovec.writev, 0, [0, "1", 2])
        self.assertRaises(TypeError, iovec.writev, 0, [0, 1, "2"])
        self.assertRaises(TypeError, iovec.writev, 0, [0, 1, 2])

    def testWriteToFileDescriptor(self):
        s = [chr(i + ord('a')) * i for i in range(1, HARD_CHUNK_SIZE+1)]
        f = tempfile.TemporaryFile('w+')
        self.assertEquals(arith(HARD_CHUNK_SIZE), iovec.writev(f.fileno(), s)[0])
        
        f.seek(0, 0)
        self.assertEquals(f.read(), ''.join(s))

    def testIncompleteWrites(self):
        server = socket.socket()
        server.setblocking(0)
        server.bind(('', 0))
        server.listen(5)
        
        port = server.getsockname()[1]
        
        client = socket.socket()
        client.setblocking(False)
        try:
            client.connect(('', port))
        except:
            pass
        
        s, _ = server.accept()
        s.setblocking(False)

        bytes = ''
        v = [chr(ord('a') + i % 26) * i for i in range(1000, 2000)]
        shouldGet = ''.join(v)

        while v:
            written, errno = iovec.writev(client.fileno(), v)
            if written == -1:
                if errno == errno.EINTR:
                    continue
                else:
                    break
            while True:
                try:
                    bytes += s.recv(written * 10)
                except:
                    break
            
            while v and written >= len(v[0]):
                written -= len(v[0])
                del v[0]
            
            if written > 0:
                v[0] = v[0][written:]
                written = 0
            
        while True:
            try:
                bytes += s.recv(1024 * 1024)
            except Exception, e:
                break         

        # file('first', 'w').write('\n'.join(splitup(bytes)))
        # file('second', 'w').write('\n'.join(splitup(shouldGet)))
        
        self.assertEquals(len(bytes), len(shouldGet))
        self.assertEquals(bytes, shouldGet)

def splitup(s):
    for i in range(0, len(s) + 80, 80):
        yield s[i:i+80]
