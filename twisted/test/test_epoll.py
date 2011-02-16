# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for epoll wrapper.
"""

import socket, errno, time

from twisted.trial import unittest
from twisted.python.util import untilConcludes

try:
    from twisted.python import _epoll
except ImportError:
    _epoll = None


class EPoll(unittest.TestCase):
    """
    Tests for the low-level epoll bindings.
    """
    def setUp(self):
        """
        Create a listening server port and a list with which to keep track
        of created sockets.
        """
        self.serverSocket = socket.socket()
        self.serverSocket.bind(('127.0.0.1', 0))
        self.serverSocket.listen(1)
        self.connections = [self.serverSocket]


    def tearDown(self):
        """
        Close any sockets which were opened by the test.
        """
        for skt in self.connections:
            skt.close()


    def _connectedPair(self):
        """
        Return the two sockets which make up a new TCP connection.
        """
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


    def test_create(self):
        """
        Test the creation of an epoll object.
        """
        try:
            p = _epoll.epoll(16)
        except OSError, e:
            raise unittest.FailTest(str(e))
        else:
            p.close()


    def test_badCreate(self):
        """
        Test that attempting to create an epoll object with some random
        objects raises a TypeError.
        """
        self.assertRaises(TypeError, _epoll.epoll, 1, 2, 3)
        self.assertRaises(TypeError, _epoll.epoll, 'foo')
        self.assertRaises(TypeError, _epoll.epoll, None)
        self.assertRaises(TypeError, _epoll.epoll, ())
        self.assertRaises(TypeError, _epoll.epoll, ['foo'])
        self.assertRaises(TypeError, _epoll.epoll, {})
        self.assertRaises(TypeError, _epoll.epoll)


    def test_add(self):
        """
        Test adding a socket to an epoll object.
        """
        server, client = self._connectedPair()

        p = _epoll.epoll(2)
        try:
            p._control(_epoll.CTL_ADD, server.fileno(), _epoll.IN | _epoll.OUT)
            p._control(_epoll.CTL_ADD, client.fileno(), _epoll.IN | _epoll.OUT)
        finally:
            p.close()


    def test_controlAndWait(self):
        """
        Test waiting on an epoll object which has had some sockets added to
        it.
        """
        client, server = self._connectedPair()

        p = _epoll.epoll(16)
        p._control(_epoll.CTL_ADD, client.fileno(), _epoll.IN | _epoll.OUT |
                   _epoll.ET)
        p._control(_epoll.CTL_ADD, server.fileno(), _epoll.IN | _epoll.OUT |
                   _epoll.ET)

        now = time.time()
        events = untilConcludes(p.wait, 4, 1000)
        then = time.time()
        self.failIf(then - now > 0.01)

        events.sort()
        expected = [(client.fileno(), _epoll.OUT),
                    (server.fileno(), _epoll.OUT)]
        expected.sort()

        self.assertEquals(events, expected)

        now = time.time()
        events = untilConcludes(p.wait, 4, 200)
        then = time.time()
        self.failUnless(then - now > 0.1)
        self.failIf(events)

        client.send("Hello!")
        server.send("world!!!")

        now = time.time()
        events = untilConcludes(p.wait, 4, 1000)
        then = time.time()
        self.failIf(then - now > 0.01)

        events.sort()
        expected = [(client.fileno(), _epoll.IN | _epoll.OUT),
                    (server.fileno(), _epoll.IN | _epoll.OUT)]
        expected.sort()

        self.assertEquals(events, expected)

if _epoll is None:
    EPoll.skip = "_epoll module unavailable"
else:
    try:
        e = _epoll.epoll(16)
    except IOError, exc:
        if exc.errno == errno.ENOSYS:
            del exc
            EPoll.skip = "epoll support missing from platform"
        else:
            raise
    else:
        e.close()
        del e
