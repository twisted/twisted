
import sys, os, socket, errno, time

from twisted.trial import unittest

import _epoll

class EPoll(unittest.TestCase):
    def setUpClass(self):
        port = socket.socket()
        port.bind(('127.0.0.1', 0))
        port.listen(1)

        self.serverSocket = port
    
    def setUp(self):
        self.connections = []
    
    def tearDown(self):
        for skt in self.connections:
            skt.close()
    
    def tearDownClass(self):
        self.serverSocket.close()
    
    def _connectedPair(self):
        client = socket.socket()
        client.setblocking(False)
        try:
            client.connect(('127.0.0.1', self.serverSocket.getsockname()[1]))
        except socket.error, e:
            self.assertEquals(e.args[0], errno.EINPROGRESS)
        else:
            raise unittest.FailTest("Connect should have raised EINPROGRESS")
        server, addr = self.serverSocket.accept()
        
        self.connections.extend((client, server))
        return client, server

    def testCreate(self):
        try:
            p = _epoll.epoll(16)
        except OSError, e:
            raise unittest.FailTest(str(e))
        else:
            p.close()

    def testBadCreate(self):
        self.assertRaises(TypeError, _epoll.epoll, 1, 2, 3)
        self.assertRaises(TypeError, _epoll.epoll, 'foo')
        self.assertRaises(TypeError, _epoll.epoll, None)
        self.assertRaises(TypeError, _epoll.epoll, ())
        self.assertRaises(TypeError, _epoll.epoll, ['foo'])
        self.assertRaises(TypeError, _epoll.epoll, {})
        self.assertRaises(TypeError, _epoll.epoll)

    def testAdd(self):
        server, client = self._connectedPair()

        p = _epoll.epoll(2)
        try:
            p.add(server.fileno(), _epoll.IN | _epoll.OUT)
            p.add(client.fileno(), _epoll.IN | _epoll.OUT)
        finally:
            p.close()

    def testControlAndWait(self):
        client, server = self._connectedPair()

        p = _epoll.epoll(16)
        p.add(client.fileno(), _epoll.IN | _epoll.OUT | _epoll.ET)
        p.add(server.fileno(), _epoll.IN | _epoll.OUT | _epoll.ET)

        now = time.time()
        events = p.wait(4, 1000)
        then = time.time()
        self.failIf(then - now > 0.01)
        
        events.sort()
        expected = [(client.fileno(), _epoll.OUT),
                    (server.fileno(), _epoll.OUT)]
        expected.sort()
        
        self.assertEquals(events, expected)

        now = time.time()
        events = p.wait(4, 200)
        then = time.time()
        self.failUnless(then - now > 0.1)
        self.failIf(events)

        client.send("Hello!")
        server.send("world!!!")

        now = time.time()
        events = p.wait(4, 1000)
        then = time.time()
        self.failIf(then - now > 0.01)
        
        events.sort()
        expected = [(client.fileno(), _epoll.IN | _epoll.OUT),
                    (server.fileno(), _epoll.IN | _epoll.OUT)]
        expected.sort()

        self.assertEquals(events, expected)
