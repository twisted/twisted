
import os, socket, errno, time

from twisted.trial import unittest

import _epoll

class EPoll(unittest.TestCase):
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

    def testControlAndWait(self):
        port = socket.socket()
        port.bind(('127.0.0.1', 0))
        port.listen(1)

        client = socket.socket()
        client.setblocking(False)
        try:
            client.connect(('127.0.0.1', port.getsockname()[1]))
        except socket.error, e:
            self.assertEquals(e.args[0], errno.EINPROGRESS)
        else:
            raise unittest.FailTest("Connect should have raised EINPROGRESS")

        server, addr = port.accept()

        p = _epoll.epoll(16)
        p.control(_epoll.CTL_ADD, client.fileno(), _epoll.IN | _epoll.OUT)
        p.control(_epoll.CTL_ADD, server.fileno(), _epoll.IN | _epoll.OUT)

        now = time.time()
        events = p.wait(4, 1)
        then = time.time()
        self.failIf(then - now > 0.01)
        self.assertEquals(events, [(client.fileno(), _epoll.OUT),
                                   (server.fileno(), _epoll.OUT)])

        now = time.time()
        events = p.wait(4, 1)
        then = time.time()
        self.failUnless(then - now > 1)
        self.failIf(events)

        client.send("Hello!")
        server.send("world!!!")

        now = time.time()
        events = p.wait(4, 1)
        then = time.time()
        self.failIf(then - now > 0.01)
        self.assertEquals(events, [(client.fileno(), _epoll.IN | _epoll.OUT),
                                   (server.fileno(), _epoll.IN | _epoll.OUT)])

