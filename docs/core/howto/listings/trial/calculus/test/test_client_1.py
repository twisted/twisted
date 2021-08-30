from calculus.client_1 import RemoteCalculationClient

from twisted.test import proto_helpers
from twisted.trial import unittest


class ClientCalculationTestCase(unittest.TestCase):
    def setUp(self):
        self.tr = proto_helpers.StringTransport()
        self.proto = RemoteCalculationClient()
        self.proto.makeConnection(self.tr)

    def _test(self, operation, a, b, expected):
        d = getattr(self.proto, operation)(a, b)
        self.assertEqual(self.tr.value(), f"{operation} {a} {b}\r\n".encode())
        self.tr.clear()
        d.addCallback(self.assertEqual, expected)
        self.proto.dataReceived(
            "{}\r\n".format(
                expected,
            ).encode("utf-8")
        )
        return d

    def test_add(self):
        return self._test("add", 7, 6, 13)

    def test_subtract(self):
        return self._test("subtract", 82, 78, 4)

    def test_multiply(self):
        return self._test("multiply", 2, 8, 16)

    def test_divide(self):
        return self._test("divide", 14, 3, 4)
