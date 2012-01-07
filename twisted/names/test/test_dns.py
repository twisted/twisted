# test-case-name: twisted.names.test.test_dns
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for twisted.names.dns.
"""

from cStringIO import StringIO

import struct

from twisted.python.failure import Failure
from twisted.internet import address, task
from twisted.internet.error import CannotListenError, ConnectionDone
from twisted.trial import unittest
from twisted.names import dns

from twisted.test import proto_helpers

RECORD_TYPES = [
    dns.Record_NS, dns.Record_MD, dns.Record_MF, dns.Record_CNAME,
    dns.Record_MB, dns.Record_MG, dns.Record_MR, dns.Record_PTR,
    dns.Record_DNAME, dns.Record_A, dns.Record_SOA, dns.Record_NULL,
    dns.Record_WKS, dns.Record_SRV, dns.Record_AFSDB, dns.Record_RP,
    dns.Record_HINFO, dns.Record_MINFO, dns.Record_MX, dns.Record_TXT,
    dns.Record_AAAA, dns.Record_A6, dns.Record_NAPTR, dns.UnknownRecord,
    ]

class NameTests(unittest.TestCase):
    """
    Tests for L{Name}, the representation of a single domain name with support
    for encoding into and decoding from DNS message format.
    """
    def test_decode(self):
        """
        L{Name.decode} populates the L{Name} instance with name information read
        from the file-like object passed to it.
        """
        n = dns.Name()
        n.decode(StringIO("\x07example\x03com\x00"))
        self.assertEqual(n.name, "example.com")


    def test_encode(self):
        """
        L{Name.encode} encodes its name information and writes it to the
        file-like object passed to it.
        """
        name = dns.Name("foo.example.com")
        stream = StringIO()
        name.encode(stream)
        self.assertEqual(stream.getvalue(), "\x03foo\x07example\x03com\x00")


    def test_encodeWithCompression(self):
        """
        If a compression dictionary is passed to it, L{Name.encode} uses offset
        information from it to encode its name with references to existing
        labels in the stream instead of including another copy of them in the
        output.  It also updates the compression dictionary with the location of
        the name it writes to the stream.
        """
        name = dns.Name("foo.example.com")
        compression = {"example.com": 0x17}

        # Some bytes already encoded into the stream for this message
        previous = "some prefix to change .tell()"
        stream = StringIO()
        stream.write(previous)

        # The position at which the encoded form of this new name will appear in
        # the stream.
        expected = len(previous) + dns.Message.headerSize
        name.encode(stream, compression)
        self.assertEqual(
            "\x03foo\xc0\x17",
            stream.getvalue()[len(previous):])
        self.assertEqual(
            {"example.com": 0x17, "foo.example.com": expected},
            compression)


    def test_unknown(self):
        """
        A resource record of unknown type and class is parsed into an
        L{UnknownRecord} instance with its data preserved, and an
        L{UnknownRecord} instance is serialized to a string equal to the one it
        was parsed from.
        """
        wire = (
            '\x01\x00' # Message ID
            '\x00' # answer bit, opCode nibble, auth bit, trunc bit, recursive
                   # bit
            '\x00' # recursion bit, empty bit, empty bit, empty bit, response
                   # code nibble
            '\x00\x01' # number of queries
            '\x00\x01' # number of answers
            '\x00\x00' # number of authorities
            '\x00\x01' # number of additionals

            # query
            '\x03foo\x03bar\x00'    # foo.bar
            '\xde\xad'              # type=0xdead
            '\xbe\xef'              # cls=0xbeef

            # 1st answer
            '\xc0\x0c'              # foo.bar - compressed
            '\xde\xad'              # type=0xdead
            '\xbe\xef'              # cls=0xbeef
            '\x00\x00\x01\x01'      # ttl=257
            '\x00\x08somedata'      # some payload data

            # 1st additional
            '\x03baz\x03ban\x00'    # baz.ban
            '\x00\x01'              # type=A
            '\x00\x01'              # cls=IN
            '\x00\x00\x01\x01'      # ttl=257
            '\x00\x04'              # len=4
            '\x01\x02\x03\x04'      # 1.2.3.4

            )

        msg = dns.Message()
        msg.fromStr(wire)

        self.assertEqual(msg.queries, [
                dns.Query('foo.bar', type=0xdead, cls=0xbeef),
                ])
        self.assertEqual(msg.answers, [
                dns.RRHeader('foo.bar', type=0xdead, cls=0xbeef, ttl=257,
                             payload=dns.UnknownRecord('somedata', ttl=257)),
                ])
        self.assertEqual(msg.additional, [
                dns.RRHeader('baz.ban', type=dns.A, cls=dns.IN, ttl=257,
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
        stream = StringIO(
            "x" * 20 +
            "\x01f\x03isi\x04arpa\x00"
            "\x03foo\xc0\x14"
            "\x03bar\xc0\x20")
        stream.seek(20)
        name = dns.Name()
        name.decode(stream)
        # Verify we found the first name in the stream and that the stream
        # position is left at the first byte after the decoded name.
        self.assertEqual("f.isi.arpa", name.name)
        self.assertEqual(32, stream.tell())

        # Get the second name from the stream and make the same assertions.
        name.decode(stream)
        self.assertEqual(name.name, "foo.f.isi.arpa")
        self.assertEqual(38, stream.tell())

        # Get the third and final name
        name.decode(stream)
        self.assertEqual(name.name, "bar.foo.f.isi.arpa")
        self.assertEqual(44, stream.tell())


    def test_rejectCompressionLoop(self):
        """
        L{Name.decode} raises L{ValueError} if the stream passed to it includes
        a compression pointer which forms a loop, causing the name to be
        undecodable.
        """
        name = dns.Name()
        stream = StringIO("\xc0\x00")
        self.assertRaises(ValueError, name.decode, stream)



class RoundtripDNSTestCase(unittest.TestCase):
    """Encoding and then decoding various objects."""

    names = ["example.org", "go-away.fish.tv", "23strikesback.net"]

    def testName(self):
        for n in self.names:
            # encode the name
            f = StringIO()
            dns.Name(n).encode(f)

            # decode the name
            f.seek(0, 0)
            result = dns.Name()
            result.decode(f)
            self.assertEqual(result.name, n)

    def testQuery(self):
        for n in self.names:
            for dnstype in range(1, 17):
                for dnscls in range(1, 5):
                    # encode the query
                    f = StringIO()
                    dns.Query(n, dnstype, dnscls).encode(f)

                    # decode the result
                    f.seek(0, 0)
                    result = dns.Query()
                    result.decode(f)
                    self.assertEqual(result.name.name, n)
                    self.assertEqual(result.type, dnstype)
                    self.assertEqual(result.cls, dnscls)

    def testRR(self):
        # encode the RR
        f = StringIO()
        dns.RRHeader("test.org", 3, 4, 17).encode(f)

        # decode the result
        f.seek(0, 0)
        result = dns.RRHeader()
        result.decode(f)
        self.assertEqual(str(result.name), "test.org")
        self.assertEqual(result.type, 3)
        self.assertEqual(result.cls, 4)
        self.assertEqual(result.ttl, 17)


    def testResources(self):
        names = (
            "this.are.test.name",
            "will.compress.will.this.will.name.will.hopefully",
            "test.CASE.preSErVatIOn.YeAH",
            "a.s.h.o.r.t.c.a.s.e.t.o.t.e.s.t",
            "singleton"
        )
        for s in names:
            f = StringIO()
            dns.SimpleRecord(s).encode(f)
            f.seek(0, 0)
            result = dns.SimpleRecord()
            result.decode(f)
            self.assertEqual(str(result.name), s)

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
            f = StringIO()
            dns.Charstr(n).encode(f)

            # decode the name
            f.seek(0, 0)
            result = dns.Charstr()
            result.decode(f)
            self.assertEqual(result.string, n)


    def test_NAPTR(self):
        """
        Test L{dns.Record_NAPTR} encode and decode.
        """
        naptrs = [(100, 10, "u", "sip+E2U",
                   "!^.*$!sip:information@domain.tld!", ""),
                  (100, 50, "s", "http+I2L+I2C+I2R", "",
                   "_http._tcp.gatech.edu")]

        for (order, preference, flags, service, regexp, replacement) in naptrs:
            rin = dns.Record_NAPTR(order, preference, flags, service, regexp,
                                   replacement)
            e = StringIO()
            rin.encode(e)
            e.seek(0,0)
            rout = dns.Record_NAPTR()
            rout.decode(e)
            self.assertEqual(rin.order, rout.order)
            self.assertEqual(rin.preference, rout.preference)
            self.assertEqual(rin.flags, rout.flags)
            self.assertEqual(rin.service, rout.service)
            self.assertEqual(rin.regexp, rout.regexp)
            self.assertEqual(rin.replacement.name, rout.replacement.name)
            self.assertEqual(rin.ttl, rout.ttl)



class MessageTestCase(unittest.TestCase):
    """
    Tests for L{twisted.names.dns.Message}.
    """

    def testEmptyMessage(self):
        """
        Test that a message which has been truncated causes an EOFError to
        be raised when it is parsed.
        """
        msg = dns.Message()
        self.assertRaises(EOFError, msg.fromStr, '')


    def testEmptyQuery(self):
        """
        Test that bytes representing an empty query message can be decoded
        as such.
        """
        msg = dns.Message()
        msg.fromStr(
            '\x01\x00' # Message ID
            '\x00' # answer bit, opCode nibble, auth bit, trunc bit, recursive bit
            '\x00' # recursion bit, empty bit, empty bit, empty bit, response code nibble
            '\x00\x00' # number of queries
            '\x00\x00' # number of answers
            '\x00\x00' # number of authorities
            '\x00\x00' # number of additionals
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


    def testNULL(self):
        bytes = ''.join([chr(i) for i in range(256)])
        rec = dns.Record_NULL(bytes)
        rr = dns.RRHeader('testname', dns.NULL, payload=rec)
        msg1 = dns.Message()
        msg1.answers.append(rr)
        s = StringIO()
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
        buf = StringIO()
        answer = dns.RRHeader(payload=dns.Record_A('1.2.3.4', ttl=0))
        answer.encode(buf)
        message = dns.Message()
        message.fromStr(
            '\x01\x00' # Message ID
            # answer bit, opCode nibble, auth bit, trunc bit, recursive bit
            '\x00'
            # recursion bit, empty bit, empty bit, empty bit, response code
            # nibble
            '\x00'
            '\x00\x00' # number of queries
            '\x00\x01' # number of answers
            '\x00\x00' # number of authorities
            '\x00\x00' # number of additionals
            + buf.getvalue()
            )
        self.assertEqual(message.answers, [answer])
        self.assertFalse(message.answers[0].auth)


    def test_authoritativeMessage(self):
        """
        The L{RRHeader} instances created by L{Message} from an authoritative
        message are marked as authoritative.
        """
        buf = StringIO()
        answer = dns.RRHeader(payload=dns.Record_A('1.2.3.4', ttl=0))
        answer.encode(buf)
        message = dns.Message()
        message.fromStr(
            '\x01\x00' # Message ID
            # answer bit, opCode nibble, auth bit, trunc bit, recursive bit
            '\x04'
            # recursion bit, empty bit, empty bit, empty bit, response code
            # nibble
            '\x00'
            '\x00\x00' # number of queries
            '\x00\x01' # number of answers
            '\x00\x00' # number of authorities
            '\x00\x00' # number of additionals
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


    def messageReceived(self, msg, proto, addr):
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
        self.proto.datagramReceived('',
            address.IPv4Address('UDP', '127.0.0.1', 12345))
        self.assertEqual(self.controller.messages, [])


    def test_simpleQuery(self):
        """
        Test content received after a query.
        """
        d = self.proto.query(('127.0.0.1', 21345), [dns.Query('foo')])
        self.assertEqual(len(self.proto.liveMessages.keys()), 1)
        m = dns.Message()
        m.id = self.proto.liveMessages.items()[0][0]
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
        d = self.proto.query(('127.0.0.1', 21345), [dns.Query('foo')])
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

        d = self.proto.query(('127.0.0.1', 21345), [dns.Query('foo')])
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

        d = self.proto.query(('127.0.0.1', 21345), [dns.Query('foo')])
        return self.assertFailure(d, CannotListenError)



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
        d = self.proto.query([dns.Query('foo')])
        self.assertEqual(len(self.proto.liveMessages), 1)
        self.clock.advance(60)
        self.assertFailure(d, dns.DNSQueryTimeoutError)
        self.assertEqual(len(self.proto.liveMessages), 0)
        return d


    def test_simpleQuery(self):
        """
        Test content received after a query.
        """
        d = self.proto.query([dns.Query('foo')])
        self.assertEqual(len(self.proto.liveMessages.keys()), 1)
        m = dns.Message()
        m.id = self.proto.liveMessages.items()[0][0]
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

        d = self.proto.query([dns.Query('foo')])
        return self.assertFailure(d, RuntimeError)



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
            repr(dns.Record_NS('example.com', 4321)),
            "<NS name=example.com ttl=4321>")


    def test_md(self):
        """
        The repr of a L{dns.Record_MD} instance includes the name of the
        mail destination and the TTL of the record.
        """
        self.assertEqual(
            repr(dns.Record_MD('example.com', 4321)),
            "<MD name=example.com ttl=4321>")


    def test_mf(self):
        """
        The repr of a L{dns.Record_MF} instance includes the name of the
        mail forwarder and the TTL of the record.
        """
        self.assertEqual(
            repr(dns.Record_MF('example.com', 4321)),
            "<MF name=example.com ttl=4321>")


    def test_cname(self):
        """
        The repr of a L{dns.Record_CNAME} instance includes the name of the
        mail forwarder and the TTL of the record.
        """
        self.assertEqual(
            repr(dns.Record_CNAME('example.com', 4321)),
            "<CNAME name=example.com ttl=4321>")


    def test_mb(self):
        """
        The repr of a L{dns.Record_MB} instance includes the name of the
        mailbox and the TTL of the record.
        """
        self.assertEqual(
            repr(dns.Record_MB('example.com', 4321)),
            "<MB name=example.com ttl=4321>")


    def test_mg(self):
        """
        The repr of a L{dns.Record_MG} instance includes the name of the
        mail group memeber and the TTL of the record.
        """
        self.assertEqual(
            repr(dns.Record_MG('example.com', 4321)),
            "<MG name=example.com ttl=4321>")


    def test_mr(self):
        """
        The repr of a L{dns.Record_MR} instance includes the name of the
        mail rename domain and the TTL of the record.
        """
        self.assertEqual(
            repr(dns.Record_MR('example.com', 4321)),
            "<MR name=example.com ttl=4321>")


    def test_ptr(self):
        """
        The repr of a L{dns.Record_PTR} instance includes the name of the
        pointer and the TTL of the record.
        """
        self.assertEqual(
            repr(dns.Record_PTR('example.com', 4321)),
            "<PTR name=example.com ttl=4321>")


    def test_dname(self):
        """
        The repr of a L{dns.Record_DNAME} instance includes the name of the
        non-terminal DNS name redirection and the TTL of the record.
        """
        self.assertEqual(
            repr(dns.Record_DNAME('example.com', 4321)),
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
            repr(dns.Record_SOA(mname='mName', rname='rName', serial=123,
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
            repr(dns.Record_NULL('abcd', 123)),
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
            repr(dns.Record_A6(0, '1234::5678', 'foo.bar', ttl=10)),
            "<A6 suffix=1234::5678 prefix=foo.bar ttl=10>")


    def test_srv(self):
        """
        The repr of a L{dns.Record_SRV} instance includes the name and port of
        the target and the priority, weight, and TTL of the record.
        """
        self.assertEqual(
            repr(dns.Record_SRV(1, 2, 3, 'example.org', 4)),
            "<SRV priority=1 weight=2 target=example.org port=3 ttl=4>")


    def test_naptr(self):
        """
        The repr of a L{dns.Record_NAPTR} instance includes the order,
        preference, flags, service, regular expression, replacement, and TTL of
        the record.
        """
        self.assertEqual(
            repr(dns.Record_NAPTR(5, 9, "S", "http", "/foo/bar/i", "baz", 3)),
            "<NAPTR order=5 preference=9 flags=S service=http "
            "regexp=/foo/bar/i replacement=baz ttl=3>")


    def test_afsdb(self):
        """
        The repr of a L{dns.Record_AFSDB} instance includes the subtype,
        hostname, and TTL of the record.
        """
        self.assertEqual(
            repr(dns.Record_AFSDB(3, 'example.org', 5)),
            "<AFSDB subtype=3 hostname=example.org ttl=5>")


    def test_rp(self):
        """
        The repr of a L{dns.Record_RP} instance includes the mbox, txt, and TTL
        fields of the record.
        """
        self.assertEqual(
            repr(dns.Record_RP('alice.example.com', 'admin.example.com', 3)),
            "<RP mbox=alice.example.com txt=admin.example.com ttl=3>")


    def test_hinfo(self):
        """
        The repr of a L{dns.Record_HINFO} instance includes the cpu, os, and
        TTL fields of the record.
        """
        self.assertEqual(
            repr(dns.Record_HINFO('sparc', 'minix', 12)),
            "<HINFO cpu='sparc' os='minix' ttl=12>")


    def test_minfo(self):
        """
        The repr of a L{dns.Record_MINFO} instance includes the rmailbx,
        emailbx, and TTL fields of the record.
        """
        self.assertEqual(
            repr(dns.Record_MINFO('alice.example.com', 'bob.example.com', 15)),
            "<MINFO responsibility=alice.example.com "
            "errors=bob.example.com ttl=15>")


    def test_mx(self):
        """
        The repr of a L{dns.Record_MX} instance includes the preference, name,
        and TTL fields of the record.
        """
        self.assertEqual(
            repr(dns.Record_MX(13, 'mx.example.com', 2)),
            "<MX preference=13 name=mx.example.com ttl=2>")


    def test_txt(self):
        """
        The repr of a L{dns.Record_TXT} instance includes the data and ttl
        fields of the record.
        """
        self.assertEqual(
            repr(dns.Record_TXT("foo", "bar", ttl=15)),
            "<TXT data=['foo', 'bar'] ttl=15>")


    def test_spf(self):
        """
        The repr of a L{dns.Record_SPF} instance includes the data and ttl
        fields of the record.
        """
        self.assertEqual(
            repr(dns.Record_SPF("foo", "bar", ttl=15)),
            "<SPF data=['foo', 'bar'] ttl=15>")


    def test_unknown(self):
        """
        The repr of a L{dns.UnknownRecord} instance includes the data and ttl
        fields of the record.
        """
        self.assertEqual(
            repr(dns.UnknownRecord("foo\x1fbar", 12)),
            "<UNKNOWN data='foo\\x1fbar' ttl=12>")



class _Equal(object):
    """
    A class the instances of which are equal to anything and everything.
    """
    def __eq__(self, other):
        return True


    def __ne__(self, other):
        return False



class _NotEqual(object):
    """
    A class the instances of which are equal to nothing.
    """
    def __eq__(self, other):
        return False


    def __ne__(self, other):
        return True



class EqualityTests(unittest.TestCase):
    """
    Tests for the equality and non-equality behavior of record classes.
    """
    def _equalityTest(self, firstValueOne, secondValueOne, valueTwo):
        """
        Assert that C{firstValueOne} is equal to C{secondValueOne} but not
        equal to C{valueOne} and that it defines equality cooperatively with
        other types it doesn't know about.
        """
        # This doesn't use assertEqual and assertNotEqual because the exact
        # operator those functions use is not very well defined.  The point
        # of these assertions is to check the results of the use of specific
        # operators (precisely to ensure that using different permutations
        # (eg "x == y" or "not (x != y)") which should yield the same results
        # actually does yield the same result). -exarkun
        self.assertTrue(firstValueOne == firstValueOne)
        self.assertTrue(firstValueOne == secondValueOne)
        self.assertFalse(firstValueOne == valueTwo)
        self.assertFalse(firstValueOne != firstValueOne)
        self.assertFalse(firstValueOne != secondValueOne)
        self.assertTrue(firstValueOne != valueTwo)
        self.assertTrue(firstValueOne == _Equal())
        self.assertFalse(firstValueOne != _Equal())
        self.assertFalse(firstValueOne == _NotEqual())
        self.assertTrue(firstValueOne != _NotEqual())


    def _simpleEqualityTest(self, cls):
        # Vary the TTL
        self._equalityTest(
            cls('example.com', 123),
            cls('example.com', 123),
            cls('example.com', 321))
        # Vary the name
        self._equalityTest(
            cls('example.com', 123),
            cls('example.com', 123),
            cls('example.org', 123))


    def test_rrheader(self):
        """
        Two L{dns.RRHeader} instances compare equal if and only if they have
        the same name, type, class, time to live, payload, and authoritative
        bit.
        """
        # Vary the name
        self._equalityTest(
            dns.RRHeader('example.com', payload=dns.Record_A('1.2.3.4')),
            dns.RRHeader('example.com', payload=dns.Record_A('1.2.3.4')),
            dns.RRHeader('example.org', payload=dns.Record_A('1.2.3.4')))

        # Vary the payload
        self._equalityTest(
            dns.RRHeader('example.com', payload=dns.Record_A('1.2.3.4')),
            dns.RRHeader('example.com', payload=dns.Record_A('1.2.3.4')),
            dns.RRHeader('example.com', payload=dns.Record_A('1.2.3.5')))

        # Vary the type.  Leave the payload as None so that we don't have to
        # provide non-equal values.
        self._equalityTest(
            dns.RRHeader('example.com', dns.A),
            dns.RRHeader('example.com', dns.A),
            dns.RRHeader('example.com', dns.MX))

        # Probably not likely to come up.  Most people use the internet.
        self._equalityTest(
            dns.RRHeader('example.com', cls=dns.IN, payload=dns.Record_A('1.2.3.4')),
            dns.RRHeader('example.com', cls=dns.IN, payload=dns.Record_A('1.2.3.4')),
            dns.RRHeader('example.com', cls=dns.CS, payload=dns.Record_A('1.2.3.4')))

        # Vary the ttl
        self._equalityTest(
            dns.RRHeader('example.com', ttl=60, payload=dns.Record_A('1.2.3.4')),
            dns.RRHeader('example.com', ttl=60, payload=dns.Record_A('1.2.3.4')),
            dns.RRHeader('example.com', ttl=120, payload=dns.Record_A('1.2.3.4')))

        # Vary the auth bit
        self._equalityTest(
            dns.RRHeader('example.com', auth=1, payload=dns.Record_A('1.2.3.4')),
            dns.RRHeader('example.com', auth=1, payload=dns.Record_A('1.2.3.4')),
            dns.RRHeader('example.com', auth=0, payload=dns.Record_A('1.2.3.4')))


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
            dns.Record_SOA('mname', 'rname', 123, 456, 789, 10, 20, 30),
            dns.Record_SOA('mname', 'rname', 123, 456, 789, 10, 20, 30),
            dns.Record_SOA('xname', 'rname', 123, 456, 789, 10, 20, 30))
        # Vary the rname
        self._equalityTest(
            dns.Record_SOA('mname', 'rname', 123, 456, 789, 10, 20, 30),
            dns.Record_SOA('mname', 'rname', 123, 456, 789, 10, 20, 30),
            dns.Record_SOA('mname', 'xname', 123, 456, 789, 10, 20, 30))
        # Vary the serial
        self._equalityTest(
            dns.Record_SOA('mname', 'rname', 123, 456, 789, 10, 20, 30),
            dns.Record_SOA('mname', 'rname', 123, 456, 789, 10, 20, 30),
            dns.Record_SOA('mname', 'rname', 1, 456, 789, 10, 20, 30))
        # Vary the refresh
        self._equalityTest(
            dns.Record_SOA('mname', 'rname', 123, 456, 789, 10, 20, 30),
            dns.Record_SOA('mname', 'rname', 123, 456, 789, 10, 20, 30),
            dns.Record_SOA('mname', 'rname', 123, 1, 789, 10, 20, 30))
        # Vary the minimum
        self._equalityTest(
            dns.Record_SOA('mname', 'rname', 123, 456, 789, 10, 20, 30),
            dns.Record_SOA('mname', 'rname', 123, 456, 789, 10, 20, 30),
            dns.Record_SOA('mname', 'rname', 123, 456, 1, 10, 20, 30))
        # Vary the expire
        self._equalityTest(
            dns.Record_SOA('mname', 'rname', 123, 456, 789, 10, 20, 30),
            dns.Record_SOA('mname', 'rname', 123, 456, 789, 10, 20, 30),
            dns.Record_SOA('mname', 'rname', 123, 456, 789, 1, 20, 30))
        # Vary the retry
        self._equalityTest(
            dns.Record_SOA('mname', 'rname', 123, 456, 789, 10, 20, 30),
            dns.Record_SOA('mname', 'rname', 123, 456, 789, 10, 20, 30),
            dns.Record_SOA('mname', 'rname', 123, 456, 789, 10, 1, 30))
        # Vary the ttl
        self._equalityTest(
            dns.Record_SOA('mname', 'rname', 123, 456, 789, 10, 20, 30),
            dns.Record_SOA('mname', 'rname', 123, 456, 789, 10, 20, 30),
            dns.Record_SOA('mname', 'xname', 123, 456, 789, 10, 20, 1))


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
            dns.Record_A6(16, '::abcd', 'example.com', 10),
            dns.Record_A6(16, '::abcd', 'example.com', 10),
            dns.Record_A6(32, '::abcd', 'example.com', 10))
        # Vary the suffix
        self._equalityTest(
            dns.Record_A6(16, '::abcd', 'example.com', 10),
            dns.Record_A6(16, '::abcd', 'example.com', 10),
            dns.Record_A6(16, '::abcd:0', 'example.com', 10))
        # Vary the prefix
        self._equalityTest(
            dns.Record_A6(16, '::abcd', 'example.com', 10),
            dns.Record_A6(16, '::abcd', 'example.com', 10),
            dns.Record_A6(16, '::abcd', 'example.org', 10))
        # Vary the ttl
        self._equalityTest(
            dns.Record_A6(16, '::abcd', 'example.com', 10),
            dns.Record_A6(16, '::abcd', 'example.com', 10),
            dns.Record_A6(16, '::abcd', 'example.com', 100))


    def test_srv(self):
        """
        Two L{dns.Record_SRV} instances compare equal if and only if they have
        the same priority, weight, port, target, and ttl.
        """
        # Vary the priority
        self._equalityTest(
            dns.Record_SRV(10, 20, 30, 'example.com', 40),
            dns.Record_SRV(10, 20, 30, 'example.com', 40),
            dns.Record_SRV(100, 20, 30, 'example.com', 40))
        # Vary the weight
        self._equalityTest(
            dns.Record_SRV(10, 20, 30, 'example.com', 40),
            dns.Record_SRV(10, 20, 30, 'example.com', 40),
            dns.Record_SRV(10, 200, 30, 'example.com', 40))
        # Vary the port
        self._equalityTest(
            dns.Record_SRV(10, 20, 30, 'example.com', 40),
            dns.Record_SRV(10, 20, 30, 'example.com', 40),
            dns.Record_SRV(10, 20, 300, 'example.com', 40))
        # Vary the target
        self._equalityTest(
            dns.Record_SRV(10, 20, 30, 'example.com', 40),
            dns.Record_SRV(10, 20, 30, 'example.com', 40),
            dns.Record_SRV(10, 20, 30, 'example.org', 40))
        # Vary the ttl
        self._equalityTest(
            dns.Record_SRV(10, 20, 30, 'example.com', 40),
            dns.Record_SRV(10, 20, 30, 'example.com', 40),
            dns.Record_SRV(10, 20, 30, 'example.com', 400))


    def test_naptr(self):
        """
        Two L{dns.Record_NAPTR} instances compare equal if and only if they
        have the same order, preference, flags, service, regexp, replacement,
        and ttl.
        """
        # Vary the order
        self._equalityTest(
            dns.Record_NAPTR(1, 2, "u", "sip+E2U", "/foo/bar/", "baz", 12),
            dns.Record_NAPTR(1, 2, "u", "sip+E2U", "/foo/bar/", "baz", 12),
            dns.Record_NAPTR(2, 2, "u", "sip+E2U", "/foo/bar/", "baz", 12))
        # Vary the preference
        self._equalityTest(
            dns.Record_NAPTR(1, 2, "u", "sip+E2U", "/foo/bar/", "baz", 12),
            dns.Record_NAPTR(1, 2, "u", "sip+E2U", "/foo/bar/", "baz", 12),
            dns.Record_NAPTR(1, 3, "u", "sip+E2U", "/foo/bar/", "baz", 12))
        # Vary the flags
        self._equalityTest(
            dns.Record_NAPTR(1, 2, "u", "sip+E2U", "/foo/bar/", "baz", 12),
            dns.Record_NAPTR(1, 2, "u", "sip+E2U", "/foo/bar/", "baz", 12),
            dns.Record_NAPTR(1, 2, "p", "sip+E2U", "/foo/bar/", "baz", 12))
        # Vary the service
        self._equalityTest(
            dns.Record_NAPTR(1, 2, "u", "sip+E2U", "/foo/bar/", "baz", 12),
            dns.Record_NAPTR(1, 2, "u", "sip+E2U", "/foo/bar/", "baz", 12),
            dns.Record_NAPTR(1, 2, "u", "http", "/foo/bar/", "baz", 12))
        # Vary the regexp
        self._equalityTest(
            dns.Record_NAPTR(1, 2, "u", "sip+E2U", "/foo/bar/", "baz", 12),
            dns.Record_NAPTR(1, 2, "u", "sip+E2U", "/foo/bar/", "baz", 12),
            dns.Record_NAPTR(1, 2, "u", "sip+E2U", "/bar/foo/", "baz", 12))
        # Vary the replacement
        self._equalityTest(
            dns.Record_NAPTR(1, 2, "u", "sip+E2U", "/foo/bar/", "baz", 12),
            dns.Record_NAPTR(1, 2, "u", "sip+E2U", "/foo/bar/", "baz", 12),
            dns.Record_NAPTR(1, 2, "u", "sip+E2U", "/bar/foo/", "quux", 12))
        # Vary the ttl
        self._equalityTest(
            dns.Record_NAPTR(1, 2, "u", "sip+E2U", "/foo/bar/", "baz", 12),
            dns.Record_NAPTR(1, 2, "u", "sip+E2U", "/foo/bar/", "baz", 12),
            dns.Record_NAPTR(1, 2, "u", "sip+E2U", "/bar/foo/", "baz", 5))


    def test_afsdb(self):
        """
        Two L{dns.Record_AFSDB} instances compare equal if and only if they
        have the same subtype, hostname, and ttl.
        """
        # Vary the subtype
        self._equalityTest(
            dns.Record_AFSDB(1, 'example.com', 2),
            dns.Record_AFSDB(1, 'example.com', 2),
            dns.Record_AFSDB(2, 'example.com', 2))
        # Vary the hostname
        self._equalityTest(
            dns.Record_AFSDB(1, 'example.com', 2),
            dns.Record_AFSDB(1, 'example.com', 2),
            dns.Record_AFSDB(1, 'example.org', 2))
        # Vary the ttl
        self._equalityTest(
            dns.Record_AFSDB(1, 'example.com', 2),
            dns.Record_AFSDB(1, 'example.com', 2),
            dns.Record_AFSDB(1, 'example.com', 3))


    def test_rp(self):
        """
        Two L{Record_RP} instances compare equal if and only if they have the
        same mbox, txt, and ttl.
        """
        # Vary the mbox
        self._equalityTest(
            dns.Record_RP('alice.example.com', 'alice is nice', 10),
            dns.Record_RP('alice.example.com', 'alice is nice', 10),
            dns.Record_RP('bob.example.com', 'alice is nice', 10))
        # Vary the txt
        self._equalityTest(
            dns.Record_RP('alice.example.com', 'alice is nice', 10),
            dns.Record_RP('alice.example.com', 'alice is nice', 10),
            dns.Record_RP('alice.example.com', 'alice is not nice', 10))
        # Vary the ttl
        self._equalityTest(
            dns.Record_RP('alice.example.com', 'alice is nice', 10),
            dns.Record_RP('alice.example.com', 'alice is nice', 10),
            dns.Record_RP('alice.example.com', 'alice is nice', 100))


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
            dns.Record_MINFO('rmailbox', 'emailbox', 10),
            dns.Record_MINFO('rmailbox', 'emailbox', 10),
            dns.Record_MINFO('someplace', 'emailbox', 10))
        # Vary the emailbx
        self._equalityTest(
            dns.Record_MINFO('rmailbox', 'emailbox', 10),
            dns.Record_MINFO('rmailbox', 'emailbox', 10),
            dns.Record_MINFO('rmailbox', 'something', 10))
        # Vary the ttl
        self._equalityTest(
            dns.Record_MINFO('rmailbox', 'emailbox', 10),
            dns.Record_MINFO('rmailbox', 'emailbox', 10),
            dns.Record_MINFO('rmailbox', 'emailbox', 100))


    def test_mx(self):
        """
        Two L{dns.Record_MX} instances compare equal if and only if they have
        the same preference, name, and ttl.
        """
        # Vary the preference
        self._equalityTest(
            dns.Record_MX(10, 'example.org', 20),
            dns.Record_MX(10, 'example.org', 20),
            dns.Record_MX(100, 'example.org', 20))
        # Vary the name
        self._equalityTest(
            dns.Record_MX(10, 'example.org', 20),
            dns.Record_MX(10, 'example.org', 20),
            dns.Record_MX(10, 'example.net', 20))
        # Vary the ttl
        self._equalityTest(
            dns.Record_MX(10, 'example.org', 20),
            dns.Record_MX(10, 'example.org', 20),
            dns.Record_MX(10, 'example.org', 200))


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
