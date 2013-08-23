# test-case-name: twisted.names.test.test_dns
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for twisted.names.dns.
"""

from __future__ import division, absolute_import

from io import BytesIO

import struct

from zope.interface.verify import verifyClass

from twisted.python.failure import Failure
from twisted.internet import address, task
from twisted.internet.error import CannotListenError, ConnectionDone
from twisted.trial import unittest
from twisted.names import dns

from twisted.test import proto_helpers
from twisted.test.testutils import ComparisonTestsMixin

RECORD_TYPES = [
    dns.Record_NS, dns.Record_MD, dns.Record_MF, dns.Record_CNAME,
    dns.Record_MB, dns.Record_MG, dns.Record_MR, dns.Record_PTR,
    dns.Record_DNAME, dns.Record_A, dns.Record_SOA, dns.Record_NULL,
    dns.Record_WKS, dns.Record_SRV, dns.Record_AFSDB, dns.Record_RP,
    dns.Record_HINFO, dns.Record_MINFO, dns.Record_MX, dns.Record_TXT,
    dns.Record_AAAA, dns.Record_A6, dns.Record_NAPTR, dns.UnknownRecord,
    ]


class Ord2ByteTests(unittest.TestCase):
    """
    Tests for L{dns._ord2bytes}.
    """
    def test_ord2byte(self):
        """
        L{dns._ord2byte} accepts an integer and returns a byte string of length
        one with an ordinal value equal to the given integer.
        """
        self.assertEqual(b'\x10', dns._ord2bytes(0x10))



class Str2TimeTests(unittest.TestCase):
    """
    Tests for L{dns.str2name}.
    """
    def test_nonString(self):
        """
        When passed a non-string object, L{dns.str2name} returns it unmodified.
        """
        time = object()
        self.assertIdentical(time, dns.str2time(time))


    def test_seconds(self):
        """
        Passed a string giving a number of seconds, L{dns.str2time} returns the
        number of seconds represented.  For example, C{"10S"} represents C{10}
        seconds.
        """
        self.assertEqual(10, dns.str2time("10S"))


    def test_minutes(self):
        """
        Like C{test_seconds}, but for the C{"M"} suffix which multiplies the
        time value by C{60} (the number of seconds in a minute!).
        """
        self.assertEqual(2 * 60, dns.str2time("2M"))


    def test_hours(self):
        """
        Like C{test_seconds}, but for the C{"H"} suffix which multiplies the
        time value by C{3600}, the number of seconds in an hour.
        """
        self.assertEqual(3 * 3600, dns.str2time("3H"))


    def test_days(self):
        """
        Like L{test_seconds}, but for the C{"D"} suffix which multiplies the
        time value by C{86400}, the number of seconds in a day.
        """
        self.assertEqual(4 * 86400, dns.str2time("4D"))


    def test_weeks(self):
        """
        Like L{test_seconds}, but for the C{"W"} suffix which multiplies the
        time value by C{604800}, the number of seconds in a week.
        """
        self.assertEqual(5 * 604800, dns.str2time("5W"))


    def test_years(self):
        """
        Like L{test_seconds}, but for the C{"Y"} suffix which multiplies the
        time value by C{31536000}, the number of seconds in a year.
        """
        self.assertEqual(6 * 31536000, dns.str2time("6Y"))


    def test_invalidPrefix(self):
        """
        If a non-integer prefix is given, L{dns.str2time} raises L{ValueError}.
        """
        self.assertRaises(ValueError, dns.str2time, "fooS")



class NameTests(unittest.TestCase):
    """
    Tests for L{Name}, the representation of a single domain name with support
    for encoding into and decoding from DNS message format.
    """
    def test_nonStringName(self):
        """
        When constructed with a name which is neither C{bytes} nor C{str},
        L{Name} raises L{TypeError}.
        """
        self.assertRaises(TypeError, dns.Name, 123)
        self.assertRaises(TypeError, dns.Name, object())
        self.assertRaises(TypeError, dns.Name, [])


    def test_unicodeName(self):
        """
        L{dns.Name} automatically encodes unicode domain name using C{idna}
        encoding.
        """
        name = dns.Name(u'\u00e9chec.example.org')
        self.assertIsInstance(name.name, bytes)
        self.assertEqual(b'xn--chec-9oa.example.org', name.name)


    def test_decode(self):
        """
        L{Name.decode} populates the L{Name} instance with name information read
        from the file-like object passed to it.
        """
        n = dns.Name()
        n.decode(BytesIO(b"\x07example\x03com\x00"))
        self.assertEqual(n.name, b"example.com")


    def test_encode(self):
        """
        L{Name.encode} encodes its name information and writes it to the
        file-like object passed to it.
        """
        name = dns.Name(b"foo.example.com")
        stream = BytesIO()
        name.encode(stream)
        self.assertEqual(stream.getvalue(), b"\x03foo\x07example\x03com\x00")


    def test_encodeWithCompression(self):
        """
        If a compression dictionary is passed to it, L{Name.encode} uses offset
        information from it to encode its name with references to existing
        labels in the stream instead of including another copy of them in the
        output.  It also updates the compression dictionary with the location of
        the name it writes to the stream.
        """
        name = dns.Name(b"foo.example.com")
        compression = {b"example.com": 0x17}

        # Some bytes already encoded into the stream for this message
        previous = b"some prefix to change .tell()"
        stream = BytesIO()
        stream.write(previous)

        # The position at which the encoded form of this new name will appear in
        # the stream.
        expected = len(previous) + dns.Message.headerSize
        name.encode(stream, compression)
        self.assertEqual(
            b"\x03foo\xc0\x17",
            stream.getvalue()[len(previous):])
        self.assertEqual(
            {b"example.com": 0x17, b"foo.example.com": expected},
            compression)


    def test_unknown(self):
        """
        A resource record of unknown type and class is parsed into an
        L{UnknownRecord} instance with its data preserved, and an
        L{UnknownRecord} instance is serialized to a string equal to the one it
        was parsed from.
        """
        wire = (
            b'\x01\x00' # Message ID
            b'\x00' # answer bit, opCode nibble, auth bit, trunc bit, recursive
                    # bit
            b'\x00' # recursion bit, empty bit, authenticData bit,
                    # checkingDisabled bit, response code nibble
            b'\x00\x01' # number of queries
            b'\x00\x01' # number of answers
            b'\x00\x00' # number of authorities
            b'\x00\x01' # number of additionals

            # query
            b'\x03foo\x03bar\x00'    # foo.bar
            b'\xde\xad'              # type=0xdead
            b'\xbe\xef'              # cls=0xbeef

            # 1st answer
            b'\xc0\x0c'              # foo.bar - compressed
            b'\xde\xad'              # type=0xdead
            b'\xbe\xef'              # cls=0xbeef
            b'\x00\x00\x01\x01'      # ttl=257
            b'\x00\x08somedata'      # some payload data

            # 1st additional
            b'\x03baz\x03ban\x00'    # baz.ban
            b'\x00\x01'              # type=A
            b'\x00\x01'              # cls=IN
            b'\x00\x00\x01\x01'      # ttl=257
            b'\x00\x04'              # len=4
            b'\x01\x02\x03\x04'      # 1.2.3.4
            )

        msg = dns.Message()
        msg.fromStr(wire)

        self.assertEqual(msg.queries, [
                dns.Query(b'foo.bar', type=0xdead, cls=0xbeef),
                ])
        self.assertEqual(msg.answers, [
                dns.RRHeader(b'foo.bar', type=0xdead, cls=0xbeef, ttl=257,
                             payload=dns.UnknownRecord(b'somedata', ttl=257)),
                ])
        self.assertEqual(msg.additional, [
                dns.RRHeader(b'baz.ban', type=dns.A, cls=dns.IN, ttl=257,
                             payload=dns.Record_A('1.2.3.4', ttl=257)),
                ])

        enc = msg.toStr()

        self.assertEqual(enc, wire)


    def test_decodeWithCompression(self):
        """
        If the leading byte of an encoded label (in bytes read from a stream
        passed to L{Name.decode}) has its two high bits set, the next byte is
        treated as a pointer to another label in the stream and that label is
        included in the name being decoded.
        """
        # Slightly modified version of the example from RFC 1035, section 4.1.4.
        stream = BytesIO(
            b"x" * 20 +
            b"\x01f\x03isi\x04arpa\x00"
            b"\x03foo\xc0\x14"
            b"\x03bar\xc0\x20")
        stream.seek(20)
        name = dns.Name()
        name.decode(stream)
        # Verify we found the first name in the stream and that the stream
        # position is left at the first byte after the decoded name.
        self.assertEqual(b"f.isi.arpa", name.name)
        self.assertEqual(32, stream.tell())

        # Get the second name from the stream and make the same assertions.
        name.decode(stream)
        self.assertEqual(name.name, b"foo.f.isi.arpa")
        self.assertEqual(38, stream.tell())

        # Get the third and final name
        name.decode(stream)
        self.assertEqual(name.name, b"bar.foo.f.isi.arpa")
        self.assertEqual(44, stream.tell())


    def test_rejectCompressionLoop(self):
        """
        L{Name.decode} raises L{ValueError} if the stream passed to it includes
        a compression pointer which forms a loop, causing the name to be
        undecodable.
        """
        name = dns.Name()
        stream = BytesIO(b"\xc0\x00")
        self.assertRaises(ValueError, name.decode, stream)



class RoundtripDNSTestCase(unittest.TestCase):
    """
    Encoding and then decoding various objects.
    """

    names = [b"example.org", b"go-away.fish.tv", b"23strikesback.net"]

    def testName(self):
        for n in self.names:
            # encode the name
            f = BytesIO()
            dns.Name(n).encode(f)

            # decode the name
            f.seek(0, 0)
            result = dns.Name()
            result.decode(f)
            self.assertEqual(result.name, n)

    def test_query(self):
        """
        L{dns.Query.encode} returns a byte string representing the fields of the
        query which can be decoded into a new L{dns.Query} instance using
        L{dns.Query.decode}.
        """
        for n in self.names:
            for dnstype in range(1, 17):
                for dnscls in range(1, 5):
                    # encode the query
                    f = BytesIO()
                    dns.Query(n, dnstype, dnscls).encode(f)

                    # decode the result
                    f.seek(0, 0)
                    result = dns.Query()
                    result.decode(f)
                    self.assertEqual(result.name.name, n)
                    self.assertEqual(result.type, dnstype)
                    self.assertEqual(result.cls, dnscls)

    def test_resourceRecordHeader(self):
        """
        L{dns.RRHeader.encode} encodes the record header's information and
        writes it to the file-like object passed to it and
        L{dns.RRHeader.decode} reads from a file-like object to re-construct a
        L{dns.RRHeader} instance.
        """
        # encode the RR
        f = BytesIO()
        dns.RRHeader(b"test.org", 3, 4, 17).encode(f)

        # decode the result
        f.seek(0, 0)
        result = dns.RRHeader()
        result.decode(f)
        self.assertEqual(result.name, dns.Name(b"test.org"))
        self.assertEqual(result.type, 3)
        self.assertEqual(result.cls, 4)
        self.assertEqual(result.ttl, 17)


    def test_resources(self):
        """
        L{dns.SimpleRecord.encode} encodes the record's name information and
        writes it to the file-like object passed to it and
        L{dns.SimpleRecord.decode} reads from a file-like object to re-construct
        a L{dns.SimpleRecord} instance.
        """
        names = (
            b"this.are.test.name",
            b"will.compress.will.this.will.name.will.hopefully",
            b"test.CASE.preSErVatIOn.YeAH",
            b"a.s.h.o.r.t.c.a.s.e.t.o.t.e.s.t",
            b"singleton"
        )
        for s in names:
            f = BytesIO()
            dns.SimpleRecord(s).encode(f)
            f.seek(0, 0)
            result = dns.SimpleRecord()
            result.decode(f)
            self.assertEqual(result.name, dns.Name(s))


    def test_hashable(self):
        """
        Instances of all record types are hashable.
        """
        for k in RECORD_TYPES:
            k1, k2 = k(), k()
            hk1 = hash(k1)
            hk2 = hash(k2)
            self.assertEqual(hk1, hk2, "%s != %s (for %s)" % (hk1,hk2,k))


    def test_Charstr(self):
        """
        Test L{dns.Charstr} encode and decode.
        """
        for n in self.names:
            # encode the name
            f = BytesIO()
            dns.Charstr(n).encode(f)

            # decode the name
            f.seek(0, 0)
            result = dns.Charstr()
            result.decode(f)
            self.assertEqual(result.string, n)


    def _recordRoundtripTest(self, record):
        """
        Assert that encoding C{record} and then decoding the resulting bytes
        creates a record which compares equal to C{record}.
        """
        stream = BytesIO()
        record.encode(stream)

        length = stream.tell()
        stream.seek(0, 0)
        replica = record.__class__()
        replica.decode(stream, length)
        self.assertEqual(record, replica)


    def test_SOA(self):
        """
        The byte stream written by L{dns.Record_SOA.encode} can be used by
        L{dns.Record_SOA.decode} to reconstruct the state of the original
        L{dns.Record_SOA} instance.
        """
        self._recordRoundtripTest(
            dns.Record_SOA(
                mname=b'foo', rname=b'bar', serial=12, refresh=34,
                retry=56, expire=78, minimum=90))


    def test_A(self):
        """
        The byte stream written by L{dns.Record_A.encode} can be used by
        L{dns.Record_A.decode} to reconstruct the state of the original
        L{dns.Record_A} instance.
        """
        self._recordRoundtripTest(dns.Record_A('1.2.3.4'))


    def test_NULL(self):
        """
        The byte stream written by L{dns.Record_NULL.encode} can be used by
        L{dns.Record_NULL.decode} to reconstruct the state of the original
        L{dns.Record_NULL} instance.
        """
        self._recordRoundtripTest(dns.Record_NULL(b'foo bar'))


    def test_WKS(self):
        """
        The byte stream written by L{dns.Record_WKS.encode} can be used by
        L{dns.Record_WKS.decode} to reconstruct the state of the original
        L{dns.Record_WKS} instance.
        """
        self._recordRoundtripTest(dns.Record_WKS('1.2.3.4', 3, b'xyz'))


    def test_AAAA(self):
        """
        The byte stream written by L{dns.Record_AAAA.encode} can be used by
        L{dns.Record_AAAA.decode} to reconstruct the state of the original
        L{dns.Record_AAAA} instance.
        """
        self._recordRoundtripTest(dns.Record_AAAA('::1'))


    def test_A6(self):
        """
        The byte stream written by L{dns.Record_A6.encode} can be used by
        L{dns.Record_A6.decode} to reconstruct the state of the original
        L{dns.Record_A6} instance.
        """
        self._recordRoundtripTest(dns.Record_A6(8, '::1:2', b'foo'))


    def test_SRV(self):
        """
        The byte stream written by L{dns.Record_SRV.encode} can be used by
        L{dns.Record_SRV.decode} to reconstruct the state of the original
        L{dns.Record_SRV} instance.
        """
        self._recordRoundtripTest(dns.Record_SRV(
                priority=1, weight=2, port=3, target=b'example.com'))


    def test_NAPTR(self):
        """
        Test L{dns.Record_NAPTR} encode and decode.
        """
        naptrs = [
            (100, 10, b"u", b"sip+E2U",
             b"!^.*$!sip:information@domain.tld!", b""),
            (100, 50, b"s", b"http+I2L+I2C+I2R",
             b"", b"_http._tcp.gatech.edu")]

        for (order, preference, flags, service, regexp, replacement) in naptrs:
            rin = dns.Record_NAPTR(order, preference, flags, service, regexp,
                                   replacement)
            e = BytesIO()
            rin.encode(e)
            e.seek(0, 0)
            rout = dns.Record_NAPTR()
            rout.decode(e)
            self.assertEqual(rin.order, rout.order)
            self.assertEqual(rin.preference, rout.preference)
            self.assertEqual(rin.flags, rout.flags)
            self.assertEqual(rin.service, rout.service)
            self.assertEqual(rin.regexp, rout.regexp)
            self.assertEqual(rin.replacement.name, rout.replacement.name)
            self.assertEqual(rin.ttl, rout.ttl)


    def test_AFSDB(self):
        """
        The byte stream written by L{dns.Record_AFSDB.encode} can be used by
        L{dns.Record_AFSDB.decode} to reconstruct the state of the original
        L{dns.Record_AFSDB} instance.
        """
        self._recordRoundtripTest(dns.Record_AFSDB(
                subtype=3, hostname=b'example.com'))


    def test_RP(self):
        """
        The byte stream written by L{dns.Record_RP.encode} can be used by
        L{dns.Record_RP.decode} to reconstruct the state of the original
        L{dns.Record_RP} instance.
        """
        self._recordRoundtripTest(dns.Record_RP(
                mbox=b'alice.example.com', txt=b'example.com'))


    def test_HINFO(self):
        """
        The byte stream written by L{dns.Record_HINFO.encode} can be used by
        L{dns.Record_HINFO.decode} to reconstruct the state of the original
        L{dns.Record_HINFO} instance.
        """
        self._recordRoundtripTest(dns.Record_HINFO(cpu=b'fast', os=b'great'))


    def test_MINFO(self):
        """
        The byte stream written by L{dns.Record_MINFO.encode} can be used by
        L{dns.Record_MINFO.decode} to reconstruct the state of the original
        L{dns.Record_MINFO} instance.
        """
        self._recordRoundtripTest(dns.Record_MINFO(
                rmailbx=b'foo', emailbx=b'bar'))


    def test_MX(self):
        """
        The byte stream written by L{dns.Record_MX.encode} can be used by
        L{dns.Record_MX.decode} to reconstruct the state of the original
        L{dns.Record_MX} instance.
        """
        self._recordRoundtripTest(dns.Record_MX(
                preference=1, name=b'example.com'))


    def test_TXT(self):
        """
        The byte stream written by L{dns.Record_TXT.encode} can be used by
        L{dns.Record_TXT.decode} to reconstruct the state of the original
        L{dns.Record_TXT} instance.
        """
        self._recordRoundtripTest(dns.Record_TXT(b'foo', b'bar'))



MESSAGE_AUTHENTIC_DATA_BYTES = (
    b'\x00\x00' # ID
    b'\x00' #
    b'\x20' # RA, Z, AD=1, CD, RCODE
    b'\x00\x00' # Query count
    b'\x00\x00' # Answer count
    b'\x00\x00' # Authority count
    b'\x00\x00' # Additional count
)



MESSAGE_CHECKING_DISABLED_BYTES = (
    b'\x00\x00' # ID
    b'\x00' #
    b'\x10' # RA, Z, AD, CD=1, RCODE
    b'\x00\x00' # Query count
    b'\x00\x00' # Answer count
    b'\x00\x00' # Authority count
    b'\x00\x00' # Additional count
)



class MessageTestCase(unittest.SynchronousTestCase):
    """
    Tests for L{twisted.names.dns.Message}.
    """

    def test_authenticDataDefault(self):
        """
        L{dns.Message.authenticData} has default value 0.
        """
        self.assertEqual(dns.Message().authenticData, 0)


    def test_authenticDataOverride(self):
        """
        L{dns.Message.__init__} accepts a C{authenticData} argument which
        is assigned to L{dns.Message.authenticData}.
        """
        self.assertEqual(dns.Message(authenticData=1).authenticData, 1)


    def test_authenticDataEncode(self):
        """
        L{dns.Message.toStr} encodes L{dns.Message.authenticData} into
        byte4 of the byte string.
        """
        self.assertEqual(
            dns.Message(authenticData=1).toStr(),
            MESSAGE_AUTHENTIC_DATA_BYTES
        )


    def test_authenticDataDecode(self):
        """
        L{dns.Message.fromStr} decodes byte4 and assigns bit3 to
        L{dns.Message.authenticData}.
        """
        m = dns.Message()
        m.fromStr(MESSAGE_AUTHENTIC_DATA_BYTES)

        self.assertEqual(m.authenticData, 1)


    def test_checkingDisabledDefault(self):
        """
        L{dns.Message.checkingDisabled} has default value 0.
        """
        self.assertEqual(dns.Message().checkingDisabled, 0)


    def test_checkingDisabledOverride(self):
        """
        L{dns.Message.__init__} accepts a C{checkingDisabled} argument which
        is assigned to L{dns.Message.checkingDisabled}.
        """
        self.assertEqual(
            dns.Message(checkingDisabled=1).checkingDisabled, 1)


    def test_checkingDisabledEncode(self):
        """
        L{dns.Message.toStr} encodes L{dns.Message.checkingDisabled} into
        byte4 of the byte string.
        """
        self.assertEqual(
            dns.Message(checkingDisabled=1).toStr(),
            MESSAGE_CHECKING_DISABLED_BYTES
        )


    def test_checkingDisabledDecode(self):
        """
        L{dns.Message.fromStr} decodes byte4 and assigns bit4 to
        L{dns.Message.checkingDisabled}.
        """
        m = dns.Message()
        m.fromStr(MESSAGE_CHECKING_DISABLED_BYTES)

        self.assertEqual(m.checkingDisabled, 1)


    def testEmptyMessage(self):
        """
        Test that a message which has been truncated causes an EOFError to
        be raised when it is parsed.
        """
        msg = dns.Message()
        self.assertRaises(EOFError, msg.fromStr, b'')


    def test_emptyQuery(self):
        """
        Test that bytes representing an empty query message can be decoded
        as such.
        """
        msg = dns.Message()
        msg.fromStr(
            b'\x01\x00' # Message ID
            b'\x00' # answer bit, opCode nibble, auth bit, trunc bit, recursive bit
            b'\x00' # recursion bit, empty bit, authenticData bit,
                    # checkingDisabled bit, response code nibble
            b'\x00\x00' # number of queries
            b'\x00\x00' # number of answers
            b'\x00\x00' # number of authorities
            b'\x00\x00' # number of additionals
            )
        self.assertEqual(msg.id, 256)
        self.failIf(msg.answer, "Message was not supposed to be an answer.")
        self.assertEqual(msg.opCode, dns.OP_QUERY)
        self.failIf(msg.auth, "Message was not supposed to be authoritative.")
        self.failIf(msg.trunc, "Message was not supposed to be truncated.")
        self.assertEqual(msg.queries, [])
        self.assertEqual(msg.answers, [])
        self.assertEqual(msg.authority, [])
        self.assertEqual(msg.additional, [])


    def test_NULL(self):
        """
        A I{NULL} record with an arbitrary payload can be encoded and decoded as
        part of a L{dns.Message}.
        """
        bytes = b''.join([dns._ord2bytes(i) for i in range(256)])
        rec = dns.Record_NULL(bytes)
        rr = dns.RRHeader(b'testname', dns.NULL, payload=rec)
        msg1 = dns.Message()
        msg1.answers.append(rr)
        s = BytesIO()
        msg1.encode(s)
        s.seek(0, 0)
        msg2 = dns.Message()
        msg2.decode(s)

        self.failUnless(isinstance(msg2.answers[0].payload, dns.Record_NULL))
        self.assertEqual(msg2.answers[0].payload.payload, bytes)


    def test_lookupRecordTypeDefault(self):
        """
        L{Message.lookupRecordType} returns C{dns.UnknownRecord} if it is
        called with an integer which doesn't correspond to any known record
        type.
        """
        # 65280 is the first value in the range reserved for private
        # use, so it shouldn't ever conflict with an officially
        # allocated value.
        self.assertIdentical(
            dns.Message().lookupRecordType(65280), dns.UnknownRecord)


    def test_nonAuthoritativeMessage(self):
        """
        The L{RRHeader} instances created by L{Message} from a non-authoritative
        message are marked as not authoritative.
        """
        buf = BytesIO()
        answer = dns.RRHeader(payload=dns.Record_A('1.2.3.4', ttl=0))
        answer.encode(buf)
        message = dns.Message()
        message.fromStr(
            b'\x01\x00' # Message ID
            # answer bit, opCode nibble, auth bit, trunc bit, recursive bit
            b'\x00'
            # recursion bit, empty bit, authenticData bit,
            # checkingDisabled bit, response code nibble
            b'\x00'
            b'\x00\x00' # number of queries
            b'\x00\x01' # number of answers
            b'\x00\x00' # number of authorities
            b'\x00\x00' # number of additionals
            + buf.getvalue()
            )
        self.assertEqual(message.answers, [answer])
        self.assertFalse(message.answers[0].auth)


    def test_authoritativeMessage(self):
        """
        The L{RRHeader} instances created by L{Message} from an authoritative
        message are marked as authoritative.
        """
        buf = BytesIO()
        answer = dns.RRHeader(payload=dns.Record_A('1.2.3.4', ttl=0))
        answer.encode(buf)
        message = dns.Message()
        message.fromStr(
            b'\x01\x00' # Message ID
            # answer bit, opCode nibble, auth bit, trunc bit, recursive bit
            b'\x04'
            # recursion bit, empty bit, authenticData bit,
            # checkingDisabled bit, response code nibble
            b'\x00'
            b'\x00\x00' # number of queries
            b'\x00\x01' # number of answers
            b'\x00\x00' # number of authorities
            b'\x00\x00' # number of additionals
            + buf.getvalue()
            )
        answer.auth = True
        self.assertEqual(message.answers, [answer])
        self.assertTrue(message.answers[0].auth)



class TestController(object):
    """
    Pretend to be a DNS query processor for a DNSDatagramProtocol.

    @ivar messages: the list of received messages.
    @type messages: C{list} of (msg, protocol, address)
    """

    def __init__(self):
        """
        Initialize the controller: create a list of messages.
        """
        self.messages = []


    def messageReceived(self, msg, proto, addr=None):
        """
        Save the message so that it can be checked during the tests.
        """
        self.messages.append((msg, proto, addr))



class DatagramProtocolTestCase(unittest.TestCase):
    """
    Test various aspects of L{dns.DNSDatagramProtocol}.
    """

    def setUp(self):
        """
        Create a L{dns.DNSDatagramProtocol} with a deterministic clock.
        """
        self.clock = task.Clock()
        self.controller = TestController()
        self.proto = dns.DNSDatagramProtocol(self.controller)
        transport = proto_helpers.FakeDatagramTransport()
        self.proto.makeConnection(transport)
        self.proto.callLater = self.clock.callLater


    def test_truncatedPacket(self):
        """
        Test that when a short datagram is received, datagramReceived does
        not raise an exception while processing it.
        """
        self.proto.datagramReceived(
            b'', address.IPv4Address('UDP', '127.0.0.1', 12345))
        self.assertEqual(self.controller.messages, [])


    def test_simpleQuery(self):
        """
        Test content received after a query.
        """
        d = self.proto.query(('127.0.0.1', 21345), [dns.Query(b'foo')])
        self.assertEqual(len(self.proto.liveMessages.keys()), 1)
        m = dns.Message()
        m.id = next(iter(self.proto.liveMessages.keys()))
        m.answers = [dns.RRHeader(payload=dns.Record_A(address='1.2.3.4'))]
        def cb(result):
            self.assertEqual(result.answers[0].payload.dottedQuad(), '1.2.3.4')
        d.addCallback(cb)
        self.proto.datagramReceived(m.toStr(), ('127.0.0.1', 21345))
        return d


    def test_queryTimeout(self):
        """
        Test that query timeouts after some seconds.
        """
        d = self.proto.query(('127.0.0.1', 21345), [dns.Query(b'foo')])
        self.assertEqual(len(self.proto.liveMessages), 1)
        self.clock.advance(10)
        self.assertFailure(d, dns.DNSQueryTimeoutError)
        self.assertEqual(len(self.proto.liveMessages), 0)
        return d


    def test_writeError(self):
        """
        Exceptions raised by the transport's write method should be turned into
        C{Failure}s passed to errbacks of the C{Deferred} returned by
        L{DNSDatagramProtocol.query}.
        """
        def writeError(message, addr):
            raise RuntimeError("bar")
        self.proto.transport.write = writeError

        d = self.proto.query(('127.0.0.1', 21345), [dns.Query(b'foo')])
        return self.assertFailure(d, RuntimeError)


    def test_listenError(self):
        """
        Exception L{CannotListenError} raised by C{listenUDP} should be turned
        into a C{Failure} passed to errback of the C{Deferred} returned by
        L{DNSDatagramProtocol.query}.
        """
        def startListeningError():
            raise CannotListenError(None, None, None)
        self.proto.startListening = startListeningError
        # Clean up transport so that the protocol calls startListening again
        self.proto.transport = None

        d = self.proto.query(('127.0.0.1', 21345), [dns.Query(b'foo')])
        return self.assertFailure(d, CannotListenError)


    def test_receiveMessageNotInLiveMessages(self):
        """
        When receiving a message whose id is not in
        L{DNSDatagramProtocol.liveMessages} or L{DNSDatagramProtocol.resends},
        the message will be received by L{DNSDatagramProtocol.controller}.
        """
        message = dns.Message()
        message.id = 1
        message.answers = [dns.RRHeader(
            payload=dns.Record_A(address='1.2.3.4'))]
        self.proto.datagramReceived(message.toStr(), ('127.0.0.1', 21345))
        self.assertEqual(self.controller.messages[-1][0].toStr(),
                         message.toStr())



class TestTCPController(TestController):
    """
    Pretend to be a DNS query processor for a DNSProtocol.

    @ivar connections: A list of L{DNSProtocol} instances which have
        notified this controller that they are connected and have not
        yet notified it that their connection has been lost.
    """
    def __init__(self):
        TestController.__init__(self)
        self.connections = []


    def connectionMade(self, proto):
        self.connections.append(proto)


    def connectionLost(self, proto):
        self.connections.remove(proto)



class DNSProtocolTestCase(unittest.TestCase):
    """
    Test various aspects of L{dns.DNSProtocol}.
    """

    def setUp(self):
        """
        Create a L{dns.DNSProtocol} with a deterministic clock.
        """
        self.clock = task.Clock()
        self.controller = TestTCPController()
        self.proto = dns.DNSProtocol(self.controller)
        self.proto.makeConnection(proto_helpers.StringTransport())
        self.proto.callLater = self.clock.callLater


    def test_connectionTracking(self):
        """
        L{dns.DNSProtocol} calls its controller's C{connectionMade}
        method with itself when it is connected to a transport and its
        controller's C{connectionLost} method when it is disconnected.
        """
        self.assertEqual(self.controller.connections, [self.proto])
        self.proto.connectionLost(
            Failure(ConnectionDone("Fake Connection Done")))
        self.assertEqual(self.controller.connections, [])


    def test_queryTimeout(self):
        """
        Test that query timeouts after some seconds.
        """
        d = self.proto.query([dns.Query(b'foo')])
        self.assertEqual(len(self.proto.liveMessages), 1)
        self.clock.advance(60)
        self.assertFailure(d, dns.DNSQueryTimeoutError)
        self.assertEqual(len(self.proto.liveMessages), 0)
        return d


    def test_simpleQuery(self):
        """
        Test content received after a query.
        """
        d = self.proto.query([dns.Query(b'foo')])
        self.assertEqual(len(self.proto.liveMessages.keys()), 1)
        m = dns.Message()
        m.id = next(iter(self.proto.liveMessages.keys()))
        m.answers = [dns.RRHeader(payload=dns.Record_A(address='1.2.3.4'))]
        def cb(result):
            self.assertEqual(result.answers[0].payload.dottedQuad(), '1.2.3.4')
        d.addCallback(cb)
        s = m.toStr()
        s = struct.pack('!H', len(s)) + s
        self.proto.dataReceived(s)
        return d


    def test_writeError(self):
        """
        Exceptions raised by the transport's write method should be turned into
        C{Failure}s passed to errbacks of the C{Deferred} returned by
        L{DNSProtocol.query}.
        """
        def writeError(message):
            raise RuntimeError("bar")
        self.proto.transport.write = writeError

        d = self.proto.query([dns.Query(b'foo')])
        return self.assertFailure(d, RuntimeError)


    def test_receiveMessageNotInLiveMessages(self):
        """
        When receiving a message whose id is not in L{DNSProtocol.liveMessages}
        the message will be received by L{DNSProtocol.controller}.
        """
        message = dns.Message()
        message.id = 1
        message.answers = [dns.RRHeader(
            payload=dns.Record_A(address='1.2.3.4'))]
        string = message.toStr()
        string = struct.pack('!H', len(string)) + string
        self.proto.dataReceived(string)
        self.assertEqual(self.controller.messages[-1][0].toStr(),
                         message.toStr())



class ReprTests(unittest.TestCase):
    """
    Tests for the C{__repr__} implementation of record classes.
    """
    def test_ns(self):
        """
        The repr of a L{dns.Record_NS} instance includes the name of the
        nameserver and the TTL of the record.
        """
        self.assertEqual(
            repr(dns.Record_NS(b'example.com', 4321)),
            "<NS name=example.com ttl=4321>")


    def test_md(self):
        """
        The repr of a L{dns.Record_MD} instance includes the name of the
        mail destination and the TTL of the record.
        """
        self.assertEqual(
            repr(dns.Record_MD(b'example.com', 4321)),
            "<MD name=example.com ttl=4321>")


    def test_mf(self):
        """
        The repr of a L{dns.Record_MF} instance includes the name of the
        mail forwarder and the TTL of the record.
        """
        self.assertEqual(
            repr(dns.Record_MF(b'example.com', 4321)),
            "<MF name=example.com ttl=4321>")


    def test_cname(self):
        """
        The repr of a L{dns.Record_CNAME} instance includes the name of the
        mail forwarder and the TTL of the record.
        """
        self.assertEqual(
            repr(dns.Record_CNAME(b'example.com', 4321)),
            "<CNAME name=example.com ttl=4321>")


    def test_mb(self):
        """
        The repr of a L{dns.Record_MB} instance includes the name of the
        mailbox and the TTL of the record.
        """
        self.assertEqual(
            repr(dns.Record_MB(b'example.com', 4321)),
            "<MB name=example.com ttl=4321>")


    def test_mg(self):
        """
        The repr of a L{dns.Record_MG} instance includes the name of the
        mail group memeber and the TTL of the record.
        """
        self.assertEqual(
            repr(dns.Record_MG(b'example.com', 4321)),
            "<MG name=example.com ttl=4321>")


    def test_mr(self):
        """
        The repr of a L{dns.Record_MR} instance includes the name of the
        mail rename domain and the TTL of the record.
        """
        self.assertEqual(
            repr(dns.Record_MR(b'example.com', 4321)),
            "<MR name=example.com ttl=4321>")


    def test_ptr(self):
        """
        The repr of a L{dns.Record_PTR} instance includes the name of the
        pointer and the TTL of the record.
        """
        self.assertEqual(
            repr(dns.Record_PTR(b'example.com', 4321)),
            "<PTR name=example.com ttl=4321>")


    def test_dname(self):
        """
        The repr of a L{dns.Record_DNAME} instance includes the name of the
        non-terminal DNS name redirection and the TTL of the record.
        """
        self.assertEqual(
            repr(dns.Record_DNAME(b'example.com', 4321)),
            "<DNAME name=example.com ttl=4321>")


    def test_a(self):
        """
        The repr of a L{dns.Record_A} instance includes the dotted-quad
        string representation of the address it is for and the TTL of the
        record.
        """
        self.assertEqual(
            repr(dns.Record_A('1.2.3.4', 567)),
            '<A address=1.2.3.4 ttl=567>')


    def test_soa(self):
        """
        The repr of a L{dns.Record_SOA} instance includes all of the
        authority fields.
        """
        self.assertEqual(
            repr(dns.Record_SOA(mname=b'mName', rname=b'rName', serial=123,
                                refresh=456, retry=789, expire=10,
                                minimum=11, ttl=12)),
            "<SOA mname=mName rname=rName serial=123 refresh=456 "
            "retry=789 expire=10 minimum=11 ttl=12>")


    def test_null(self):
        """
        The repr of a L{dns.Record_NULL} instance includes the repr of its
        payload and the TTL of the record.
        """
        self.assertEqual(
            repr(dns.Record_NULL(b'abcd', 123)),
            "<NULL payload='abcd' ttl=123>")


    def test_wks(self):
        """
        The repr of a L{dns.Record_WKS} instance includes the dotted-quad
        string representation of the address it is for, the IP protocol
        number it is for, and the TTL of the record.
        """
        self.assertEqual(
            repr(dns.Record_WKS('2.3.4.5', 7, ttl=8)),
            "<WKS address=2.3.4.5 protocol=7 ttl=8>")


    def test_aaaa(self):
        """
        The repr of a L{dns.Record_AAAA} instance includes the colon-separated
        hex string representation of the address it is for and the TTL of the
        record.
        """
        self.assertEqual(
            repr(dns.Record_AAAA('8765::1234', ttl=10)),
            "<AAAA address=8765::1234 ttl=10>")


    def test_a6(self):
        """
        The repr of a L{dns.Record_A6} instance includes the colon-separated
        hex string representation of the address it is for and the TTL of the
        record.
        """
        self.assertEqual(
            repr(dns.Record_A6(0, '1234::5678', b'foo.bar', ttl=10)),
            "<A6 suffix=1234::5678 prefix=foo.bar ttl=10>")


    def test_srv(self):
        """
        The repr of a L{dns.Record_SRV} instance includes the name and port of
        the target and the priority, weight, and TTL of the record.
        """
        self.assertEqual(
            repr(dns.Record_SRV(1, 2, 3, b'example.org', 4)),
            "<SRV priority=1 weight=2 target=example.org port=3 ttl=4>")


    def test_naptr(self):
        """
        The repr of a L{dns.Record_NAPTR} instance includes the order,
        preference, flags, service, regular expression, replacement, and TTL of
        the record.
        """
        record = dns.Record_NAPTR(
            5, 9, b"S", b"http", b"/foo/bar/i", b"baz", 3)
        self.assertEqual(
            repr(record),
            "<NAPTR order=5 preference=9 flags=S service=http "
            "regexp=/foo/bar/i replacement=baz ttl=3>")


    def test_afsdb(self):
        """
        The repr of a L{dns.Record_AFSDB} instance includes the subtype,
        hostname, and TTL of the record.
        """
        self.assertEqual(
            repr(dns.Record_AFSDB(3, b'example.org', 5)),
            "<AFSDB subtype=3 hostname=example.org ttl=5>")


    def test_rp(self):
        """
        The repr of a L{dns.Record_RP} instance includes the mbox, txt, and TTL
        fields of the record.
        """
        self.assertEqual(
            repr(dns.Record_RP(b'alice.example.com', b'admin.example.com', 3)),
            "<RP mbox=alice.example.com txt=admin.example.com ttl=3>")


    def test_hinfo(self):
        """
        The repr of a L{dns.Record_HINFO} instance includes the cpu, os, and
        TTL fields of the record.
        """
        self.assertEqual(
            repr(dns.Record_HINFO(b'sparc', b'minix', 12)),
            "<HINFO cpu='sparc' os='minix' ttl=12>")


    def test_minfo(self):
        """
        The repr of a L{dns.Record_MINFO} instance includes the rmailbx,
        emailbx, and TTL fields of the record.
        """
        record = dns.Record_MINFO(
            b'alice.example.com', b'bob.example.com', 15)
        self.assertEqual(
            repr(record),
            "<MINFO responsibility=alice.example.com "
            "errors=bob.example.com ttl=15>")


    def test_mx(self):
        """
        The repr of a L{dns.Record_MX} instance includes the preference, name,
        and TTL fields of the record.
        """
        self.assertEqual(
            repr(dns.Record_MX(13, b'mx.example.com', 2)),
            "<MX preference=13 name=mx.example.com ttl=2>")


    def test_txt(self):
        """
        The repr of a L{dns.Record_TXT} instance includes the data and ttl
        fields of the record.
        """
        self.assertEqual(
            repr(dns.Record_TXT(b"foo", b"bar", ttl=15)),
            "<TXT data=['foo', 'bar'] ttl=15>")


    def test_spf(self):
        """
        The repr of a L{dns.Record_SPF} instance includes the data and ttl
        fields of the record.
        """
        self.assertEqual(
            repr(dns.Record_SPF(b"foo", b"bar", ttl=15)),
            "<SPF data=['foo', 'bar'] ttl=15>")


    def test_unknown(self):
        """
        The repr of a L{dns.UnknownRecord} instance includes the data and ttl
        fields of the record.
        """
        self.assertEqual(
            repr(dns.UnknownRecord(b"foo\x1fbar", 12)),
            "<UNKNOWN data='foo\\x1fbar' ttl=12>")



class EqualityTests(ComparisonTestsMixin, unittest.TestCase):
    """
    Tests for the equality and non-equality behavior of record classes.
    """
    def _equalityTest(self, firstValueOne, secondValueOne, valueTwo):
        return self.assertNormalEqualityImplementation(
            firstValueOne, secondValueOne, valueTwo)


    def test_charstr(self):
        """
        Two L{dns.Charstr} instances compare equal if and only if they have the
        same string value.
        """
        self._equalityTest(
            dns.Charstr(b'abc'), dns.Charstr(b'abc'), dns.Charstr(b'def'))


    def test_name(self):
        """
        Two L{dns.Name} instances compare equal if and only if they have the
        same name value.
        """
        self._equalityTest(
            dns.Name(b'abc'), dns.Name(b'abc'), dns.Name(b'def'))


    def _simpleEqualityTest(self, cls):
        """
        Assert that instances of C{cls} with the same attributes compare equal
        to each other and instances with different attributes compare as not
        equal.

        @param cls: A L{dns.SimpleRecord} subclass.
        """
        # Vary the TTL
        self._equalityTest(
            cls(b'example.com', 123),
            cls(b'example.com', 123),
            cls(b'example.com', 321))
        # Vary the name
        self._equalityTest(
            cls(b'example.com', 123),
            cls(b'example.com', 123),
            cls(b'example.org', 123))


    def test_rrheader(self):
        """
        Two L{dns.RRHeader} instances compare equal if and only if they have
        the same name, type, class, time to live, payload, and authoritative
        bit.
        """
        # Vary the name
        self._equalityTest(
            dns.RRHeader(b'example.com', payload=dns.Record_A('1.2.3.4')),
            dns.RRHeader(b'example.com', payload=dns.Record_A('1.2.3.4')),
            dns.RRHeader(b'example.org', payload=dns.Record_A('1.2.3.4')))

        # Vary the payload
        self._equalityTest(
            dns.RRHeader(b'example.com', payload=dns.Record_A('1.2.3.4')),
            dns.RRHeader(b'example.com', payload=dns.Record_A('1.2.3.4')),
            dns.RRHeader(b'example.com', payload=dns.Record_A('1.2.3.5')))

        # Vary the type.  Leave the payload as None so that we don't have to
        # provide non-equal values.
        self._equalityTest(
            dns.RRHeader(b'example.com', dns.A),
            dns.RRHeader(b'example.com', dns.A),
            dns.RRHeader(b'example.com', dns.MX))

        # Probably not likely to come up.  Most people use the internet.
        self._equalityTest(
            dns.RRHeader(b'example.com', cls=dns.IN, payload=dns.Record_A('1.2.3.4')),
            dns.RRHeader(b'example.com', cls=dns.IN, payload=dns.Record_A('1.2.3.4')),
            dns.RRHeader(b'example.com', cls=dns.CS, payload=dns.Record_A('1.2.3.4')))

        # Vary the ttl
        self._equalityTest(
            dns.RRHeader(b'example.com', ttl=60, payload=dns.Record_A('1.2.3.4')),
            dns.RRHeader(b'example.com', ttl=60, payload=dns.Record_A('1.2.3.4')),
            dns.RRHeader(b'example.com', ttl=120, payload=dns.Record_A('1.2.3.4')))

        # Vary the auth bit
        self._equalityTest(
            dns.RRHeader(b'example.com', auth=1, payload=dns.Record_A('1.2.3.4')),
            dns.RRHeader(b'example.com', auth=1, payload=dns.Record_A('1.2.3.4')),
            dns.RRHeader(b'example.com', auth=0, payload=dns.Record_A('1.2.3.4')))


    def test_ns(self):
        """
        Two L{dns.Record_NS} instances compare equal if and only if they have
        the same name and TTL.
        """
        self._simpleEqualityTest(dns.Record_NS)


    def test_md(self):
        """
        Two L{dns.Record_MD} instances compare equal if and only if they have
        the same name and TTL.
        """
        self._simpleEqualityTest(dns.Record_MD)


    def test_mf(self):
        """
        Two L{dns.Record_MF} instances compare equal if and only if they have
        the same name and TTL.
        """
        self._simpleEqualityTest(dns.Record_MF)


    def test_cname(self):
        """
        Two L{dns.Record_CNAME} instances compare equal if and only if they
        have the same name and TTL.
        """
        self._simpleEqualityTest(dns.Record_CNAME)


    def test_mb(self):
        """
        Two L{dns.Record_MB} instances compare equal if and only if they have
        the same name and TTL.
        """
        self._simpleEqualityTest(dns.Record_MB)


    def test_mg(self):
        """
        Two L{dns.Record_MG} instances compare equal if and only if they have
        the same name and TTL.
        """
        self._simpleEqualityTest(dns.Record_MG)


    def test_mr(self):
        """
        Two L{dns.Record_MR} instances compare equal if and only if they have
        the same name and TTL.
        """
        self._simpleEqualityTest(dns.Record_MR)


    def test_ptr(self):
        """
        Two L{dns.Record_PTR} instances compare equal if and only if they have
        the same name and TTL.
        """
        self._simpleEqualityTest(dns.Record_PTR)


    def test_dname(self):
        """
        Two L{dns.Record_MD} instances compare equal if and only if they have
        the same name and TTL.
        """
        self._simpleEqualityTest(dns.Record_DNAME)


    def test_a(self):
        """
        Two L{dns.Record_A} instances compare equal if and only if they have
        the same address and TTL.
        """
        # Vary the TTL
        self._equalityTest(
            dns.Record_A('1.2.3.4', 5),
            dns.Record_A('1.2.3.4', 5),
            dns.Record_A('1.2.3.4', 6))
        # Vary the address
        self._equalityTest(
            dns.Record_A('1.2.3.4', 5),
            dns.Record_A('1.2.3.4', 5),
            dns.Record_A('1.2.3.5', 5))


    def test_soa(self):
        """
        Two L{dns.Record_SOA} instances compare equal if and only if they have
        the same mname, rname, serial, refresh, minimum, expire, retry, and
        ttl.
        """
        # Vary the mname
        self._equalityTest(
            dns.Record_SOA(b'mname', b'rname', 123, 456, 789, 10, 20, 30),
            dns.Record_SOA(b'mname', b'rname', 123, 456, 789, 10, 20, 30),
            dns.Record_SOA(b'xname', b'rname', 123, 456, 789, 10, 20, 30))
        # Vary the rname
        self._equalityTest(
            dns.Record_SOA(b'mname', b'rname', 123, 456, 789, 10, 20, 30),
            dns.Record_SOA(b'mname', b'rname', 123, 456, 789, 10, 20, 30),
            dns.Record_SOA(b'mname', b'xname', 123, 456, 789, 10, 20, 30))
        # Vary the serial
        self._equalityTest(
            dns.Record_SOA(b'mname', b'rname', 123, 456, 789, 10, 20, 30),
            dns.Record_SOA(b'mname', b'rname', 123, 456, 789, 10, 20, 30),
            dns.Record_SOA(b'mname', b'rname', 1, 456, 789, 10, 20, 30))
        # Vary the refresh
        self._equalityTest(
            dns.Record_SOA(b'mname', b'rname', 123, 456, 789, 10, 20, 30),
            dns.Record_SOA(b'mname', b'rname', 123, 456, 789, 10, 20, 30),
            dns.Record_SOA(b'mname', b'rname', 123, 1, 789, 10, 20, 30))
        # Vary the minimum
        self._equalityTest(
            dns.Record_SOA(b'mname', b'rname', 123, 456, 789, 10, 20, 30),
            dns.Record_SOA(b'mname', b'rname', 123, 456, 789, 10, 20, 30),
            dns.Record_SOA(b'mname', b'rname', 123, 456, 1, 10, 20, 30))
        # Vary the expire
        self._equalityTest(
            dns.Record_SOA(b'mname', b'rname', 123, 456, 789, 10, 20, 30),
            dns.Record_SOA(b'mname', b'rname', 123, 456, 789, 10, 20, 30),
            dns.Record_SOA(b'mname', b'rname', 123, 456, 789, 1, 20, 30))
        # Vary the retry
        self._equalityTest(
            dns.Record_SOA(b'mname', b'rname', 123, 456, 789, 10, 20, 30),
            dns.Record_SOA(b'mname', b'rname', 123, 456, 789, 10, 20, 30),
            dns.Record_SOA(b'mname', b'rname', 123, 456, 789, 10, 1, 30))
        # Vary the ttl
        self._equalityTest(
            dns.Record_SOA(b'mname', b'rname', 123, 456, 789, 10, 20, 30),
            dns.Record_SOA(b'mname', b'rname', 123, 456, 789, 10, 20, 30),
            dns.Record_SOA(b'mname', b'xname', 123, 456, 789, 10, 20, 1))


    def test_null(self):
        """
        Two L{dns.Record_NULL} instances compare equal if and only if they have
        the same payload and ttl.
        """
        # Vary the payload
        self._equalityTest(
            dns.Record_NULL('foo bar', 10),
            dns.Record_NULL('foo bar', 10),
            dns.Record_NULL('bar foo', 10))
        # Vary the ttl
        self._equalityTest(
            dns.Record_NULL('foo bar', 10),
            dns.Record_NULL('foo bar', 10),
            dns.Record_NULL('foo bar', 100))


    def test_wks(self):
        """
        Two L{dns.Record_WKS} instances compare equal if and only if they have
        the same address, protocol, map, and ttl.
        """
        # Vary the address
        self._equalityTest(
            dns.Record_WKS('1.2.3.4', 1, 'foo', 2),
            dns.Record_WKS('1.2.3.4', 1, 'foo', 2),
            dns.Record_WKS('4.3.2.1', 1, 'foo', 2))
        # Vary the protocol
        self._equalityTest(
            dns.Record_WKS('1.2.3.4', 1, 'foo', 2),
            dns.Record_WKS('1.2.3.4', 1, 'foo', 2),
            dns.Record_WKS('1.2.3.4', 100, 'foo', 2))
        # Vary the map
        self._equalityTest(
            dns.Record_WKS('1.2.3.4', 1, 'foo', 2),
            dns.Record_WKS('1.2.3.4', 1, 'foo', 2),
            dns.Record_WKS('1.2.3.4', 1, 'bar', 2))
        # Vary the ttl
        self._equalityTest(
            dns.Record_WKS('1.2.3.4', 1, 'foo', 2),
            dns.Record_WKS('1.2.3.4', 1, 'foo', 2),
            dns.Record_WKS('1.2.3.4', 1, 'foo', 200))


    def test_aaaa(self):
        """
        Two L{dns.Record_AAAA} instances compare equal if and only if they have
        the same address and ttl.
        """
        # Vary the address
        self._equalityTest(
            dns.Record_AAAA('1::2', 1),
            dns.Record_AAAA('1::2', 1),
            dns.Record_AAAA('2::1', 1))
        # Vary the ttl
        self._equalityTest(
            dns.Record_AAAA('1::2', 1),
            dns.Record_AAAA('1::2', 1),
            dns.Record_AAAA('1::2', 10))


    def test_a6(self):
        """
        Two L{dns.Record_A6} instances compare equal if and only if they have
        the same prefix, prefix length, suffix, and ttl.
        """
        # Note, A6 is crazy, I'm not sure these values are actually legal.
        # Hopefully that doesn't matter for this test. -exarkun

        # Vary the prefix length
        self._equalityTest(
            dns.Record_A6(16, '::abcd', b'example.com', 10),
            dns.Record_A6(16, '::abcd', b'example.com', 10),
            dns.Record_A6(32, '::abcd', b'example.com', 10))
        # Vary the suffix
        self._equalityTest(
            dns.Record_A6(16, '::abcd', b'example.com', 10),
            dns.Record_A6(16, '::abcd', b'example.com', 10),
            dns.Record_A6(16, '::abcd:0', b'example.com', 10))
        # Vary the prefix
        self._equalityTest(
            dns.Record_A6(16, '::abcd', b'example.com', 10),
            dns.Record_A6(16, '::abcd', b'example.com', 10),
            dns.Record_A6(16, '::abcd', b'example.org', 10))
        # Vary the ttl
        self._equalityTest(
            dns.Record_A6(16, '::abcd', b'example.com', 10),
            dns.Record_A6(16, '::abcd', b'example.com', 10),
            dns.Record_A6(16, '::abcd', b'example.com', 100))


    def test_srv(self):
        """
        Two L{dns.Record_SRV} instances compare equal if and only if they have
        the same priority, weight, port, target, and ttl.
        """
        # Vary the priority
        self._equalityTest(
            dns.Record_SRV(10, 20, 30, b'example.com', 40),
            dns.Record_SRV(10, 20, 30, b'example.com', 40),
            dns.Record_SRV(100, 20, 30, b'example.com', 40))
        # Vary the weight
        self._equalityTest(
            dns.Record_SRV(10, 20, 30, b'example.com', 40),
            dns.Record_SRV(10, 20, 30, b'example.com', 40),
            dns.Record_SRV(10, 200, 30, b'example.com', 40))
        # Vary the port
        self._equalityTest(
            dns.Record_SRV(10, 20, 30, b'example.com', 40),
            dns.Record_SRV(10, 20, 30, b'example.com', 40),
            dns.Record_SRV(10, 20, 300, b'example.com', 40))
        # Vary the target
        self._equalityTest(
            dns.Record_SRV(10, 20, 30, b'example.com', 40),
            dns.Record_SRV(10, 20, 30, b'example.com', 40),
            dns.Record_SRV(10, 20, 30, b'example.org', 40))
        # Vary the ttl
        self._equalityTest(
            dns.Record_SRV(10, 20, 30, b'example.com', 40),
            dns.Record_SRV(10, 20, 30, b'example.com', 40),
            dns.Record_SRV(10, 20, 30, b'example.com', 400))


    def test_naptr(self):
        """
        Two L{dns.Record_NAPTR} instances compare equal if and only if they
        have the same order, preference, flags, service, regexp, replacement,
        and ttl.
        """
        # Vary the order
        self._equalityTest(
            dns.Record_NAPTR(1, 2, b"u", b"sip+E2U", b"/foo/bar/", b"baz", 12),
            dns.Record_NAPTR(1, 2, b"u", b"sip+E2U", b"/foo/bar/", b"baz", 12),
            dns.Record_NAPTR(2, 2, b"u", b"sip+E2U", b"/foo/bar/", b"baz", 12))
        # Vary the preference
        self._equalityTest(
            dns.Record_NAPTR(1, 2, b"u", b"sip+E2U", b"/foo/bar/", b"baz", 12),
            dns.Record_NAPTR(1, 2, b"u", b"sip+E2U", b"/foo/bar/", b"baz", 12),
            dns.Record_NAPTR(1, 3, b"u", b"sip+E2U", b"/foo/bar/", b"baz", 12))
        # Vary the flags
        self._equalityTest(
            dns.Record_NAPTR(1, 2, b"u", b"sip+E2U", b"/foo/bar/", b"baz", 12),
            dns.Record_NAPTR(1, 2, b"u", b"sip+E2U", b"/foo/bar/", b"baz", 12),
            dns.Record_NAPTR(1, 2, b"p", b"sip+E2U", b"/foo/bar/", b"baz", 12))
        # Vary the service
        self._equalityTest(
            dns.Record_NAPTR(1, 2, b"u", b"sip+E2U", b"/foo/bar/", b"baz", 12),
            dns.Record_NAPTR(1, 2, b"u", b"sip+E2U", b"/foo/bar/", b"baz", 12),
            dns.Record_NAPTR(1, 2, b"u", b"http", b"/foo/bar/", b"baz", 12))
        # Vary the regexp
        self._equalityTest(
            dns.Record_NAPTR(1, 2, b"u", b"sip+E2U", b"/foo/bar/", b"baz", 12),
            dns.Record_NAPTR(1, 2, b"u", b"sip+E2U", b"/foo/bar/", b"baz", 12),
            dns.Record_NAPTR(1, 2, b"u", b"sip+E2U", b"/bar/foo/", b"baz", 12))
        # Vary the replacement
        self._equalityTest(
            dns.Record_NAPTR(1, 2, b"u", b"sip+E2U", b"/foo/bar/", b"baz", 12),
            dns.Record_NAPTR(1, 2, b"u", b"sip+E2U", b"/foo/bar/", b"baz", 12),
            dns.Record_NAPTR(1, 2, b"u", b"sip+E2U", b"/bar/foo/", b"quux", 12))
        # Vary the ttl
        self._equalityTest(
            dns.Record_NAPTR(1, 2, b"u", b"sip+E2U", b"/foo/bar/", b"baz", 12),
            dns.Record_NAPTR(1, 2, b"u", b"sip+E2U", b"/foo/bar/", b"baz", 12),
            dns.Record_NAPTR(1, 2, b"u", b"sip+E2U", b"/bar/foo/", b"baz", 5))


    def test_afsdb(self):
        """
        Two L{dns.Record_AFSDB} instances compare equal if and only if they
        have the same subtype, hostname, and ttl.
        """
        # Vary the subtype
        self._equalityTest(
            dns.Record_AFSDB(1, b'example.com', 2),
            dns.Record_AFSDB(1, b'example.com', 2),
            dns.Record_AFSDB(2, b'example.com', 2))
        # Vary the hostname
        self._equalityTest(
            dns.Record_AFSDB(1, b'example.com', 2),
            dns.Record_AFSDB(1, b'example.com', 2),
            dns.Record_AFSDB(1, b'example.org', 2))
        # Vary the ttl
        self._equalityTest(
            dns.Record_AFSDB(1, b'example.com', 2),
            dns.Record_AFSDB(1, b'example.com', 2),
            dns.Record_AFSDB(1, b'example.com', 3))


    def test_rp(self):
        """
        Two L{Record_RP} instances compare equal if and only if they have the
        same mbox, txt, and ttl.
        """
        # Vary the mbox
        self._equalityTest(
            dns.Record_RP(b'alice.example.com', b'alice is nice', 10),
            dns.Record_RP(b'alice.example.com', b'alice is nice', 10),
            dns.Record_RP(b'bob.example.com', b'alice is nice', 10))
        # Vary the txt
        self._equalityTest(
            dns.Record_RP(b'alice.example.com', b'alice is nice', 10),
            dns.Record_RP(b'alice.example.com', b'alice is nice', 10),
            dns.Record_RP(b'alice.example.com', b'alice is not nice', 10))
        # Vary the ttl
        self._equalityTest(
            dns.Record_RP(b'alice.example.com', b'alice is nice', 10),
            dns.Record_RP(b'alice.example.com', b'alice is nice', 10),
            dns.Record_RP(b'alice.example.com', b'alice is nice', 100))


    def test_hinfo(self):
        """
        Two L{dns.Record_HINFO} instances compare equal if and only if they
        have the same cpu, os, and ttl.
        """
        # Vary the cpu
        self._equalityTest(
            dns.Record_HINFO('x86-64', 'plan9', 10),
            dns.Record_HINFO('x86-64', 'plan9', 10),
            dns.Record_HINFO('i386', 'plan9', 10))
        # Vary the os
        self._equalityTest(
            dns.Record_HINFO('x86-64', 'plan9', 10),
            dns.Record_HINFO('x86-64', 'plan9', 10),
            dns.Record_HINFO('x86-64', 'plan11', 10))
        # Vary the ttl
        self._equalityTest(
            dns.Record_HINFO('x86-64', 'plan9', 10),
            dns.Record_HINFO('x86-64', 'plan9', 10),
            dns.Record_HINFO('x86-64', 'plan9', 100))


    def test_minfo(self):
        """
        Two L{dns.Record_MINFO} instances compare equal if and only if they
        have the same rmailbx, emailbx, and ttl.
        """
        # Vary the rmailbx
        self._equalityTest(
            dns.Record_MINFO(b'rmailbox', b'emailbox', 10),
            dns.Record_MINFO(b'rmailbox', b'emailbox', 10),
            dns.Record_MINFO(b'someplace', b'emailbox', 10))
        # Vary the emailbx
        self._equalityTest(
            dns.Record_MINFO(b'rmailbox', b'emailbox', 10),
            dns.Record_MINFO(b'rmailbox', b'emailbox', 10),
            dns.Record_MINFO(b'rmailbox', b'something', 10))
        # Vary the ttl
        self._equalityTest(
            dns.Record_MINFO(b'rmailbox', b'emailbox', 10),
            dns.Record_MINFO(b'rmailbox', b'emailbox', 10),
            dns.Record_MINFO(b'rmailbox', b'emailbox', 100))


    def test_mx(self):
        """
        Two L{dns.Record_MX} instances compare equal if and only if they have
        the same preference, name, and ttl.
        """
        # Vary the preference
        self._equalityTest(
            dns.Record_MX(10, b'example.org', 20),
            dns.Record_MX(10, b'example.org', 20),
            dns.Record_MX(100, b'example.org', 20))
        # Vary the name
        self._equalityTest(
            dns.Record_MX(10, b'example.org', 20),
            dns.Record_MX(10, b'example.org', 20),
            dns.Record_MX(10, b'example.net', 20))
        # Vary the ttl
        self._equalityTest(
            dns.Record_MX(10, b'example.org', 20),
            dns.Record_MX(10, b'example.org', 20),
            dns.Record_MX(10, b'example.org', 200))


    def test_txt(self):
        """
        Two L{dns.Record_TXT} instances compare equal if and only if they have
        the same data and ttl.
        """
        # Vary the length of the data
        self._equalityTest(
            dns.Record_TXT('foo', 'bar', ttl=10),
            dns.Record_TXT('foo', 'bar', ttl=10),
            dns.Record_TXT('foo', 'bar', 'baz', ttl=10))
        # Vary the value of the data
        self._equalityTest(
            dns.Record_TXT('foo', 'bar', ttl=10),
            dns.Record_TXT('foo', 'bar', ttl=10),
            dns.Record_TXT('bar', 'foo', ttl=10))
        # Vary the ttl
        self._equalityTest(
            dns.Record_TXT('foo', 'bar', ttl=10),
            dns.Record_TXT('foo', 'bar', ttl=10),
            dns.Record_TXT('foo', 'bar', ttl=100))


    def test_spf(self):
        """
        L{dns.Record_SPF} instances compare equal if and only if they have the
        same data and ttl.
        """
        # Vary the length of the data
        self._equalityTest(
            dns.Record_SPF('foo', 'bar', ttl=10),
            dns.Record_SPF('foo', 'bar', ttl=10),
            dns.Record_SPF('foo', 'bar', 'baz', ttl=10))
        # Vary the value of the data
        self._equalityTest(
            dns.Record_SPF('foo', 'bar', ttl=10),
            dns.Record_SPF('foo', 'bar', ttl=10),
            dns.Record_SPF('bar', 'foo', ttl=10))
        # Vary the ttl
        self._equalityTest(
            dns.Record_SPF('foo', 'bar', ttl=10),
            dns.Record_SPF('foo', 'bar', ttl=10),
            dns.Record_SPF('foo', 'bar', ttl=100))


    def test_unknown(self):
        """
        L{dns.UnknownRecord} instances compare equal if and only if they have
        the same data and ttl.
        """
        # Vary the length of the data
        self._equalityTest(
            dns.UnknownRecord('foo', ttl=10),
            dns.UnknownRecord('foo', ttl=10),
            dns.UnknownRecord('foobar', ttl=10))
        # Vary the value of the data
        self._equalityTest(
            dns.UnknownRecord('foo', ttl=10),
            dns.UnknownRecord('foo', ttl=10),
            dns.UnknownRecord('bar', ttl=10))
        # Vary the ttl
        self._equalityTest(
            dns.UnknownRecord('foo', ttl=10),
            dns.UnknownRecord('foo', ttl=10),
            dns.UnknownRecord('foo', ttl=100))



class RRHeaderTests(unittest.TestCase):
    """
    Tests for L{twisted.names.dns.RRHeader}.
    """

    def test_negativeTTL(self):
        """
        Attempting to create a L{dns.RRHeader} instance with a negative TTL
        causes L{ValueError} to be raised.
        """
        self.assertRaises(
            ValueError, dns.RRHeader, "example.com", dns.A,
            dns.IN, -1, dns.Record_A("127.0.0.1"))



class NameToLabelsTests(unittest.SynchronousTestCase):
    """
    Tests for L{twisted.names.dns._nameToLabels}.
    """

    def test_empty(self):
        """
        L{dns._nameToLabels} returns a list containing a single
        empty label for an empty name.
        """
        self.assertEqual(dns._nameToLabels(b''), [b''])


    def test_onlyDot(self):
        """
        L{dns._nameToLabels} returns a list containing a single
        empty label for a name containing only a dot.
        """
        self.assertEqual(dns._nameToLabels(b'.'), [b''])


    def test_withoutTrailingDot(self):
        """
        L{dns._nameToLabels} returns a list ending with an empty
        label for a name without a trailing dot.
        """
        self.assertEqual(dns._nameToLabels(b'com'), [b'com', b''])


    def test_withTrailingDot(self):
        """
        L{dns._nameToLabels} returns a list ending with an empty
        label for a name with a trailing dot.
        """
        self.assertEqual(dns._nameToLabels(b'com.'), [b'com', b''])


    def test_subdomain(self):
        """
        L{dns._nameToLabels} returns a list containing entries
        for all labels in a subdomain name.
        """
        self.assertEqual(
            dns._nameToLabels(b'foo.bar.baz.example.com.'),
            [b'foo', b'bar', b'baz', b'example', b'com', b''])


    def test_casePreservation(self):
        """
        L{dns._nameToLabels} preserves the case of ascii
        characters in labels.
        """
        self.assertEqual(
            dns._nameToLabels(b'EXAMPLE.COM'),
            [b'EXAMPLE', b'COM', b''])



def assertIsSubdomainOf(testCase, descendant, ancestor):
    """
    Assert that C{descendant} *is* a subdomain of C{ancestor}.

    @type testCase: L{unittest.SynchronousTestCase}
    @param testCase: The test case on which to run the assertions.

    @type descendant: C{str}
    @param descendant: The subdomain name to test.

    @type ancestor: C{str}
    @param ancestor: The superdomain name to test.
    """
    testCase.assertTrue(
        dns._isSubdomainOf(descendant, ancestor),
        '%r is not a subdomain of %r' % (descendant, ancestor))



def assertIsNotSubdomainOf(testCase, descendant, ancestor):
    """
    Assert that C{descendant} *is not* a subdomain of C{ancestor}.

    @type testCase: L{unittest.SynchronousTestCase}
    @param testCase: The test case on which to run the assertions.

    @type descendant: C{str}
    @param descendant: The subdomain name to test.

    @type ancestor: C{str}
    @param ancestor: The superdomain name to test.
    """
    testCase.assertFalse(
        dns._isSubdomainOf(descendant, ancestor),
        '%r is a subdomain of %r' % (descendant, ancestor))



class IsSubdomainOfTests(unittest.SynchronousTestCase):
    """
    Tests for L{twisted.names.dns._isSubdomainOf}.
    """

    def test_identical(self):
        """
        L{dns._isSubdomainOf} returns C{True} for identical
        domain names.
        """
        assertIsSubdomainOf(self, b'example.com', b'example.com')


    def test_parent(self):
        """
        L{dns._isSubdomainOf} returns C{True} when the first
        name is an immediate descendant of the second name.
        """
        assertIsSubdomainOf(self, b'foo.example.com', b'example.com')


    def test_distantAncestor(self):
        """
        L{dns._isSubdomainOf} returns C{True} when the first
        name is a distant descendant of the second name.
        """
        assertIsSubdomainOf(self, b'foo.bar.baz.example.com', b'com')


    def test_superdomain(self):
        """
        L{dns._isSubdomainOf} returns C{False} when the first
        name is an ancestor of the second name.
        """
        assertIsNotSubdomainOf(self, b'example.com', b'foo.example.com')


    def test_sibling(self):
        """
        L{dns._isSubdomainOf} returns C{False} if the first name
        is a sibling of the second name.
        """
        assertIsNotSubdomainOf(self, b'foo.example.com', b'bar.example.com')


    def test_unrelatedCommonSuffix(self):
        """
        L{dns._isSubdomainOf} returns C{False} even when domain
        names happen to share a common suffix.
        """
        assertIsNotSubdomainOf(self, b'foo.myexample.com', b'example.com')


    def test_subdomainWithTrailingDot(self):
        """
        L{dns._isSubdomainOf} returns C{True} if the first name
        is a subdomain of the second name but the first name has a
        trailing ".".
        """
        assertIsSubdomainOf(self, b'foo.example.com.', b'example.com')


    def test_superdomainWithTrailingDot(self):
        """
        L{dns._isSubdomainOf} returns C{True} if the first name
        is a subdomain of the second name but the second name has a
        trailing ".".
        """
        assertIsSubdomainOf(self, b'foo.example.com', b'example.com.')


    def test_bothWithTrailingDot(self):
        """
        L{dns._isSubdomainOf} returns C{True} if the first name
        is a subdomain of the second name and both names have a
        trailing ".".
        """
        assertIsSubdomainOf(self, b'foo.example.com.', b'example.com.')


    def test_emptySubdomain(self):
        """
        L{dns._isSubdomainOf} returns C{False} if the first name
        is empty and the second name is not.
        """
        assertIsNotSubdomainOf(self, b'', b'example.com')


    def test_emptySuperdomain(self):
        """
        L{dns._isSubdomainOf} returns C{True} if the second name
        is empty and the first name is not.
        """
        assertIsSubdomainOf(self, b'foo.example.com', b'')


    def test_caseInsensitiveComparison(self):
        """
        L{dns._isSubdomainOf} does case-insensitive comparison
        of name labels.
        """
        assertIsSubdomainOf(self, b'foo.example.com', b'EXAMPLE.COM')

        assertIsSubdomainOf(self, b'FOO.EXAMPLE.COM', b'example.com')



class OPTNonStandardAttributes(object):
    """
    Generate byte and instance representations of an L{dns._OPTHeader}
    where all attributes are set to non-default values.

    For testing whether attributes have really been read from the byte
    string during decoding.
    """
    @classmethod
    def bytes(cls, excludeName=False, excludeOptions=False):
        """
        Return L{bytes} representing an encoded OPT record.

        @param excludeName: A flag that controls whether to exclude
            the name field. This allows a non-standard name to be
            prepended during the test.
        @type excludeName: L{bool}

        @param excludeOptions: A flag that controls whether to exclude
            the RDLEN field. This allows encoded variable options to be
            appended during the test.
        @type excludeOptions: L{bool}

        @return: L{bytes} representing the encoded OPT record returned
            by L{object}.
        """
        rdlen = b'\x00\x00' # RDLEN 0
        if excludeOptions:
            rdlen = b''

        return (
            b'\x00' # 0 root zone
            b'\x00\x29' # type 41
            b'\x02\x00' # udpPayloadsize 512
            b'\x03' # extendedRCODE 3
            b'\x04' # version 4
            b'\x80\x00' # DNSSEC OK 1 + Z
            ) + rdlen


    @classmethod
    def object(cls):
        """
        Return a new L{dns._OPTHeader} instance.

        @return: A L{dns._OPTHeader} instance with attributes that
            match the encoded record returned by L{bytes}.
        """
        return dns._OPTHeader(
            udpPayloadSize=512,
            extendedRCODE=3,
            version=4,
            dnssecOK=1)



class OPTHeaderTests(ComparisonTestsMixin, unittest.TestCase):
    """
    Tests for L{twisted.names.dns._OPTHeader}.
    """
    def test_interface(self):
        """
        L{dns._OPTHeader} implements L{dns.IEncodable}.
        """
        verifyClass(dns.IEncodable, dns._OPTHeader)


    def test_name(self):
        """
        L{dns._OPTHeader.name} is a instance attribute whose value is
        fixed as the root domain
        """
        self.assertEqual(dns._OPTHeader().name, dns.Name(b''))


    def test_nameReadonly(self):
        """
        L{dns._OPTHeader.name} is readonly.
        """
        h = dns._OPTHeader()
        self.assertRaises(
            AttributeError, setattr, h, 'name', dns.Name(b'example.com'))


    def test_type(self):
        """
        L{dns._OPTHeader.type} is an instance attribute with fixed value
        41.
        """
        self.assertEqual(dns._OPTHeader().type, 41)


    def test_typeReadonly(self):
        """
        L{dns._OPTHeader.type} is readonly.
        """
        h = dns._OPTHeader()
        self.assertRaises(
            AttributeError, setattr, h, 'type', dns.A)


    def test_udpPayloadSize(self):
        """
        L{dns._OPTHeader.udpPayloadSize} defaults to 4096 as
        recommended in rfc6891 section-6.2.5.
        """
        self.assertEqual(dns._OPTHeader().udpPayloadSize, 4096)


    def test_udpPayloadSizeOverride(self):
        """
        L{dns._OPTHeader.udpPayloadSize} can be overridden in the
        constructor.
        """
        self.assertEqual(dns._OPTHeader(udpPayloadSize=512).udpPayloadSize, 512)


    def test_extendedRCODE(self):
        """
        L{dns._OPTHeader.extendedRCODE} defaults to 0.
        """
        self.assertEqual(dns._OPTHeader().extendedRCODE, 0)


    def test_extendedRCODEOverride(self):
        """
        L{dns._OPTHeader.extendedRCODE} can be overridden in the
        constructor.
        """
        self.assertEqual(dns._OPTHeader(extendedRCODE=1).extendedRCODE, 1)


    def test_version(self):
        """
        L{dns._OPTHeader.version} defaults to 0.
        """
        self.assertEqual(dns._OPTHeader().version, 0)


    def test_versionOverride(self):
        """
        L{dns._OPTHeader.version} can be overridden in the
        constructor.
        """
        self.assertEqual(dns._OPTHeader(version=1).version, 1)


    def test_dnssecOK(self):
        """
        L{dns._OPTHeader.dnssecOK} defaults to False.
        """
        self.assertEqual(dns._OPTHeader().dnssecOK, False)


    def test_dnssecOKOverride(self):
        """
        L{dns._OPTHeader.dnssecOK} can be overridden in the
        constructor.
        """
        self.assertEqual(dns._OPTHeader(dnssecOK=True).dnssecOK, True)


    def test_options(self):
        """
        L{dns._OPTHeader.options} defaults to empty list.
        """
        self.assertEqual(dns._OPTHeader().options, [])


    def test_optionsOverride(self):
        """
        L{dns._OPTHeader.options} can be overridden in the
        constructor.
        """
        h = dns._OPTHeader(options=[(1, 1, b'\x00')])
        self.assertEqual(h.options, [(1, 1, b'\x00')])


    def test_encode(self):
        """
        L{dns._OPTHeader.encode} packs the header fields and writes
        them to a file like object passed in as an argument.
        """
        b = BytesIO()

        OPTNonStandardAttributes.object().encode(b)
        self.assertEqual(
            b.getvalue(),
            OPTNonStandardAttributes.bytes()
            )


    def test_encodeWithOptions(self):
        """
        L{dns._OPTHeader.options} is a list of L{dns._OPTVariableOption}
        instances which are packed into the rdata area of the header.
        """
        h = OPTNonStandardAttributes.object()
        h.options = [
            dns._OPTVariableOption(1, b'foobarbaz'),
            dns._OPTVariableOption(2, b'qux'),
            ]
        b = BytesIO()

        h.encode(b)
        self.assertEqual(
            b.getvalue(),

            OPTNonStandardAttributes.bytes(excludeOptions=True) + (
                b'\x00\x14' # RDLEN 20

                b'\x00\x01' # OPTION-CODE
                b'\x00\x09' # OPTION-LENGTH
                b'foobarbaz' # OPTION-DATA

                b'\x00\x02' # OPTION-CODE
                b'\x00\x03' # OPTION-LENGTH
                b'qux' # OPTION-DATA
                ))


    def test_decode(self):
        """
        L{dns._OPTHeader.decode} unpacks the header fields from a file
        like object and populates the attributes of an existing
        L{dns._OPTHeader} instance.
        """
        decodedHeader = dns._OPTHeader()
        decodedHeader.decode(BytesIO(OPTNonStandardAttributes.bytes()))

        self.assertEqual(
            decodedHeader,
            OPTNonStandardAttributes.object())


    def test_decodeAllExpectedBytes(self):
        """
        L{dns._OPTHeader.decode} reads all the bytes of the record
        that is being decoded.
        """
        # Check that all the input data has been consumed.
        b = BytesIO(OPTNonStandardAttributes.bytes())

        decodedHeader = dns._OPTHeader()
        decodedHeader.decode(b)

        self.assertEqual(b.tell(), len(b.getvalue()))


    def test_decodeOnlyExpectedBytes(self):
        """
        L{dns._OPTHeader.decode} reads only the bytes from the current
        file position to the end of the record that is being
        decoded. Trailing bytes are not consumed.
        """
        b = BytesIO(OPTNonStandardAttributes.bytes()
                    + b'xxxx') # Trailing bytes

        decodedHeader = dns._OPTHeader()
        decodedHeader.decode(b)

        self.assertEqual(b.tell(), len(b.getvalue())-len(b'xxxx'))


    def test_decodeDiscardsName(self):
        """
        L{dns._OPTHeader.decode} discards the name which is encoded in
        the supplied bytes. The name attribute of the resulting
        L{dns._OPTHeader} instance will always be L{dns.Name(b'')}.
        """
        b = BytesIO(OPTNonStandardAttributes.bytes(excludeName=True)
                    + b'\x07example\x03com\x00')

        h = dns._OPTHeader()
        h.decode(b)
        self.assertEqual(h.name, dns.Name(b''))


    def test_decodeRdlengthTooShort(self):
        """
        L{dns._OPTHeader.decode} raises an exception if the supplied
        RDLEN is too short.
        """
        b = BytesIO(
            OPTNonStandardAttributes.bytes(excludeOptions=True) + (
                b'\x00\x05' # RDLEN 5 Too short - should be 6

                b'\x00\x01' # OPTION-CODE
                b'\x00\x02' # OPTION-LENGTH
                b'\x00\x00' # OPTION-DATA
                ))
        h = dns._OPTHeader()
        self.assertRaises(EOFError, h.decode, b)


    def test_decodeRdlengthTooLong(self):
        """
        L{dns._OPTHeader.decode} raises an exception if the supplied
        RDLEN is too long.
        """
        b = BytesIO(
            OPTNonStandardAttributes.bytes(excludeOptions=True) + (

                b'\x00\x07' # RDLEN 7 Too long - should be 6

                b'\x00\x01' # OPTION-CODE
                b'\x00\x02' # OPTION-LENGTH
                b'\x00\x00' # OPTION-DATA
                ))
        h = dns._OPTHeader()
        self.assertRaises(EOFError, h.decode, b)


    def test_decodeWithOptions(self):
        """
        If the OPT bytes contain variable options,
        L{dns._OPTHeader.decode} will populate a list
        L{dns._OPTHeader.options} with L{dns._OPTVariableOption}
        instances.
        """

        b = BytesIO(
            OPTNonStandardAttributes.bytes(excludeOptions=True) + (

                b'\x00\x14' # RDLEN 20

                b'\x00\x01' # OPTION-CODE
                b'\x00\x09' # OPTION-LENGTH
                b'foobarbaz' # OPTION-DATA

                b'\x00\x02' # OPTION-CODE
                b'\x00\x03' # OPTION-LENGTH
                b'qux' # OPTION-DATA
                ))

        h = dns._OPTHeader()
        h.decode(b)
        self.assertEqual(
            h.options,
            [dns._OPTVariableOption(1, b'foobarbaz'),
             dns._OPTVariableOption(2, b'qux'),]
            )


    def test_fromRRHeader(self):
        """
        L{_OPTHeader.fromRRHeader} accepts an L{RRHeader} instance and
        returns an L{_OPTHeader} instance whose attribute values have
        been derived from the C{cls}, C{ttl} and C{payload} attributes
        of the original header.
        """
        genericHeader = dns.RRHeader(
            b'example.com',
            type=dns.OPT,
            cls=0xffff,
            ttl=(0xfe << 24
                 | 0xfd << 16
                 | True << 15),
            payload=dns.UnknownRecord(b'\xff\xff\x00\x03abc'))

        decodedOptHeader = dns._OPTHeader.fromRRHeader(genericHeader)

        expectedOptHeader = dns._OPTHeader(
            udpPayloadSize=0xffff,
            extendedRCODE=0xfe,
            version=0xfd,
            dnssecOK=1,
            options=[dns._OPTVariableOption(code=0xffff, data=b'abc')])

        self.assertEqual(decodedOptHeader, expectedOptHeader)


    def test_repr(self):
        """
        L{dns._OPTHeader.__repr__} displays the name and type and all
        the fixed and extended header values of the OPT record.
        """
        self.assertEqual(
            repr(dns._OPTHeader()),
            '<_OPTHeader '
            'name= '
            'type=41 '
            'udpPayloadSize=4096 '
            'extendedRCODE=0 '
            'version=0 '
            'dnssecOK=False '
            'options=[]>')


    def test_equalityUdpPayloadSize(self):
        """
        Two L{OPTHeader} instances compare equal if they have the same
        udpPayloadSize.
        """
        self.assertNormalEqualityImplementation(
            dns._OPTHeader(udpPayloadSize=512),
            dns._OPTHeader(udpPayloadSize=512),
            dns._OPTHeader(udpPayloadSize=4096))


    def test_equalityExtendedRCODE(self):
        """
        Two L{OPTHeader} instances compare equal if they have the same
        extendedRCODE.
        """
        self.assertNormalEqualityImplementation(
            dns._OPTHeader(extendedRCODE=1),
            dns._OPTHeader(extendedRCODE=1),
            dns._OPTHeader(extendedRCODE=2))


    def test_equalityVersion(self):
        """
        Two L{OPTHeader} instances compare equal if they have the same
        version.
        """
        self.assertNormalEqualityImplementation(
            dns._OPTHeader(version=1),
            dns._OPTHeader(version=1),
            dns._OPTHeader(version=2))


    def test_equalityDnssecOK(self):
        """
        Two L{OPTHeader} instances compare equal if they have the same
        dnssecOK flags.
        """
        self.assertNormalEqualityImplementation(
            dns._OPTHeader(dnssecOK=1),
            dns._OPTHeader(dnssecOK=1),
            dns._OPTHeader(dnssecOK=0))


    def test_equalityOptions(self):
        """
        Two L{OPTHeader} instances compare equal if they have the same
        options.
        """
        self.assertNormalEqualityImplementation(
            dns._OPTHeader(options=[dns._OPTVariableOption(1, b'x')]),
            dns._OPTHeader(options=[dns._OPTVariableOption(1, b'x')]),
            dns._OPTHeader(options=[dns._OPTVariableOption(2, b'y')]))



class OPTVariableOptionTests(ComparisonTestsMixin, unittest.TestCase):
    """
    Tests for L{dns._OPTVariableOption}.
    """
    def test_interface(self):
        """
        L{dns._OPTVariableOption} implements L{dns.IEncodable}.
        """
        verifyClass(dns.IEncodable, dns._OPTVariableOption)


    def test_constructorArguments(self):
        """
        L{dns._OPTVariableOption.__init__} requires code and data
        arguments which are saved as public instance attributes.
        """
        h = dns._OPTVariableOption(1, b'x')
        self.assertEqual(h.code, 1)
        self.assertEqual(h.data, b'x')


    def test_repr(self):
        """
        L{dns._OPTVariableOption.__repr__} displays the code and data
        of the option.
        """
        self.assertEqual(
            repr(dns._OPTVariableOption(1, b'x')),
            '<_OPTVariableOption '
            'code=1 '
            "data=x"
            '>')


    def test_equality(self):
        """
        Two OPTVariableOption instances compare equal if they have the same
        code and data values.
        """
        self.assertNormalEqualityImplementation(
            dns._OPTVariableOption(1, b'x'),
            dns._OPTVariableOption(1, b'x'),
            dns._OPTVariableOption(2, b'x'))

        self.assertNormalEqualityImplementation(
            dns._OPTVariableOption(1, b'x'),
            dns._OPTVariableOption(1, b'x'),
            dns._OPTVariableOption(1, b'y'))


    def test_encode(self):
        """
        L{dns._OPTVariableOption.encode} encodes the code and data
        instance attributes to a byte string which also includes the
        data length.
        """
        o = dns._OPTVariableOption(1, b'foobar')
        b = BytesIO()
        o.encode(b)
        self.assertEqual(
            b.getvalue(),
            b'\x00\x01' # OPTION-CODE 1
            b'\x00\x06' # OPTION-LENGTH 6
            b'foobar' # OPTION-DATA
            )


    def test_decode(self):
        """
        L{dns._OPTVariableOption.decode} is a classmethod that decodes
        a byte string and returns a L{dns._OPTVariableOption} instance.
        """
        b = BytesIO(
            b'\x00\x01' # OPTION-CODE 1
            b'\x00\x06' # OPTION-LENGTH 6
            b'foobar' # OPTION-DATA
            )

        o = dns._OPTVariableOption()
        o.decode(b)
        self.assertEqual(o.code, 1)
        self.assertEqual(o.data, b'foobar')
