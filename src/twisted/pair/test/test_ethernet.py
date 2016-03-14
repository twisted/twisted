# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.
from twisted.trial import unittest

from twisted.python import components
from twisted.pair import ethernet, raw
from zope.interface import implements


class MyProtocol:
    implements(raw.IRawPacketProtocol)

    def __init__(self, expecting):
        self.expecting = list(expecting)

    def datagramReceived(self, data, **kw):
        assert self.expecting, 'Got a packet when not expecting anymore.'
        expect = self.expecting.pop(0)
        assert expect == (data, kw), \
               "Expected %r, got %r" % (
            expect, (data, kw),
            )

class EthernetTests(unittest.TestCase):
    def testPacketParsing(self):
        proto = ethernet.EthernetProtocol()
        p1 = MyProtocol([

            ('foobar', {
            'partial': 0,
            'dest': "123456",
            'source': "987654",
            'protocol': 0x0800,
            }),

            ])
        proto.addProto(0x0800, p1)

        proto.datagramReceived("123456987654\x08\x00foobar",
                               partial=0)

        assert not p1.expecting, \
               'Should not expect any more packets, but still want %r' % p1.expecting


    def testMultiplePackets(self):
        proto = ethernet.EthernetProtocol()
        p1 = MyProtocol([

            ('foobar', {
            'partial': 0,
            'dest': "123456",
            'source': "987654",
            'protocol': 0x0800,
            }),

            ('quux', {
            'partial': 1,
            'dest': "012345",
            'source': "abcdef",
            'protocol': 0x0800,
            }),

            ])
        proto.addProto(0x0800, p1)

        proto.datagramReceived("123456987654\x08\x00foobar",
                               partial=0)
        proto.datagramReceived("012345abcdef\x08\x00quux",
                               partial=1)

        assert not p1.expecting, \
               'Should not expect any more packets, but still want %r' % p1.expecting


    def testMultipleSameProtos(self):
        proto = ethernet.EthernetProtocol()
        p1 = MyProtocol([

            ('foobar', {
            'partial': 0,
            'dest': "123456",
            'source': "987654",
            'protocol': 0x0800,
            }),

            ])

        p2 = MyProtocol([

            ('foobar', {
            'partial': 0,
            'dest': "123456",
            'source': "987654",
            'protocol': 0x0800,
            }),

            ])

        proto.addProto(0x0800, p1)
        proto.addProto(0x0800, p2)

        proto.datagramReceived("123456987654\x08\x00foobar",
                               partial=0)

        assert not p1.expecting, \
               'Should not expect any more packets, but still want %r' % p1.expecting
        assert not p2.expecting, \
               'Should not expect any more packets, but still want %r' % p2.expecting

    def testWrongProtoNotSeen(self):
        proto = ethernet.EthernetProtocol()
        p1 = MyProtocol([])
        proto.addProto(0x0801, p1)

        proto.datagramReceived("123456987654\x08\x00foobar",
                               partial=0)
        proto.datagramReceived("012345abcdef\x08\x00quux",
                               partial=1)

    def testDemuxing(self):
        proto = ethernet.EthernetProtocol()
        p1 = MyProtocol([

            ('foobar', {
            'partial': 0,
            'dest': "123456",
            'source': "987654",
            'protocol': 0x0800,
            }),

            ('quux', {
            'partial': 1,
            'dest': "012345",
            'source': "abcdef",
            'protocol': 0x0800,
            }),

            ])
        proto.addProto(0x0800, p1)

        p2 = MyProtocol([

            ('quux', {
            'partial': 1,
            'dest': "012345",
            'source': "abcdef",
            'protocol': 0x0806,
            }),

            ('foobar', {
            'partial': 0,
            'dest': "123456",
            'source': "987654",
            'protocol': 0x0806,
            }),

            ])
        proto.addProto(0x0806, p2)

        proto.datagramReceived("123456987654\x08\x00foobar",
                               partial=0)
        proto.datagramReceived("012345abcdef\x08\x06quux",
                               partial=1)
        proto.datagramReceived("123456987654\x08\x06foobar",
                               partial=0)
        proto.datagramReceived("012345abcdef\x08\x00quux",
                               partial=1)

        assert not p1.expecting, \
               'Should not expect any more packets, but still want %r' % p1.expecting
        assert not p2.expecting, \
               'Should not expect any more packets, but still want %r' % p2.expecting

    def testAddingBadProtos_WrongLevel(self):
        """Adding a wrong level protocol raises an exception."""
        e = ethernet.EthernetProtocol()
        try:
            e.addProto(42, "silliness")
        except components.CannotAdapt:
            pass
        else:
            raise AssertionError, 'addProto must raise an exception for bad protocols'


    def testAddingBadProtos_TooSmall(self):
        """Adding a protocol with a negative number raises an exception."""
        e = ethernet.EthernetProtocol()
        try:
            e.addProto(-1, MyProtocol([]))
        except TypeError, e:
            if e.args == ('Added protocol must be positive or zero',):
                pass
            else:
                raise
        else:
            raise AssertionError, 'addProto must raise an exception for bad protocols'


    def testAddingBadProtos_TooBig(self):
        """Adding a protocol with a number >=2**16 raises an exception."""
        e = ethernet.EthernetProtocol()
        try:
            e.addProto(2**16, MyProtocol([]))
        except TypeError, e:
            if e.args == ('Added protocol must fit in 16 bits',):
                pass
            else:
                raise
        else:
            raise AssertionError, 'addProto must raise an exception for bad protocols'

    def testAddingBadProtos_TooBig2(self):
        """Adding a protocol with a number >=2**16 raises an exception."""
        e = ethernet.EthernetProtocol()
        try:
            e.addProto(2**16+1, MyProtocol([]))
        except TypeError, e:
            if e.args == ('Added protocol must fit in 16 bits',):
                pass
            else:
                raise
        else:
            raise AssertionError, 'addProto must raise an exception for bad protocols'
