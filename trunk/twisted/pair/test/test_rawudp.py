# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

#
from twisted.trial import unittest

from twisted.internet import protocol
from twisted.pair import rawudp

class MyProtocol(protocol.DatagramProtocol):
    def __init__(self, expecting):
        self.expecting = list(expecting)

    def datagramReceived(self, data, (host, port)):
        assert self.expecting, 'Got a packet when not expecting anymore.'
        expectData, expectHost, expectPort = self.expecting.pop(0)

        assert expectData == data, "Expected data %r, got %r" % (expectData, data)
        assert expectHost == host, "Expected host %r, got %r" % (expectHost, host)
        assert expectPort == port, "Expected port %d=0x%04x, got %d=0x%04x" % (expectPort, expectPort, port, port)

class RawUDPTestCase(unittest.TestCase):
    def testPacketParsing(self):
        proto = rawudp.RawUDPProtocol()
        p1 = MyProtocol([

            ('foobar', 'testHost', 0x43A2),

            ])
        proto.addProto(0xF00F, p1)

        proto.datagramReceived("\x43\xA2" #source
                               + "\xf0\x0f" #dest
                               + "\x00\x06" #len
                               + "\xDE\xAD" #check
                               + "foobar",
                               partial=0,
                               dest='dummy',
                               source='testHost',
                               protocol='dummy',
                               version='dummy',
                               ihl='dummy',
                               tos='dummy',
                               tot_len='dummy',
                               fragment_id='dummy',
                               fragment_offset='dummy',
                               dont_fragment='dummy',
                               more_fragments='dummy',
                               ttl='dummy',
                               )

        assert not p1.expecting, \
               'Should not expect any more packets, but still want %r' % p1.expecting

    def testMultiplePackets(self):
        proto = rawudp.RawUDPProtocol()
        p1 = MyProtocol([

            ('foobar', 'testHost', 0x43A2),
            ('quux', 'otherHost', 0x33FE),

            ])
        proto.addProto(0xF00F, p1)
        proto.datagramReceived("\x43\xA2" #source
                               + "\xf0\x0f" #dest
                               + "\x00\x06" #len
                               + "\xDE\xAD" #check
                               + "foobar",
                               partial=0,
                               dest='dummy',
                               source='testHost',
                               protocol='dummy',
                               version='dummy',
                               ihl='dummy',
                               tos='dummy',
                               tot_len='dummy',
                               fragment_id='dummy',
                               fragment_offset='dummy',
                               dont_fragment='dummy',
                               more_fragments='dummy',
                               ttl='dummy',
                               )
        proto.datagramReceived("\x33\xFE" #source
                               + "\xf0\x0f" #dest
                               + "\x00\x05" #len
                               + "\xDE\xAD" #check
                               + "quux",
                               partial=0,
                               dest='dummy',
                               source='otherHost',
                               protocol='dummy',
                               version='dummy',
                               ihl='dummy',
                               tos='dummy',
                               tot_len='dummy',
                               fragment_id='dummy',
                               fragment_offset='dummy',
                               dont_fragment='dummy',
                               more_fragments='dummy',
                               ttl='dummy',
                               )

        assert not p1.expecting, \
               'Should not expect any more packets, but still want %r' % p1.expecting


    def testMultipleSameProtos(self):
        proto = rawudp.RawUDPProtocol()
        p1 = MyProtocol([

            ('foobar', 'testHost', 0x43A2),

            ])

        p2 = MyProtocol([

            ('foobar', 'testHost', 0x43A2),

            ])

        proto.addProto(0xF00F, p1)
        proto.addProto(0xF00F, p2)

        proto.datagramReceived("\x43\xA2" #source
                               + "\xf0\x0f" #dest
                               + "\x00\x06" #len
                               + "\xDE\xAD" #check
                               + "foobar",
                               partial=0,
                               dest='dummy',
                               source='testHost',
                               protocol='dummy',
                               version='dummy',
                               ihl='dummy',
                               tos='dummy',
                               tot_len='dummy',
                               fragment_id='dummy',
                               fragment_offset='dummy',
                               dont_fragment='dummy',
                               more_fragments='dummy',
                               ttl='dummy',
                               )

        assert not p1.expecting, \
               'Should not expect any more packets, but still want %r' % p1.expecting
        assert not p2.expecting, \
               'Should not expect any more packets, but still want %r' % p2.expecting

    def testWrongProtoNotSeen(self):
        proto = rawudp.RawUDPProtocol()
        p1 = MyProtocol([])
        proto.addProto(1, p1)

        proto.datagramReceived("\x43\xA2" #source
                               + "\xf0\x0f" #dest
                               + "\x00\x06" #len
                               + "\xDE\xAD" #check
                               + "foobar",
                               partial=0,
                               dest='dummy',
                               source='testHost',
                               protocol='dummy',
                               version='dummy',
                               ihl='dummy',
                               tos='dummy',
                               tot_len='dummy',
                               fragment_id='dummy',
                               fragment_offset='dummy',
                               dont_fragment='dummy',
                               more_fragments='dummy',
                               ttl='dummy',
                               )

    def testDemuxing(self):
        proto = rawudp.RawUDPProtocol()
        p1 = MyProtocol([

            ('foobar', 'testHost', 0x43A2),
            ('quux', 'otherHost', 0x33FE),

            ])
        proto.addProto(0xF00F, p1)

        p2 = MyProtocol([

            ('quux', 'otherHost', 0xA401),
            ('foobar', 'testHost', 0xA302),

            ])
        proto.addProto(0xB050, p2)

        proto.datagramReceived("\xA4\x01" #source
                               + "\xB0\x50" #dest
                               + "\x00\x05" #len
                               + "\xDE\xAD" #check
                               + "quux",
                               partial=0,
                               dest='dummy',
                               source='otherHost',
                               protocol='dummy',
                               version='dummy',
                               ihl='dummy',
                               tos='dummy',
                               tot_len='dummy',
                               fragment_id='dummy',
                               fragment_offset='dummy',
                               dont_fragment='dummy',
                               more_fragments='dummy',
                               ttl='dummy',
                               )
        proto.datagramReceived("\x43\xA2" #source
                               + "\xf0\x0f" #dest
                               + "\x00\x06" #len
                               + "\xDE\xAD" #check
                               + "foobar",
                               partial=0,
                               dest='dummy',
                               source='testHost',
                               protocol='dummy',
                               version='dummy',
                               ihl='dummy',
                               tos='dummy',
                               tot_len='dummy',
                               fragment_id='dummy',
                               fragment_offset='dummy',
                               dont_fragment='dummy',
                               more_fragments='dummy',
                               ttl='dummy',
                               )
        proto.datagramReceived("\x33\xFE" #source
                               + "\xf0\x0f" #dest
                               + "\x00\x05" #len
                               + "\xDE\xAD" #check
                               + "quux",
                               partial=0,
                               dest='dummy',
                               source='otherHost',
                               protocol='dummy',
                               version='dummy',
                               ihl='dummy',
                               tos='dummy',
                               tot_len='dummy',
                               fragment_id='dummy',
                               fragment_offset='dummy',
                               dont_fragment='dummy',
                               more_fragments='dummy',
                               ttl='dummy',
                               )
        proto.datagramReceived("\xA3\x02" #source
                               + "\xB0\x50" #dest
                               + "\x00\x06" #len
                               + "\xDE\xAD" #check
                               + "foobar",
                               partial=0,
                               dest='dummy',
                               source='testHost',
                               protocol='dummy',
                               version='dummy',
                               ihl='dummy',
                               tos='dummy',
                               tot_len='dummy',
                               fragment_id='dummy',
                               fragment_offset='dummy',
                               dont_fragment='dummy',
                               more_fragments='dummy',
                               ttl='dummy',
                               )

        assert not p1.expecting, \
               'Should not expect any more packets, but still want %r' % p1.expecting
        assert not p2.expecting, \
               'Should not expect any more packets, but still want %r' % p2.expecting

    def testAddingBadProtos_WrongLevel(self):
        """Adding a wrong level protocol raises an exception."""
        e = rawudp.RawUDPProtocol()
        try:
            e.addProto(42, "silliness")
        except TypeError, e:
            if e.args == ('Added protocol must be an instance of DatagramProtocol',):
                pass
            else:
                raise
        else:
            raise AssertionError, 'addProto must raise an exception for bad protocols'


    def testAddingBadProtos_TooSmall(self):
        """Adding a protocol with a negative number raises an exception."""
        e = rawudp.RawUDPProtocol()
        try:
            e.addProto(-1, protocol.DatagramProtocol())
        except TypeError, e:
            if e.args == ('Added protocol must be positive or zero',):
                pass
            else:
                raise
        else:
            raise AssertionError, 'addProto must raise an exception for bad protocols'


    def testAddingBadProtos_TooBig(self):
        """Adding a protocol with a number >=2**16 raises an exception."""
        e = rawudp.RawUDPProtocol()
        try:
            e.addProto(2**16, protocol.DatagramProtocol())
        except TypeError, e:
            if e.args == ('Added protocol must fit in 16 bits',):
                pass
            else:
                raise
        else:
            raise AssertionError, 'addProto must raise an exception for bad protocols'

    def testAddingBadProtos_TooBig2(self):
        """Adding a protocol with a number >=2**16 raises an exception."""
        e = rawudp.RawUDPProtocol()
        try:
            e.addProto(2**16+1, protocol.DatagramProtocol())
        except TypeError, e:
            if e.args == ('Added protocol must fit in 16 bits',):
                pass
            else:
                raise
        else:
            raise AssertionError, 'addProto must raise an exception for bad protocols'
