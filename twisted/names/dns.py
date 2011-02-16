# -*- test-case-name: twisted.names.test.test_dns -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
DNS protocol implementation.

Future Plans:
    - Get rid of some toplevels, maybe.

@author: Moshe Zadka
@author: Jean-Paul Calderone
"""

__all__ = [
    'IEncodable', 'IRecord',

    'A', 'A6', 'AAAA', 'AFSDB', 'CNAME', 'DNAME', 'HINFO',
    'MAILA', 'MAILB', 'MB', 'MD', 'MF', 'MG', 'MINFO', 'MR', 'MX',
    'NAPTR', 'NS', 'NULL', 'PTR', 'RP', 'SOA', 'SPF', 'SRV', 'TXT', 'WKS',

    'ANY', 'CH', 'CS', 'HS', 'IN',

    'ALL_RECORDS', 'AXFR', 'IXFR',

    'EFORMAT', 'ENAME', 'ENOTIMP', 'EREFUSED', 'ESERVER',

    'Record_A', 'Record_A6', 'Record_AAAA', 'Record_AFSDB', 'Record_CNAME',
    'Record_DNAME', 'Record_HINFO', 'Record_MB', 'Record_MD', 'Record_MF',
    'Record_MG', 'Record_MINFO', 'Record_MR', 'Record_MX', 'Record_NAPTR',
    'Record_NS', 'Record_NULL', 'Record_PTR', 'Record_RP', 'Record_SOA',
    'Record_SPF', 'Record_SRV', 'Record_TXT', 'Record_WKS',

    'QUERY_CLASSES', 'QUERY_TYPES', 'REV_CLASSES', 'REV_TYPES', 'EXT_QUERIES',

    'Charstr', 'Message', 'Name', 'Query', 'RRHeader', 'SimpleRecord',
    'DNSDatagramProtocol', 'DNSMixin', 'DNSProtocol',

    'OK', 'OP_INVERSE', 'OP_NOTIFY', 'OP_QUERY', 'OP_STATUS', 'OP_UPDATE',
    'PORT',

    'AuthoritativeDomainError', 'DNSQueryTimeoutError', 'DomainError',
    ]


# System imports
import warnings

import struct, random, types, socket

try:
    import cStringIO as StringIO
except ImportError:
    import StringIO

AF_INET6 = socket.AF_INET6

from zope.interface import implements, Interface, Attribute


# Twisted imports
from twisted.internet import protocol, defer
from twisted.internet.error import CannotListenError
from twisted.python import log, failure
from twisted.python import util as tputil
from twisted.python import randbytes


def randomSource():
    """
    Wrapper around L{randbytes.secureRandom} to return 2 random chars.
    """
    return struct.unpack('H', randbytes.secureRandom(2, fallback=True))[0]


PORT = 53

(A, NS, MD, MF, CNAME, SOA, MB, MG, MR, NULL, WKS, PTR, HINFO, MINFO, MX, TXT,
 RP, AFSDB) = range(1, 19)
AAAA = 28
SRV = 33
NAPTR = 35
A6 = 38
DNAME = 39
SPF = 99

QUERY_TYPES = {
    A: 'A',
    NS: 'NS',
    MD: 'MD',
    MF: 'MF',
    CNAME: 'CNAME',
    SOA: 'SOA',
    MB: 'MB',
    MG: 'MG',
    MR: 'MR',
    NULL: 'NULL',
    WKS: 'WKS',
    PTR: 'PTR',
    HINFO: 'HINFO',
    MINFO: 'MINFO',
    MX: 'MX',
    TXT: 'TXT',
    RP: 'RP',
    AFSDB: 'AFSDB',

    # 19 through 27?  Eh, I'll get to 'em.

    AAAA: 'AAAA',
    SRV: 'SRV',
    NAPTR: 'NAPTR',
    A6: 'A6',
    DNAME: 'DNAME',
    SPF: 'SPF'
}

IXFR, AXFR, MAILB, MAILA, ALL_RECORDS = range(251, 256)

# "Extended" queries (Hey, half of these are deprecated, good job)
EXT_QUERIES = {
    IXFR: 'IXFR',
    AXFR: 'AXFR',
    MAILB: 'MAILB',
    MAILA: 'MAILA',
    ALL_RECORDS: 'ALL_RECORDS'
}

REV_TYPES = dict([
    (v, k) for (k, v) in QUERY_TYPES.items() + EXT_QUERIES.items()
])

IN, CS, CH, HS = range(1, 5)
ANY = 255

QUERY_CLASSES = {
    IN: 'IN',
    CS: 'CS',
    CH: 'CH',
    HS: 'HS',
    ANY: 'ANY'
}
REV_CLASSES = dict([
    (v, k) for (k, v) in QUERY_CLASSES.items()
])


# Opcodes
OP_QUERY, OP_INVERSE, OP_STATUS = range(3)
OP_NOTIFY = 4 # RFC 1996
OP_UPDATE = 5 # RFC 2136


# Response Codes
OK, EFORMAT, ESERVER, ENAME, ENOTIMP, EREFUSED = range(6)

class IRecord(Interface):
    """
    An single entry in a zone of authority.
    """

    TYPE = Attribute("An indicator of what kind of record this is.")


# Backwards compatibility aliases - these should be deprecated or something I
# suppose. -exarkun
from twisted.names.error import DomainError, AuthoritativeDomainError
from twisted.names.error import DNSQueryTimeoutError


def str2time(s):
    suffixes = (
        ('S', 1), ('M', 60), ('H', 60 * 60), ('D', 60 * 60 * 24),
        ('W', 60 * 60 * 24 * 7), ('Y', 60 * 60 * 24 * 365)
    )
    if isinstance(s, types.StringType):
        s = s.upper().strip()
        for (suff, mult) in suffixes:
            if s.endswith(suff):
                return int(float(s[:-1]) * mult)
        try:
            s = int(s)
        except ValueError:
            raise ValueError, "Invalid time interval specifier: " + s
    return s


def readPrecisely(file, l):
    buff = file.read(l)
    if len(buff) < l:
        raise EOFError
    return buff


class IEncodable(Interface):
    """
    Interface for something which can be encoded to and decoded
    from a file object.
    """

    def encode(strio, compDict = None):
        """
        Write a representation of this object to the given
        file object.

        @type strio: File-like object
        @param strio: The stream to which to write bytes

        @type compDict: C{dict} or C{None}
        @param compDict: A dictionary of backreference addresses that have
        have already been written to this stream and that may be used for
        compression.
        """

    def decode(strio, length = None):
        """
        Reconstruct an object from data read from the given
        file object.

        @type strio: File-like object
        @param strio: The stream from which bytes may be read

        @type length: C{int} or C{None}
        @param length: The number of bytes in this RDATA field.  Most
        implementations can ignore this value.  Only in the case of
        records similar to TXT where the total length is in no way
        encoded in the data is it necessary.
        """



class Charstr(object):
    implements(IEncodable)

    def __init__(self, string=''):
        if not isinstance(string, str):
            raise ValueError("%r is not a string" % (string,))
        self.string = string


    def encode(self, strio, compDict=None):
        """
        Encode this Character string into the appropriate byte format.

        @type strio: file
        @param strio: The byte representation of this Charstr will be written
            to this file.
        """
        string = self.string
        ind = len(string)
        strio.write(chr(ind))
        strio.write(string)


    def decode(self, strio, length=None):
        """
        Decode a byte string into this Name.

        @type strio: file
        @param strio: Bytes will be read from this file until the full string
            is decoded.

        @raise EOFError: Raised when there are not enough bytes available from
            C{strio}.
        """
        self.string = ''
        l = ord(readPrecisely(strio, 1))
        self.string = readPrecisely(strio, l)


    def __eq__(self, other):
        if isinstance(other, Charstr):
            return self.string == other.string
        return False


    def __hash__(self):
        return hash(self.string)


    def __str__(self):
        return self.string



class Name:
    implements(IEncodable)

    def __init__(self, name=''):
        assert isinstance(name, types.StringTypes), "%r is not a string" % (name,)
        self.name = name

    def encode(self, strio, compDict=None):
        """
        Encode this Name into the appropriate byte format.

        @type strio: file
        @param strio: The byte representation of this Name will be written to
        this file.

        @type compDict: dict
        @param compDict: dictionary of Names that have already been encoded
        and whose addresses may be backreferenced by this Name (for the purpose
        of reducing the message size).
        """
        name = self.name
        while name:
            if compDict is not None:
                if name in compDict:
                    strio.write(
                        struct.pack("!H", 0xc000 | compDict[name]))
                    return
                else:
                    compDict[name] = strio.tell() + Message.headerSize
            ind = name.find('.')
            if ind > 0:
                label, name = name[:ind], name[ind + 1:]
            else:
                label, name = name, ''
                ind = len(label)
            strio.write(chr(ind))
            strio.write(label)
        strio.write(chr(0))


    def decode(self, strio, length=None):
        """
        Decode a byte string into this Name.

        @type strio: file
        @param strio: Bytes will be read from this file until the full Name
        is decoded.

        @raise EOFError: Raised when there are not enough bytes available
        from C{strio}.
        """
        self.name = ''
        off = 0
        while 1:
            l = ord(readPrecisely(strio, 1))
            if l == 0:
                if off > 0:
                    strio.seek(off)
                return
            if (l >> 6) == 3:
                new_off = ((l&63) << 8
                            | ord(readPrecisely(strio, 1)))
                if off == 0:
                    off = strio.tell()
                strio.seek(new_off)
                continue
            label = readPrecisely(strio, l)
            if self.name == '':
                self.name = label
            else:
                self.name = self.name + '.' + label

    def __eq__(self, other):
        if isinstance(other, Name):
            return str(self) == str(other)
        return 0


    def __hash__(self):
        return hash(str(self))


    def __str__(self):
        return self.name

class Query:
    """
    Represent a single DNS query.

    @ivar name: The name about which this query is requesting information.
    @ivar type: The query type.
    @ivar cls: The query class.
    """

    implements(IEncodable)

    name = None
    type = None
    cls = None

    def __init__(self, name='', type=A, cls=IN):
        """
        @type name: C{str}
        @param name: The name about which to request information.

        @type type: C{int}
        @param type: The query type.

        @type cls: C{int}
        @param cls: The query class.
        """
        self.name = Name(name)
        self.type = type
        self.cls = cls


    def encode(self, strio, compDict=None):
        self.name.encode(strio, compDict)
        strio.write(struct.pack("!HH", self.type, self.cls))


    def decode(self, strio, length = None):
        self.name.decode(strio)
        buff = readPrecisely(strio, 4)
        self.type, self.cls = struct.unpack("!HH", buff)


    def __hash__(self):
        return hash((str(self.name).lower(), self.type, self.cls))


    def __cmp__(self, other):
        return isinstance(other, Query) and cmp(
            (str(self.name).lower(), self.type, self.cls),
            (str(other.name).lower(), other.type, other.cls)
        ) or cmp(self.__class__, other.__class__)


    def __str__(self):
        t = QUERY_TYPES.get(self.type, EXT_QUERIES.get(self.type, 'UNKNOWN (%d)' % self.type))
        c = QUERY_CLASSES.get(self.cls, 'UNKNOWN (%d)' % self.cls)
        return '<Query %s %s %s>' % (self.name, t, c)


    def __repr__(self):
        return 'Query(%r, %r, %r)' % (str(self.name), self.type, self.cls)


class RRHeader(tputil.FancyEqMixin):
    """
    A resource record header.

    @cvar fmt: C{str} specifying the byte format of an RR.

    @ivar name: The name about which this reply contains information.
    @ivar type: The query type of the original request.
    @ivar cls: The query class of the original request.
    @ivar ttl: The time-to-live for this record.
    @ivar payload: An object that implements the IEncodable interface
    @ivar auth: Whether this header is authoritative or not.
    """

    implements(IEncodable)

    compareAttributes = ('name', 'type', 'cls', 'ttl', 'payload', 'auth')

    fmt = "!HHIH"

    name = None
    type = None
    cls = None
    ttl = None
    payload = None
    rdlength = None

    cachedResponse = None

    def __init__(self, name='', type=A, cls=IN, ttl=0, payload=None, auth=False):
        """
        @type name: C{str}
        @param name: The name about which this reply contains information.

        @type type: C{int}
        @param type: The query type.

        @type cls: C{int}
        @param cls: The query class.

        @type ttl: C{int}
        @param ttl: Time to live for this record.

        @type payload: An object implementing C{IEncodable}
        @param payload: A Query Type specific data object.
        """
        assert (payload is None) or (payload.TYPE == type)

        self.name = Name(name)
        self.type = type
        self.cls = cls
        self.ttl = ttl
        self.payload = payload
        self.auth = auth


    def encode(self, strio, compDict=None):
        self.name.encode(strio, compDict)
        strio.write(struct.pack(self.fmt, self.type, self.cls, self.ttl, 0))
        if self.payload:
            prefix = strio.tell()
            self.payload.encode(strio, compDict)
            aft = strio.tell()
            strio.seek(prefix - 2, 0)
            strio.write(struct.pack('!H', aft - prefix))
            strio.seek(aft, 0)


    def decode(self, strio, length = None):
        self.name.decode(strio)
        l = struct.calcsize(self.fmt)
        buff = readPrecisely(strio, l)
        r = struct.unpack(self.fmt, buff)
        self.type, self.cls, self.ttl, self.rdlength = r


    def isAuthoritative(self):
        return self.auth


    def __str__(self):
        t = QUERY_TYPES.get(self.type, EXT_QUERIES.get(self.type, 'UNKNOWN (%d)' % self.type))
        c = QUERY_CLASSES.get(self.cls, 'UNKNOWN (%d)' % self.cls)
        return '<RR name=%s type=%s class=%s ttl=%ds auth=%s>' % (self.name, t, c, self.ttl, self.auth and 'True' or 'False')


    __repr__ = __str__



class SimpleRecord(tputil.FancyStrMixin, tputil.FancyEqMixin):
    """
    A Resource Record which consists of a single RFC 1035 domain-name.

    @type name: L{Name}
    @ivar name: The name associated with this record.

    @type ttl: C{int}
    @ivar ttl: The maximum number of seconds which this record should be
        cached.
    """
    implements(IEncodable, IRecord)

    showAttributes = (('name', 'name', '%s'), 'ttl')
    compareAttributes = ('name', 'ttl')

    TYPE = None
    name = None

    def __init__(self, name='', ttl=None):
        self.name = Name(name)
        self.ttl = str2time(ttl)


    def encode(self, strio, compDict = None):
        self.name.encode(strio, compDict)


    def decode(self, strio, length = None):
        self.name = Name()
        self.name.decode(strio)


    def __hash__(self):
        return hash(self.name)


# Kinds of RRs - oh my!
class Record_NS(SimpleRecord):
    """
    An authoritative nameserver.
    """
    TYPE = NS
    fancybasename = 'NS'



class Record_MD(SimpleRecord):
    """
    A mail destination.

    This record type is obsolete.

    @see: L{Record_MX}
    """
    TYPE = MD
    fancybasename = 'MD'



class Record_MF(SimpleRecord):
    """
    A mail forwarder.

    This record type is obsolete.

    @see: L{Record_MX}
    """
    TYPE = MF
    fancybasename = 'MF'



class Record_CNAME(SimpleRecord):
    """
    The canonical name for an alias.
    """
    TYPE = CNAME
    fancybasename = 'CNAME'



class Record_MB(SimpleRecord):
    """
    A mailbox domain name.

    This is an experimental record type.
    """
    TYPE = MB
    fancybasename = 'MB'



class Record_MG(SimpleRecord):
    """
    A mail group member.

    This is an experimental record type.
    """
    TYPE = MG
    fancybasename = 'MG'



class Record_MR(SimpleRecord):
    """
    A mail rename domain name.

    This is an experimental record type.
    """
    TYPE = MR
    fancybasename = 'MR'



class Record_PTR(SimpleRecord):
    """
    A domain name pointer.
    """
    TYPE = PTR
    fancybasename = 'PTR'



class Record_DNAME(SimpleRecord):
    """
    A non-terminal DNS name redirection.

    This record type provides the capability to map an entire subtree of the
    DNS name space to another domain.  It differs from the CNAME record which
    maps a single node of the name space.

    @see: U{http://www.faqs.org/rfcs/rfc2672.html}
    @see: U{http://www.faqs.org/rfcs/rfc3363.html}
    """
    TYPE = DNAME
    fancybasename = 'DNAME'



class Record_A(tputil.FancyEqMixin):
    """
    An IPv4 host address.

    @type address: C{str}
    @ivar address: The packed network-order representation of the IPv4 address
        associated with this record.

    @type ttl: C{int}
    @ivar ttl: The maximum number of seconds which this record should be
        cached.
    """
    implements(IEncodable, IRecord)

    compareAttributes = ('address', 'ttl')

    TYPE = A
    address = None

    def __init__(self, address='0.0.0.0', ttl=None):
        address = socket.inet_aton(address)
        self.address = address
        self.ttl = str2time(ttl)


    def encode(self, strio, compDict = None):
        strio.write(self.address)


    def decode(self, strio, length = None):
        self.address = readPrecisely(strio, 4)


    def __hash__(self):
        return hash(self.address)


    def __str__(self):
        return '<A address=%s ttl=%s>' % (self.dottedQuad(), self.ttl)
    __repr__ = __str__


    def dottedQuad(self):
        return socket.inet_ntoa(self.address)



class Record_SOA(tputil.FancyEqMixin, tputil.FancyStrMixin):
    """
    Marks the start of a zone of authority.

    This record describes parameters which are shared by all records within a
    particular zone.

    @type mname: L{Name}
    @ivar mname: The domain-name of the name server that was the original or
        primary source of data for this zone.

    @type rname: L{Name}
    @ivar rname: A domain-name which specifies the mailbox of the person
        responsible for this zone.

    @type serial: C{int}
    @ivar serial: The unsigned 32 bit version number of the original copy of
        the zone.  Zone transfers preserve this value.  This value wraps and
        should be compared using sequence space arithmetic.

    @type refresh: C{int}
    @ivar refresh: A 32 bit time interval before the zone should be refreshed.

    @type minimum: C{int}
    @ivar minimum: The unsigned 32 bit minimum TTL field that should be
        exported with any RR from this zone.

    @type expire: C{int}
    @ivar expire: A 32 bit time value that specifies the upper limit on the
        time interval that can elapse before the zone is no longer
        authoritative.

    @type retry: C{int}
    @ivar retry: A 32 bit time interval that should elapse before a failed
        refresh should be retried.

    @type ttl: C{int}
    @ivar ttl: The default TTL to use for records served from this zone.
    """
    implements(IEncodable, IRecord)

    fancybasename = 'SOA'
    compareAttributes = ('serial', 'mname', 'rname', 'refresh', 'expire', 'retry', 'minimum', 'ttl')
    showAttributes = (('mname', 'mname', '%s'), ('rname', 'rname', '%s'), 'serial', 'refresh', 'retry', 'expire', 'minimum', 'ttl')

    TYPE = SOA

    def __init__(self, mname='', rname='', serial=0, refresh=0, retry=0, expire=0, minimum=0, ttl=None):
        self.mname, self.rname = Name(mname), Name(rname)
        self.serial, self.refresh = str2time(serial), str2time(refresh)
        self.minimum, self.expire = str2time(minimum), str2time(expire)
        self.retry = str2time(retry)
        self.ttl = str2time(ttl)


    def encode(self, strio, compDict = None):
        self.mname.encode(strio, compDict)
        self.rname.encode(strio, compDict)
        strio.write(
            struct.pack(
                '!LlllL',
                self.serial, self.refresh, self.retry, self.expire,
                self.minimum
            )
        )


    def decode(self, strio, length = None):
        self.mname, self.rname = Name(), Name()
        self.mname.decode(strio)
        self.rname.decode(strio)
        r = struct.unpack('!LlllL', readPrecisely(strio, 20))
        self.serial, self.refresh, self.retry, self.expire, self.minimum = r


    def __hash__(self):
        return hash((
            self.serial, self.mname, self.rname,
            self.refresh, self.expire, self.retry
        ))



class Record_NULL(tputil.FancyStrMixin, tputil.FancyEqMixin):
    """
    A null record.

    This is an experimental record type.

    @type ttl: C{int}
    @ivar ttl: The maximum number of seconds which this record should be
        cached.
    """
    implements(IEncodable, IRecord)

    fancybasename = 'NULL'
    showAttributes = compareAttributes = ('payload', 'ttl')

    TYPE = NULL

    def __init__(self, payload=None, ttl=None):
        self.payload = payload
        self.ttl = str2time(ttl)


    def encode(self, strio, compDict = None):
        strio.write(self.payload)


    def decode(self, strio, length = None):
        self.payload = readPrecisely(strio, length)


    def __hash__(self):
        return hash(self.payload)



class Record_WKS(tputil.FancyEqMixin, tputil.FancyStrMixin):
    """
    A well known service description.

    This record type is obsolete.  See L{Record_SRV}.

    @type address: C{str}
    @ivar address: The packed network-order representation of the IPv4 address
        associated with this record.

    @type protocol: C{int}
    @ivar protocol: The 8 bit IP protocol number for which this service map is
        relevant.

    @type map: C{str}
    @ivar map: A bitvector indicating the services available at the specified
        address.

    @type ttl: C{int}
    @ivar ttl: The maximum number of seconds which this record should be
        cached.
    """
    implements(IEncodable, IRecord)

    fancybasename = "WKS"
    compareAttributes = ('address', 'protocol', 'map', 'ttl')
    showAttributes = [('_address', 'address', '%s'), 'protocol', 'ttl']

    TYPE = WKS

    _address = property(lambda self: socket.inet_ntoa(self.address))

    def __init__(self, address='0.0.0.0', protocol=0, map='', ttl=None):
        self.address = socket.inet_aton(address)
        self.protocol, self.map = protocol, map
        self.ttl = str2time(ttl)


    def encode(self, strio, compDict = None):
        strio.write(self.address)
        strio.write(struct.pack('!B', self.protocol))
        strio.write(self.map)


    def decode(self, strio, length = None):
        self.address = readPrecisely(strio, 4)
        self.protocol = struct.unpack('!B', readPrecisely(strio, 1))[0]
        self.map = readPrecisely(strio, length - 5)


    def __hash__(self):
        return hash((self.address, self.protocol, self.map))



class Record_AAAA(tputil.FancyEqMixin, tputil.FancyStrMixin):
    """
    An IPv6 host address.

    @type address: C{str}
    @ivar address: The packed network-order representation of the IPv6 address
        associated with this record.

    @type ttl: C{int}
    @ivar ttl: The maximum number of seconds which this record should be
        cached.

    @see: U{http://www.faqs.org/rfcs/rfc1886.html}
    """
    implements(IEncodable, IRecord)
    TYPE = AAAA

    fancybasename = 'AAAA'
    showAttributes = (('_address', 'address', '%s'), 'ttl')
    compareAttributes = ('address', 'ttl')

    _address = property(lambda self: socket.inet_ntop(AF_INET6, self.address))

    def __init__(self, address = '::', ttl=None):
        self.address = socket.inet_pton(AF_INET6, address)
        self.ttl = str2time(ttl)


    def encode(self, strio, compDict = None):
        strio.write(self.address)


    def decode(self, strio, length = None):
        self.address = readPrecisely(strio, 16)


    def __hash__(self):
        return hash(self.address)



class Record_A6(tputil.FancyStrMixin, tputil.FancyEqMixin):
    """
    An IPv6 address.

    This is an experimental record type.

    @type prefixLen: C{int}
    @ivar prefixLen: The length of the suffix.

    @type suffix: C{str}
    @ivar suffix: An IPv6 address suffix in network order.

    @type prefix: L{Name}
    @ivar prefix: If specified, a name which will be used as a prefix for other
        A6 records.

    @type bytes: C{int}
    @ivar bytes: The length of the prefix.

    @type ttl: C{int}
    @ivar ttl: The maximum number of seconds which this record should be
        cached.

    @see: U{http://www.faqs.org/rfcs/rfc2874.html}
    @see: U{http://www.faqs.org/rfcs/rfc3363.html}
    @see: U{http://www.faqs.org/rfcs/rfc3364.html}
    """
    implements(IEncodable, IRecord)
    TYPE = A6

    fancybasename = 'A6'
    showAttributes = (('_suffix', 'suffix', '%s'), ('prefix', 'prefix', '%s'), 'ttl')
    compareAttributes = ('prefixLen', 'prefix', 'suffix', 'ttl')

    _suffix = property(lambda self: socket.inet_ntop(AF_INET6, self.suffix))

    def __init__(self, prefixLen=0, suffix='::', prefix='', ttl=None):
        self.prefixLen = prefixLen
        self.suffix = socket.inet_pton(AF_INET6, suffix)
        self.prefix = Name(prefix)
        self.bytes = int((128 - self.prefixLen) / 8.0)
        self.ttl = str2time(ttl)


    def encode(self, strio, compDict = None):
        strio.write(struct.pack('!B', self.prefixLen))
        if self.bytes:
            strio.write(self.suffix[-self.bytes:])
        if self.prefixLen:
            # This may not be compressed
            self.prefix.encode(strio, None)


    def decode(self, strio, length = None):
        self.prefixLen = struct.unpack('!B', readPrecisely(strio, 1))[0]
        self.bytes = int((128 - self.prefixLen) / 8.0)
        if self.bytes:
            self.suffix = '\x00' * (16 - self.bytes) + readPrecisely(strio, self.bytes)
        if self.prefixLen:
            self.prefix.decode(strio)


    def __eq__(self, other):
        if isinstance(other, Record_A6):
            return (self.prefixLen == other.prefixLen and
                    self.suffix[-self.bytes:] == other.suffix[-self.bytes:] and
                    self.prefix == other.prefix and
                    self.ttl == other.ttl)
        return NotImplemented


    def __hash__(self):
        return hash((self.prefixLen, self.suffix[-self.bytes:], self.prefix))


    def __str__(self):
        return '<A6 %s %s (%d) ttl=%s>' % (
            self.prefix,
            socket.inet_ntop(AF_INET6, self.suffix),
            self.prefixLen, self.ttl
        )



class Record_SRV(tputil.FancyEqMixin, tputil.FancyStrMixin):
    """
    The location of the server(s) for a specific protocol and domain.

    This is an experimental record type.

    @type priority: C{int}
    @ivar priority: The priority of this target host.  A client MUST attempt to
        contact the target host with the lowest-numbered priority it can reach;
        target hosts with the same priority SHOULD be tried in an order defined
        by the weight field.

    @type weight: C{int}
    @ivar weight: Specifies a relative weight for entries with the same
        priority. Larger weights SHOULD be given a proportionately higher
        probability of being selected.

    @type port: C{int}
    @ivar port: The port on this target host of this service.

    @type target: L{Name}
    @ivar target: The domain name of the target host.  There MUST be one or
        more address records for this name, the name MUST NOT be an alias (in
        the sense of RFC 1034 or RFC 2181).  Implementors are urged, but not
        required, to return the address record(s) in the Additional Data
        section.  Unless and until permitted by future standards action, name
        compression is not to be used for this field.

    @type ttl: C{int}
    @ivar ttl: The maximum number of seconds which this record should be
        cached.

    @see: U{http://www.faqs.org/rfcs/rfc2782.html}
    """
    implements(IEncodable, IRecord)
    TYPE = SRV

    fancybasename = 'SRV'
    compareAttributes = ('priority', 'weight', 'target', 'port', 'ttl')
    showAttributes = ('priority', 'weight', ('target', 'target', '%s'), 'port', 'ttl')

    def __init__(self, priority=0, weight=0, port=0, target='', ttl=None):
        self.priority = int(priority)
        self.weight = int(weight)
        self.port = int(port)
        self.target = Name(target)
        self.ttl = str2time(ttl)


    def encode(self, strio, compDict = None):
        strio.write(struct.pack('!HHH', self.priority, self.weight, self.port))
        # This can't be compressed
        self.target.encode(strio, None)


    def decode(self, strio, length = None):
        r = struct.unpack('!HHH', readPrecisely(strio, struct.calcsize('!HHH')))
        self.priority, self.weight, self.port = r
        self.target = Name()
        self.target.decode(strio)


    def __hash__(self):
        return hash((self.priority, self.weight, self.port, self.target))



class Record_NAPTR(tputil.FancyEqMixin, tputil.FancyStrMixin):
    """
    The location of the server(s) for a specific protocol and domain.

    @type order: C{int}
    @ivar order: An integer specifying the order in which the NAPTR records
        MUST be processed to ensure the correct ordering of rules.  Low numbers
        are processed before high numbers.

    @type preference: C{int}
    @ivar preference: An integer that specifies the order in which NAPTR
        records with equal "order" values SHOULD be processed, low numbers
        being processed before high numbers.

    @type flag: L{Charstr}
    @ivar flag: A <character-string> containing flags to control aspects of the
        rewriting and interpretation of the fields in the record.  Flags
        aresingle characters from the set [A-Z0-9].  The case of the alphabetic
        characters is not significant.

        At this time only four flags, "S", "A", "U", and "P", are defined.

    @type service: L{Charstr}
    @ivar service: Specifies the service(s) available down this rewrite path.
        It may also specify the particular protocol that is used to talk with a
        service.  A protocol MUST be specified if the flags field states that
        the NAPTR is terminal.

    @type regexp: L{Charstr}
    @ivar regexp: A STRING containing a substitution expression that is applied
        to the original string held by the client in order to construct the
        next domain name to lookup.

    @type replacement: L{Name}
    @ivar replacement: The next NAME to query for NAPTR, SRV, or address
        records depending on the value of the flags field.  This MUST be a
        fully qualified domain-name.

    @type ttl: C{int}
    @ivar ttl: The maximum number of seconds which this record should be
        cached.

    @see: U{http://www.faqs.org/rfcs/rfc2915.html}
    """
    implements(IEncodable, IRecord)
    TYPE = NAPTR

    compareAttributes = ('order', 'preference', 'flags', 'service', 'regexp',
                         'replacement')
    fancybasename = 'NAPTR'
    showAttributes = ('order', 'preference', ('flags', 'flags', '%s'),
                      ('service', 'service', '%s'), ('regexp', 'regexp', '%s'),
                      ('replacement', 'replacement', '%s'), 'ttl')

    def __init__(self, order=0, preference=0, flags='', service='', regexp='',
                 replacement='', ttl=None):
        self.order = int(order)
        self.preference = int(preference)
        self.flags = Charstr(flags)
        self.service = Charstr(service)
        self.regexp = Charstr(regexp)
        self.replacement = Name(replacement)
        self.ttl = str2time(ttl)


    def encode(self, strio, compDict=None):
        strio.write(struct.pack('!HH', self.order, self.preference))
        # This can't be compressed
        self.flags.encode(strio, None)
        self.service.encode(strio, None)
        self.regexp.encode(strio, None)
        self.replacement.encode(strio, None)


    def decode(self, strio, length=None):
        r = struct.unpack('!HH', readPrecisely(strio, struct.calcsize('!HH')))
        self.order, self.preference = r
        self.flags = Charstr()
        self.service = Charstr()
        self.regexp = Charstr()
        self.replacement = Name()
        self.flags.decode(strio)
        self.service.decode(strio)
        self.regexp.decode(strio)
        self.replacement.decode(strio)


    def __hash__(self):
        return hash((
            self.order, self.preference, self.flags,
            self.service, self.regexp, self.replacement))



class Record_AFSDB(tputil.FancyStrMixin, tputil.FancyEqMixin):
    """
    Map from a domain name to the name of an AFS cell database server.

    @type subtype: C{int}
    @ivar subtype: In the case of subtype 1, the host has an AFS version 3.0
        Volume Location Server for the named AFS cell.  In the case of subtype
        2, the host has an authenticated name server holding the cell-root
        directory node for the named DCE/NCA cell.

    @type hostname: L{Name}
    @ivar hostname: The domain name of a host that has a server for the cell
        named by this record.

    @type ttl: C{int}
    @ivar ttl: The maximum number of seconds which this record should be
        cached.

    @see: U{http://www.faqs.org/rfcs/rfc1183.html}
    """
    implements(IEncodable, IRecord)
    TYPE = AFSDB

    fancybasename = 'AFSDB'
    compareAttributes = ('subtype', 'hostname', 'ttl')
    showAttributes = ('subtype', ('hostname', 'hostname', '%s'), 'ttl')

    def __init__(self, subtype=0, hostname='', ttl=None):
        self.subtype = int(subtype)
        self.hostname = Name(hostname)
        self.ttl = str2time(ttl)


    def encode(self, strio, compDict = None):
        strio.write(struct.pack('!H', self.subtype))
        self.hostname.encode(strio, compDict)


    def decode(self, strio, length = None):
        r = struct.unpack('!H', readPrecisely(strio, struct.calcsize('!H')))
        self.subtype, = r
        self.hostname.decode(strio)


    def __hash__(self):
        return hash((self.subtype, self.hostname))



class Record_RP(tputil.FancyEqMixin, tputil.FancyStrMixin):
    """
    The responsible person for a domain.

    @type mbox: L{Name}
    @ivar mbox: A domain name that specifies the mailbox for the responsible
        person.

    @type txt: L{Name}
    @ivar txt: A domain name for which TXT RR's exist (indirection through
        which allows information sharing about the contents of this RP record).

    @type ttl: C{int}
    @ivar ttl: The maximum number of seconds which this record should be
        cached.

    @see: U{http://www.faqs.org/rfcs/rfc1183.html}
    """
    implements(IEncodable, IRecord)
    TYPE = RP

    fancybasename = 'RP'
    compareAttributes = ('mbox', 'txt', 'ttl')
    showAttributes = (('mbox', 'mbox', '%s'), ('txt', 'txt', '%s'), 'ttl')

    def __init__(self, mbox='', txt='', ttl=None):
        self.mbox = Name(mbox)
        self.txt = Name(txt)
        self.ttl = str2time(ttl)


    def encode(self, strio, compDict = None):
        self.mbox.encode(strio, compDict)
        self.txt.encode(strio, compDict)


    def decode(self, strio, length = None):
        self.mbox = Name()
        self.txt = Name()
        self.mbox.decode(strio)
        self.txt.decode(strio)


    def __hash__(self):
        return hash((self.mbox, self.txt))



class Record_HINFO(tputil.FancyStrMixin, tputil.FancyEqMixin):
    """
    Host information.

    @type cpu: C{str}
    @ivar cpu: Specifies the CPU type.

    @type os: C{str}
    @ivar os: Specifies the OS.

    @type ttl: C{int}
    @ivar ttl: The maximum number of seconds which this record should be
        cached.
    """
    implements(IEncodable, IRecord)
    TYPE = HINFO

    fancybasename = 'HINFO'
    showAttributes = compareAttributes = ('cpu', 'os', 'ttl')

    def __init__(self, cpu='', os='', ttl=None):
        self.cpu, self.os = cpu, os
        self.ttl = str2time(ttl)


    def encode(self, strio, compDict = None):
        strio.write(struct.pack('!B', len(self.cpu)) + self.cpu)
        strio.write(struct.pack('!B', len(self.os)) + self.os)


    def decode(self, strio, length = None):
        cpu = struct.unpack('!B', readPrecisely(strio, 1))[0]
        self.cpu = readPrecisely(strio, cpu)
        os = struct.unpack('!B', readPrecisely(strio, 1))[0]
        self.os = readPrecisely(strio, os)


    def __eq__(self, other):
        if isinstance(other, Record_HINFO):
            return (self.os.lower() == other.os.lower() and
                    self.cpu.lower() == other.cpu.lower() and
                    self.ttl == other.ttl)
        return NotImplemented


    def __hash__(self):
        return hash((self.os.lower(), self.cpu.lower()))



class Record_MINFO(tputil.FancyEqMixin, tputil.FancyStrMixin):
    """
    Mailbox or mail list information.

    This is an experimental record type.

    @type rmailbx: L{Name}
    @ivar rmailbx: A domain-name which specifies a mailbox which is responsible
        for the mailing list or mailbox.  If this domain name names the root,
        the owner of the MINFO RR is responsible for itself.

    @type emailbx: L{Name}
    @ivar emailbx: A domain-name which specifies a mailbox which is to receive
        error messages related to the mailing list or mailbox specified by the
        owner of the MINFO record.  If this domain name names the root, errors
        should be returned to the sender of the message.

    @type ttl: C{int}
    @ivar ttl: The maximum number of seconds which this record should be
        cached.
    """
    implements(IEncodable, IRecord)
    TYPE = MINFO

    rmailbx = None
    emailbx = None

    fancybasename = 'MINFO'
    compareAttributes = ('rmailbx', 'emailbx', 'ttl')
    showAttributes = (('rmailbx', 'responsibility', '%s'),
                      ('emailbx', 'errors', '%s'),
                      'ttl')

    def __init__(self, rmailbx='', emailbx='', ttl=None):
        self.rmailbx, self.emailbx = Name(rmailbx), Name(emailbx)
        self.ttl = str2time(ttl)


    def encode(self, strio, compDict = None):
        self.rmailbx.encode(strio, compDict)
        self.emailbx.encode(strio, compDict)


    def decode(self, strio, length = None):
        self.rmailbx, self.emailbx = Name(), Name()
        self.rmailbx.decode(strio)
        self.emailbx.decode(strio)


    def __hash__(self):
        return hash((self.rmailbx, self.emailbx))



class Record_MX(tputil.FancyStrMixin, tputil.FancyEqMixin):
    """
    Mail exchange.

    @type preference: C{int}
    @ivar preference: Specifies the preference given to this RR among others at
        the same owner.  Lower values are preferred.

    @type name: L{Name}
    @ivar name: A domain-name which specifies a host willing to act as a mail
        exchange.

    @type ttl: C{int}
    @ivar ttl: The maximum number of seconds which this record should be
        cached.
    """
    implements(IEncodable, IRecord)
    TYPE = MX

    fancybasename = 'MX'
    compareAttributes = ('preference', 'name', 'ttl')
    showAttributes = ('preference', ('name', 'name', '%s'), 'ttl')

    def __init__(self, preference=0, name='', ttl=None, **kwargs):
        self.preference, self.name = int(preference), Name(kwargs.get('exchange', name))
        self.ttl = str2time(ttl)

    def encode(self, strio, compDict = None):
        strio.write(struct.pack('!H', self.preference))
        self.name.encode(strio, compDict)


    def decode(self, strio, length = None):
        self.preference = struct.unpack('!H', readPrecisely(strio, 2))[0]
        self.name = Name()
        self.name.decode(strio)

    def exchange(self):
        warnings.warn("use Record_MX.name instead", DeprecationWarning, stacklevel=2)
        return self.name

    exchange = property(exchange)

    def __hash__(self):
        return hash((self.preference, self.name))



# Oh god, Record_TXT how I hate thee.
class Record_TXT(tputil.FancyEqMixin, tputil.FancyStrMixin):
    """
    Freeform text.

    @type data: C{list} of C{str}
    @ivar data: Freeform text which makes up this record.
    
    @type ttl: C{int}
    @ivar ttl: The maximum number of seconds which this record should be cached.
    """
    implements(IEncodable, IRecord)

    TYPE = TXT

    fancybasename = 'TXT'
    showAttributes = compareAttributes = ('data', 'ttl')

    def __init__(self, *data, **kw):
        self.data = list(data)
        # arg man python sucks so bad
        self.ttl = str2time(kw.get('ttl', None))


    def encode(self, strio, compDict = None):
        for d in self.data:
            strio.write(struct.pack('!B', len(d)) + d)


    def decode(self, strio, length = None):
        soFar = 0
        self.data = []
        while soFar < length:
            L = struct.unpack('!B', readPrecisely(strio, 1))[0]
            self.data.append(readPrecisely(strio, L))
            soFar += L + 1
        if soFar != length:
            log.msg(
                "Decoded %d bytes in %s record, but rdlength is %d" % (
                    soFar, self.fancybasename, length
                )
            )


    def __hash__(self):
        return hash(tuple(self.data))



class Record_SPF(Record_TXT):
    """
    Structurally, freeform text. Semantically, a policy definition, formatted
    as defined in U{rfc 4408<http://www.faqs.org/rfcs/rfc4408.html>}.
    
    @type data: C{list} of C{str}
    @ivar data: Freeform text which makes up this record.
    
    @type ttl: C{int}
    @ivar ttl: The maximum number of seconds which this record should be cached.
    """
    TYPE = SPF
    fancybasename = 'SPF'



class Message:
    """
    L{Message} contains all the information represented by a single
    DNS request or response.
    """
    headerFmt = "!H2B4H"
    headerSize = struct.calcsize(headerFmt)

    # Question, answer, additional, and nameserver lists
    queries = answers = add = ns = None

    def __init__(self, id=0, answer=0, opCode=0, recDes=0, recAv=0,
                       auth=0, rCode=OK, trunc=0, maxSize=512):
        self.maxSize = maxSize
        self.id = id
        self.answer = answer
        self.opCode = opCode
        self.auth = auth
        self.trunc = trunc
        self.recDes = recDes
        self.recAv = recAv
        self.rCode = rCode
        self.queries = []
        self.answers = []
        self.authority = []
        self.additional = []


    def addQuery(self, name, type=ALL_RECORDS, cls=IN):
        """
        Add another query to this Message.

        @type name: C{str}
        @param name: The name to query.

        @type type: C{int}
        @param type: Query type

        @type cls: C{int}
        @param cls: Query class
        """
        self.queries.append(Query(name, type, cls))


    def encode(self, strio):
        compDict = {}
        body_tmp = StringIO.StringIO()
        for q in self.queries:
            q.encode(body_tmp, compDict)
        for q in self.answers:
            q.encode(body_tmp, compDict)
        for q in self.authority:
            q.encode(body_tmp, compDict)
        for q in self.additional:
            q.encode(body_tmp, compDict)
        body = body_tmp.getvalue()
        size = len(body) + self.headerSize
        if self.maxSize and size > self.maxSize:
            self.trunc = 1
            body = body[:self.maxSize - self.headerSize]
        byte3 = (( ( self.answer & 1 ) << 7 )
                 | ((self.opCode & 0xf ) << 3 )
                 | ((self.auth & 1 ) << 2 )
                 | ((self.trunc & 1 ) << 1 )
                 | ( self.recDes & 1 ) )
        byte4 = ( ( (self.recAv & 1 ) << 7 )
                  | (self.rCode & 0xf ) )

        strio.write(struct.pack(self.headerFmt, self.id, byte3, byte4,
                                len(self.queries), len(self.answers),
                                len(self.authority), len(self.additional)))
        strio.write(body)


    def decode(self, strio, length=None):
        self.maxSize = 0
        header = readPrecisely(strio, self.headerSize)
        r = struct.unpack(self.headerFmt, header)
        self.id, byte3, byte4, nqueries, nans, nns, nadd = r
        self.answer = ( byte3 >> 7 ) & 1
        self.opCode = ( byte3 >> 3 ) & 0xf
        self.auth = ( byte3 >> 2 ) & 1
        self.trunc = ( byte3 >> 1 ) & 1
        self.recDes = byte3 & 1
        self.recAv = ( byte4 >> 7 ) & 1
        self.rCode = byte4 & 0xf

        self.queries = []
        for i in range(nqueries):
            q = Query()
            try:
                q.decode(strio)
            except EOFError:
                return
            self.queries.append(q)

        items = ((self.answers, nans), (self.authority, nns), (self.additional, nadd))
        for (l, n) in items:
            self.parseRecords(l, n, strio)


    def parseRecords(self, list, num, strio):
        for i in range(num):
            header = RRHeader()
            try:
                header.decode(strio)
            except EOFError:
                return
            t = self.lookupRecordType(header.type)
            if not t:
                continue
            header.payload = t(ttl=header.ttl)
            try:
                header.payload.decode(strio, header.rdlength)
            except EOFError:
                return
            list.append(header)


    # Create a mapping from record types to their corresponding Record_*
    # classes.  This relies on the global state which has been created so
    # far in initializing this module (so don't define Record classes after
    # this).
    _recordTypes = {}
    for name in globals():
        if name.startswith('Record_'):
            _recordTypes[globals()[name].TYPE] = globals()[name]

    # Clear the iteration variable out of the class namespace so it
    # doesn't become an attribute.
    del name


    def lookupRecordType(self, type):
        """
        Retrieve the L{IRecord} implementation for the given record type.

        @param type: A record type, such as L{A} or L{NS}.
        @type type: C{int}

        @return: An object which implements L{IRecord} or C{None} if none
            can be found for the given type.
        @rtype: L{types.ClassType}
        """
        return self._recordTypes.get(type, None)


    def toStr(self):
        strio = StringIO.StringIO()
        self.encode(strio)
        return strio.getvalue()


    def fromStr(self, str):
        strio = StringIO.StringIO(str)
        self.decode(strio)



class DNSMixin(object):
    """
    DNS protocol mixin shared by UDP and TCP implementations.

    @ivar _reactor: A L{IReactorTime} and L{IReactorUDP} provider which will
        be used to issue DNS queries and manage request timeouts.
    """
    id = None
    liveMessages = None

    def __init__(self, controller, reactor=None):
        self.controller = controller
        self.id = random.randrange(2 ** 10, 2 ** 15)
        if reactor is None:
            from twisted.internet import reactor
        self._reactor = reactor


    def pickID(self):
        """
        Return a unique ID for queries.
        """
        while True:
            id = randomSource()
            if id not in self.liveMessages:
                return id


    def callLater(self, period, func, *args):
        """
        Wrapper around reactor.callLater, mainly for test purpose.
        """
        return self._reactor.callLater(period, func, *args)


    def _query(self, queries, timeout, id, writeMessage):
        """
        Send out a message with the given queries.

        @type queries: C{list} of C{Query} instances
        @param queries: The queries to transmit

        @type timeout: C{int} or C{float}
        @param timeout: How long to wait before giving up

        @type id: C{int}
        @param id: Unique key for this request

        @type writeMessage: C{callable}
        @param writeMessage: One-parameter callback which writes the message

        @rtype: C{Deferred}
        @return: a C{Deferred} which will be fired with the result of the
            query, or errbacked with any errors that could happen (exceptions
            during writing of the query, timeout errors, ...).
        """
        m = Message(id, recDes=1)
        m.queries = queries

        try:
            writeMessage(m)
        except:
            return defer.fail()

        resultDeferred = defer.Deferred()
        cancelCall = self.callLater(timeout, self._clearFailed, resultDeferred, id)
        self.liveMessages[id] = (resultDeferred, cancelCall)

        return resultDeferred

    def _clearFailed(self, deferred, id):
        """
        Clean the Deferred after a timeout.
        """
        try:
            del self.liveMessages[id]
        except KeyError:
            pass
        deferred.errback(failure.Failure(DNSQueryTimeoutError(id)))


class DNSDatagramProtocol(DNSMixin, protocol.DatagramProtocol):
    """
    DNS protocol over UDP.
    """
    resends = None

    def stopProtocol(self):
        """
        Stop protocol: reset state variables.
        """
        self.liveMessages = {}
        self.resends = {}
        self.transport = None

    def startProtocol(self):
        """
        Upon start, reset internal state.
        """
        self.liveMessages = {}
        self.resends = {}

    def writeMessage(self, message, address):
        """
        Send a message holding DNS queries.

        @type message: L{Message}
        """
        self.transport.write(message.toStr(), address)

    def startListening(self):
        self._reactor.listenUDP(0, self, maxPacketSize=512)

    def datagramReceived(self, data, addr):
        """
        Read a datagram, extract the message in it and trigger the associated
        Deferred.
        """
        m = Message()
        try:
            m.fromStr(data)
        except EOFError:
            log.msg("Truncated packet (%d bytes) from %s" % (len(data), addr))
            return
        except:
            # Nothing should trigger this, but since we're potentially
            # invoking a lot of different decoding methods, we might as well
            # be extra cautious.  Anything that triggers this is itself
            # buggy.
            log.err(failure.Failure(), "Unexpected decoding error")
            return

        if m.id in self.liveMessages:
            d, canceller = self.liveMessages[m.id]
            del self.liveMessages[m.id]
            canceller.cancel()
            # XXX we shouldn't need this hack of catching exception on callback()
            try:
                d.callback(m)
            except:
                log.err()
        else:
            if m.id not in self.resends:
                self.controller.messageReceived(m, self, addr)


    def removeResend(self, id):
        """
        Mark message ID as no longer having duplication suppression.
        """
        try:
            del self.resends[id]
        except KeyError:
            pass

    def query(self, address, queries, timeout=10, id=None):
        """
        Send out a message with the given queries.

        @type address: C{tuple} of C{str} and C{int}
        @param address: The address to which to send the query

        @type queries: C{list} of C{Query} instances
        @param queries: The queries to transmit

        @rtype: C{Deferred}
        """
        if not self.transport:
            # XXX transport might not get created automatically, use callLater?
            try:
                self.startListening()
            except CannotListenError:
                return defer.fail()

        if id is None:
            id = self.pickID()
        else:
            self.resends[id] = 1

        def writeMessage(m):
            self.writeMessage(m, address)

        return self._query(queries, timeout, id, writeMessage)


class DNSProtocol(DNSMixin, protocol.Protocol):
    """
    DNS protocol over TCP.
    """
    length = None
    buffer = ''

    def writeMessage(self, message):
        """
        Send a message holding DNS queries.

        @type message: L{Message}
        """
        s = message.toStr()
        self.transport.write(struct.pack('!H', len(s)) + s)

    def connectionMade(self):
        """
        Connection is made: reset internal state, and notify the controller.
        """
        self.liveMessages = {}
        self.controller.connectionMade(self)


    def connectionLost(self, reason):
        """
        Notify the controller that this protocol is no longer
        connected.
        """
        self.controller.connectionLost(self)


    def dataReceived(self, data):
        self.buffer += data

        while self.buffer:
            if self.length is None and len(self.buffer) >= 2:
                self.length = struct.unpack('!H', self.buffer[:2])[0]
                self.buffer = self.buffer[2:]

            if len(self.buffer) >= self.length:
                myChunk = self.buffer[:self.length]
                m = Message()
                m.fromStr(myChunk)

                try:
                    d, canceller = self.liveMessages[m.id]
                except KeyError:
                    self.controller.messageReceived(m, self)
                else:
                    del self.liveMessages[m.id]
                    canceller.cancel()
                    # XXX we shouldn't need this hack
                    try:
                        d.callback(m)
                    except:
                        log.err()

                self.buffer = self.buffer[self.length:]
                self.length = None
            else:
                break


    def query(self, queries, timeout=60):
        """
        Send out a message with the given queries.

        @type queries: C{list} of C{Query} instances
        @param queries: The queries to transmit

        @rtype: C{Deferred}
        """
        id = self.pickID()
        return self._query(queries, timeout, id, self.writeMessage)
