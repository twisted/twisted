from twisted.test import test_protocols
from implicitstate import MyInt32StringReceiver

class TestInt32(test_protocols.TestMixin, MyInt32StringReceiver):
    MAX_LENGTH = 50

class Int32TestCase(test_protocols.Int32TestCase):
    protocol = TestInt32

