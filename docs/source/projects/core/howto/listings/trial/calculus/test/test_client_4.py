from calculus.client_3 import RemoteCalculationClient, ClientTimeoutError

from twisted.internet import task
from twisted.trial import unittest
from twisted.test import proto_helpers



class ClientCalculationTestCase(unittest.TestCase):
    def setUp(self):
        self.tr = proto_helpers.StringTransportWithDisconnection()
        self.clock = task.Clock()
        self.proto = RemoteCalculationClient()
        self.tr.protocol = self.proto
        self.proto.callLater = self.clock.callLater
        self.proto.makeConnection(self.tr)


    def _test(self, operation, a, b, expected):
        d = getattr(self.proto, operation)(a, b)
        self.assertEqual(self.tr.value(), '%s %d %d\r\n' % (operation, a, b))
        self.tr.clear()
        self.proto.dataReceived("%d\r\n" % (expected,))
        self.assertEqual(expected, self.successResultOf(d))


    def test_add(self):
        self._test('add', 7, 6, 13)


    def test_subtract(self):
        self._test('subtract', 82, 78, 4)


    def test_multiply(self):
        self._test('multiply', 2, 8, 16)


    def test_divide(self):
        self._test('divide', 14, 3, 4)


    def test_timeout(self):
        d = self.proto.add(9, 4)
        self.assertEqual(self.tr.value(), 'add 9 4\r\n')
        self.clock.advance(self.proto.timeOut)
        self.failureResultOf(d).trap(ClientTimeoutError)


    def test_timeoutConnectionLost(self):
        called = []
        def lost(arg):
            called.append(True)
        self.proto.connectionLost = lost

        d = self.proto.add(9, 4)
        self.assertEqual(self.tr.value(), 'add 9 4\r\n')
        self.clock.advance(self.proto.timeOut)

        def check(ignore):
            self.assertEqual(called, [True])
        self.failureResultOf(d).trap(ClientTimeoutError)
        self.assertEqual(called, [True])
