
"""
Tests for framing protocols.
"""
from twisted.tubes.framing import stringsToNetstrings

from twisted.tubes.test.util import FakeFount
from twisted.tubes.test.util import FakeDrain
from twisted.tubes.tube import cascade

from twisted.tubes.tube import Pump

from twisted.tubes.framing import netstringsToStrings
from twisted.tubes.framing import bytesToLines
from twisted.tubes.framing import linesToBytes

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
        ff.flowTo(cascade(stringsToNetstrings())).flowTo(fd)
        ff.drain.receive("hello")
        self.assertEquals(fd.received, ["{len:d}:{data:s},".format(
            len=len("hello"), data="hello"
        )])


    def test_stringsToNetstrings(self):
        """
        L{stringsToNetstrings} works on subsequent inputs as well.
        """
        ff = FakeFount()
        fd = FakeDrain()
        ff.flowTo(cascade(stringsToNetstrings())).flowTo(fd)
        ff.drain.receive("hello")
        ff.drain.receive("world")
        self.assertEquals(b"".join(fd.received), 
            "{len:d}:{data:s},{len2:d}:{data2:s},".format(
            len=len("hello"), data="hello",
            len2=len("world"), data2="world",
        ))


    def test_netstringToString(self):
        """
        Length prefix is stripped off.
        """
        ff = FakeFount()
        fd = FakeDrain()
        ff.flowTo(cascade(netstringsToStrings())).flowTo(fd)
        ff.drain.receive("1:x,2:yz,3:")
        self.assertEquals(fd.received, ["x", "yz"])



class LineTests(TestCase):
    """
    Tests for parsing delimited data ("lines").
    """

    def test_stringToLines(self):
        """
        A line is something delimited by CRLF.
        """
        ff = FakeFount()
        fd = FakeDrain()
        ff.flowTo(cascade(bytesToLines())).flowTo(fd)
        ff.drain.receive(b"alpha\r\nbeta\r\ngamma")
        self.assertEquals(fd.received, [b"alpha", b"beta"])


    def test_linesToStrings(self):
        """
        Writing out lines delimits them, with the delimiter.
        """
        ff = FakeFount()
        fd = FakeDrain()
        ff.flowTo(cascade(linesToBytes())).flowTo(fd)
        ff.drain.receive(b"hello")
        ff.drain.receive(b"world")
        self.assertEquals(b"".join(fd.received), b"hello\r\nworld\r\n")


    def test_rawMode(self):
        """
        You should be able to have some lines, and then some bytes, and then
        some lines.
        """

        lines = bytesToLines()

        class Switcher(Pump):
            def received(self, line):
                splitted = line.split(" ", 1)
                if splitted[0] == 'switch':
                    length = int(splitted[1])
                    # XXX document downstream
                    lines.tube.switch(cascade(Switchee(length),
                                              self.tube.downstream))
                return ()

        class Switchee(Pump):
            datums = []
            def __init__(self, length):
                self.length = length
            def received(self, data):
                self.datums.append(data)
        
        ff = FakeFount()
        cc = cascade(lines, Switcher())
        fd = FakeDrain()
        ff.flowTo(cc).flowTo(fd)
        ff.drain.receive("hello\r\nworld\r\nswitch 10\r\nabcde\r\nfgh"
                         # + '\r\nagain\r\n'
                         )
        self.assertEquals("".join(Switchee.datums), "abcde\r\nfgh")



