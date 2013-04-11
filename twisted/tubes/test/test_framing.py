
"""
Tests for framing protocols.
"""
from twisted.tubes.framing import stringsToNetstrings

from twisted.tubes.test.util import FakeFount
from twisted.tubes.test.util import FakeDrain
from twisted.tubes.tube import Tube
from twisted.tubes.framing import netstringsToStrings
from twisted.trial.unittest import TestCase

class NetstringTests(TestCase):
    """
    Tests for parsing netstrings.
    """

    def test_stringToNetstring(self):
        """
        A byte-string is given a length prefix.
        """
        ff = FakeFount()
        fd = FakeDrain()
        ff.flowTo(Tube(stringsToNetstrings())).flowTo(fd)
        ff.drain.receive("hello")
        self.assertEquals(fd.received, ["{len:d}:{data:s},".format(
            len=len("hello"), data="hello"
        )])


    def test_netstringToString(self):
        """
        Length prefix is stripped off.
        """
        ff = FakeFount()
        fd = FakeDrain()
        ff.flowTo(Tube(netstringsToStrings())).flowTo(fd)
        ff.drain.receive("1:x,2:yz,3:")
        self.assertEquals(fd.received, ["x", "yz"])
