# Twisted, the Framework of Your Internet
# Copyright (C) 2001 Matthew W. Lefkowitz
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of version 2.1 of the GNU Lesser General Public
# License as published by the Free Software Foundation.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

"""
DNS protocol implementation.

API Stability: Unstable

Future Plans: Get rid of some toplevels, maybe.  Put in a better
  lookupRecordType implementation.

@author: U{Moshe Zadka<mailto:moshez@twistedmatrix.com>},
         U{Jp Calderone<mailto:exarkun@twistedmatrix.com}
"""

# System imports
import StringIO, struct, random, types
from socket import inet_aton, inet_ntoa

# Twisted imports
from twisted.internet import protocol, defer, error
from twisted.python import log, util


PORT = 53

QUERY_TYPES = {
    1:  'A',     2:  'NS',    3:  'MD',   4:   'MF',
    5:  'CNAME', 6:  'SOA',   7:  'MB',   8:   'MG',
    9:  'MR',    10: 'NULL',  11: 'WKS',  12:  'PTR',
    13: 'HINFO', 14: 'MINFO', 15: 'MX',   16:  'TXT',

    17: 'RP',    18: 'AFSDB', 
    # 19 through 32?  Eh, I'll get to 'em.

    33: 'SRV'
}

# "Extended" queries (Hey, half of these are deprecated, good job)
EXT_QUERIES = {
    251: 'IXFR',  252: 'AXFR',       253: 'MAILB',
    254: 'MAILA', 255: 'ALL_RECORDS'
}
REV_TYPES = util.dict([
    (v, k) for (k, v) in QUERY_TYPES.items() + EXT_QUERIES.items()
])
for (k, v) in REV_TYPES.items():
    exec "%s = %d" % (k, v)
del k, v


QUERY_CLASSES = {
    1: 'IN',  2: 'CS',  3: 'CH',  4: 'HS',  255: 'ANY'
}
REV_CLASSES = util.dict([
    (v, k) for (k, v) in QUERY_CLASSES.items()
])
for (k, v) in REV_CLASSES.items():
    exec "%s = %d" % (k, v)
del k, v


# Opcodes
OP_QUERY, OP_INVERSE, OP_STATUS = range(3)

# Response Codes
OK, EFORMAT, ESERVER, ENAME, ENOTIMP, EREFUSED = range(6)

class DomainError(ValueError):
    pass


class AuthoritativeDomainError(ValueError):
    pass


def str2time(s):
    suffixes = (
        ('M', 60), ('H', 60 * 60), ('D', 60 * 60 * 24),
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


def readPrecisely( file, l ):
    buff = file.read( l )
    if len( buff ) < l:
        raise EOFError
    return buff


class IEncodable:
    """
    Interface for something which can be encoded to and decoded
    from a file object.
    """
    def encode(self, strio, compDict = None):
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
    
    def decode(self, strio, length = None):
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


class Name:
    __implements__ = (IEncodable,)


    def __init__(self, name=''):
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
                if compDict.has_key(name):
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


    def decode(self, strio, length = None):
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


    def __str__(self):
        return self.name


class Query:
    """
    Represent a single DNS query.

    @ivar name: The name about which this query is requesting information.
    @ivar type: The query type.
    @ivar cls: The query class.
    """

    __implements__ = (IEncodable,)

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
    
    
    def __str__(self):
        t = QUERY_TYPES.get(self.type, EXT_QUERIES.get(self.type, 'UNKNOWN (%d)' % self.type))
        c = QUERY_CLASSES.get(self.cls, 'UNKNOWN (%d)' % self.cls)
        return '<Query %s %s %s>' % (self.name, t, c)


    def __repr__(self):
        return 'Query(%r, %r, %r)' % (str(self.name), self.type, self.cls)


class RRHeader:
    """
    A resource record header.
    
    @cvar fmt: C{str} specifying the byte format of an RR.
    
    @ivar name: The name about which this reply contains information.
    @ivar type: The query type of the original request.
    @ivar cls: The query class of the original request.
    @ivar ttl: The time-to-live for this record.
    @ivar payload: An object that implements the IEncodable interface
    """

    __implements__ = (IEncodable,)
 
    fmt = "!HHIH"
    
    name = None
    type = None
    cls = None
    ttl = None
    payload = None
    rdlength = None
    
    cachedResponse = None

    def __init__(self, name='', type=A, cls=IN, ttl=0, payload=None):
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
        self.name = Name(name)
        self.type = type
        self.cls = cls
        self.ttl = ttl
        self.payload = payload


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


    def __str__(self):
        t = QUERY_TYPES.get(self.type, EXT_QUERIES.get(self.type, 'UNKNOWN (%d)' % self.type))
        c = QUERY_CLASSES.get(self.cls, 'UNKNOWN (%d)' % self.cls)
        return '<RR %s %s %s %ds>' % (self.name, t, c, self.ttl)


    def __repr__(self):
        return 'RR(%r, %d, %d, %d)' % (
            str(self.name), self.type, self.cls, self.ttl
        )


class SimpleRecord:
    """
    A Resource Record which consists of a single RFC 1035 domain-name.
    """
    TYPE = None
    
    __implements__ = (IEncodable,)
    name = None

    def __init__(self, name = ''):
        self.name = Name(name)


    def encode(self, strio, compDict = None):
        self.name.encode(strio, compDict)


    def decode(self, strio, length = None):
        self.name = Name()
        self.name.decode(strio)
    

    def __eq__(self, other):
        if isinstance(other, SimpleRecord):
            return self.name == other.name
        return 0


    def __str__(self):
        return '<%s %s>' % (QUERY_TYPES[self.TYPE], self.name)
    
    
    def xfrString(self):
        return '%s %s' % (QUERY_TYPES[self.TYPE], self.name)


# Kinds of RRs - oh my!
class Record_NS(SimpleRecord):
    TYPE = NS

class Record_MD(SimpleRecord):       # OBSOLETE
    TYPE = MD

class Record_MF(SimpleRecord):       # OBSOLETE
    TYPE = MF

class Record_CNAME(SimpleRecord):
    TYPE = CNAME

class Record_MB(SimpleRecord):       # EXPERIMENTAL
    TYPE = MB

class Record_MG(SimpleRecord):       # EXPERIMENTAL
    TYPE = MG

class Record_MR(SimpleRecord):       # EXPERIMENTAL
    TYPE = MR

class Record_PTR(SimpleRecord):
    TYPE = PTR


class Record_A:
    __implements__ = (IEncodable,)

    TYPE = A
    address = None

    def __init__(self, address = 0):
        if isinstance(address, types.StringType):
            address = inet_aton(address)
        self.address = address


    def encode(self, strio, compDict = None):
        strio.write(self.address)


    def decode(self, strio, length = None):
        self.address = readPrecisely(strio, 4)


    def __eq__(self, other):
        if isinstance(other, Record_A):
            return other.address == self.address
        return 0


    def __str__(self):
        return '<A %s>' % (inet_ntoa(self.address),)


    def xfrString(self):
        return 'A %s' % (inet_ntoa(self.address),)


class Record_SOA:
    __implements__ = (IEncodable,)

    TYPE = SOA
    
    def __init__(self, mname = '', rname = '', serial = 0, refresh = 0, retry = 0, expire = 0, minimum = 0):
        self.mname, self.rname = Name(mname), Name(rname)
        self.serial, self.refresh = str2time(serial), str2time(refresh)
        self.minimum, self.expire = str2time(minimum), str2time(expire)
        self.retry = str2time(retry)


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
    
    
    def __eq__(self, other):
        if isinstance(other, Record_SOA):
            return (self.serial == other.serial and 
                    self.mname == other.mname and
                    self.rname == other.rname and
                    self.refresh == other.refresh and
                    self.expire == other.expire and
                    self.retry == other.retry)
        return 0


    def __str__(self):
        return '<SOA %s %s serial=%d refresh=%d retry=%d expire=%d min=%d>' % (
            self.mname, self.rname, self.serial, self.refresh,
            self.retry, self.expire, self.minimum
        )
    
    
    def xfrString(self):
        return 'SOA %s %s %d %d %d %d %d' % (
            self.mname, self.rname, self.serial, self.refresh,
            self.retry, self.expire, self.minimum
        )


class Record_NULL:                   # EXPERIMENTAL
    __implements__ = (IEncodable,)
    TYPE = NULL

    def __init__(self, payload = None):
        self.payload = payload
    
    
    def encode(self, strio, compDict = None):
        raise NotImplementedError, "Cannot encode or decode NULL records"
    
    
    def decode(self, strio, length = None):
        raise NotImplementedError, "Cannot encode or decode NULL records"
    
    
    def xfrString(self):
        raise NotImplementederror, "Cannot XFR NULL records"


class Record_WKS:                    # OBSOLETE
    __implements__ = (IEncodable,)
    TYPE = WKS

    def __init__(self, address = 0, protocol = 0, map = ''):
        self.address, self.protocol, self.map = address, protocol, map


    def encode(self, strio, compDict = None):
        strio.write(
            struct.pack(
                '!LB',
                self.address, self.protocol
            ) + self.map
        )
    
    
    def decode(self, strio, length = None):
        L = struct.calcsize('!LB')
        r = struct.unpack('!LB', readPrecisely(strio, L))
        self.address, self.protocol = r
        self.map = readPrecisely(strio, length - L)


    def __eq__(self, other):
        if isinstance(other, Record_WKS):
            return (self.address == other.address and
                    self.protocol == other.protocol and
                    self.map == other.map)
        return 0


    def __str__(self):
        return '<WKS addr=%s proto=%d>' % (self.address, self.protocol)
    
    
    def xfrString(self):
        r = []
        for i in range(len(self.map)):
            for j in range(8):
                if self.map[i] & (1 << j):
                    r.append(i * 8 + j)
        return 'WKS %s %d %s' % (
            socket.inet_ntoa(self.address), self.protocol,
            ' '.join(map(str, r))
        )


class Record_SRV:                # EXPERIMENTAL
    __implements__ = (IEncodable,)
    TYPE = SRV
    
    def __init__(self, priority = 0, weight = 0, port = 0, target = ''):
        self.priority = int(priority)
        self.weight = int(weight)
        self.port = int(port)
        self.target = Name(target)
    
    
    def encode(self, strio, compDict = None):
        strio.write(struct.pack('!HHH', self.priority, self.weight, self.port))
        self.target.encode(strio, compDict)
    
    
    def decode(self, strio, length = None):
        r = struct.unpack('!HHH', readPrecisely(strio, struct.calcsize('!HHH')))
        self.priority, self.weight, self.port = r
        self.target = Name()
        self.target.decode(strio)
    
    
    def __eq__(self, other):
        if isinstance(other, Record_SRV):
            return (self.priority == other.priority and
                    self.weight == other.weight and
                    self.port == other.port and
                    self.target == other.target)
        return 0
    
    
    def __str__(self):
        return '<SRV prio=%d weight=%d %s:%d>' % (
            self.priority, self.weight, str(self.target), self.port
        )
    
    
    def xfrString(self):
        return 'SRV %d %d %d %s' % (
            self.priority, self.weight,
            self.port, self.target
        )


class Record_AFSDB:
    __implements__ = (IEncodable,)
    TYPE = AFSDB
    
    def __init__(self, subtype = 0, hostname = ''):
        self.subtype = int(subtype)
        self.hostname = Name(hostname)
    
    
    def encode(self, strio, compDict = None):
        strio.write(struct.pack('!H', self.subtype))
        self.hostname.encode(strio, compDict)
    
    
    def decode(self, strio, length = None):
        r = struct.unpack('!H', readPrecisely(strio, struct.calcsize('!H')))
        self.subtype, = r
        self.hostname.decode(strio)
    
    
    def __eq__(self, other):
        if isinstance(other, Record_AFSDB):
            return (self.subtype == other.subtype and
                    self.hostname == other.hostname)
        return 0
    
    
    def __str__(self):
        return '<AFSB subtype=%d %s>' % (self.subtype, self.hostname)
    
    
    def xfrString(self):
        return 'AFSB %d %s' % (self.subtype, self.hostname)


class Record_RP:
    __implements__ = (IEncodable,)
    TYPE = RP
    
    def __init__(self, mbox = '', txt = ''):
        self.mbox = Name(mbox)
        self.txt = Name(txt)
    
    
    def encode(self, strio, compDict = None):
        self.mbox.encode(strio, compDict)
        self.txt.encode(strio, compDict)
    
    
    def decode(self, strio, length = None):
        self.mbox = Name()
        self.txt = Name()
        self.mbox.decode(strio)
        self.txt.decode(strio)


    def __eq__(self, other):
        if isinstance(other, Record_RP):
            return (self.mbox == other.mbox and 
                    self.txt == other.txt)
        return 0
    
    
    def __str__(self):
        return '<RP mbox=%s txt=%s>' % (self.mbox, self.txt)
    
    
    def xfrString(self):
        return 'RP %s %s' % (self.mbox, self.txt)


class Record_HINFO:
    __implements__ = (IEncodable,)
    TYPE = HINFO

    def __init__(self, cpu = '', os = ''):
        self.cpu, self.os = cpu, os


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
                    self.cpu.lower() == other.cpu.lower())
        return 0


    def __str__(self):
        return '<HINFO cpu=%s os=%s>' % (self.cpu, self.os)
    
    
    def xfrString(self):
        return 'HINFO %s %s' % (self.cpu, self.os)


class Record_MINFO:                 # EXPERIMENTAL
    __implements__ = (IEncodable,)
    TYPE = MINFO
    
    rmailbx = None
    emailbx = None

    def __init__(self, rmailbx = '', emailbx = ''):
        self.rmailbx, self.emailbx = Name(rmailbx), Name(emailbx)
    
    
    def encode(self, strio, compDict = None):
        self.rmailbx.encode(strio, compDict)
        self.emailbx.encode(strio, compDict)
    
    
    def decode(self, strio, length = None):
        self.rmailbx, self.emailbx = Name(), Name()
        self.rmailbx.decode(strio)
        self.emailbx.decode(strio)


    def __eq__(self, other):
        if isinstance(other, Record_MINFO):
            return (self.rmailbx == other.rmailbx and
                    self.emailbx == other.emailbx)
        return 0


    def __str__(self):
        return '<MINFO responsibility=%s errors=%s>' % (self.rmailbx, self.emailbx)


    def xfrString(self):
        return 'MINFO %s %s' % (self.rmailbx, self.emailbx)


class Record_MX:
    __implements__ = (IEncodable,)
    TYPE = MX

    def __init__(self, preference = 0, exchange = ''):
        self.preference, self.exchange = int(preference), Name(exchange)


    def encode(self, strio, compDict = None):
        strio.write(struct.pack('!H', self.preference))
        self.exchange.encode(strio, compDict)


    def decode(self, strio, length = None):
        self.preference = struct.unpack('!H', readPrecisely(strio, 2))[0]
        self.exchange = Name()
        self.exchange.decode(strio)


    def __eq__(self, other):
        if isinstance(other, Record_MX):
            return (self.preference == other.preference and
                    self.exchange == other.exchange)
        return 0


    def __str__(self):
        return '<MX %d %s>' % (self.preference, self.exchange)
    
    
    def xfrString(self):
        return 'MX %d %s' % (self.preference, self.exchange)


# Oh god, Record_TXT how I hate thee.
class Record_TXT:
    __implements__ = (IEncodable,)

    TYPE = TXT
    def __init__(self, *data):
        self.data = list(data)
    
    
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
                "Decoded %d bytes in TXT record, but rdlength is %d" % (
                    soFar, length
                )
            )


    def __eq__(self, other):
        if isinstance(other, Record_TXT):
            return self.data == other.data
        return 0
    
    
    def __str__(self):
        return '<TXT %r>' % self.data
    
    
    def xfrString(self):
        return 'TXT ' + ' '.join(map(repr, self.data))


class Message:
    headerFmt = "!H2B4H"
    headerSize = struct.calcsize( headerFmt )

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
        self.ns = []
        self.add = []


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
        for q in self.ns:
            q.encode(body_tmp, compDict)
        for q in self.add:
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
                                len(self.ns), len(self.add)))
        strio.write(body)


    def decode(self, strio, length = None):
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

        items = ((self.answers, nans), (self.ns, nns), (self.add, nadd))
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
            header.payload = t()
            try:
                header.payload.decode(strio, header.rdlength)
            except EOFError:
                return
            list.append(header)


    def lookupRecordType(self, type):
        return globals().get('Record_' + QUERY_TYPES.get(type, ''), None)


    def toStr(self):
        strio = StringIO.StringIO()
        self.encode(strio)
        return strio.getvalue()


    def fromStr(self, str):
        strio = StringIO.StringIO(str)
        self.decode(strio)


class DNSDatagramProtocol(protocol.DatagramProtocol):
    id = None
    liveMessages = None
    
    timeout = 10
    reissue = 1
    
    def __init__(self, controller):
        self.controller = controller
        self.liveMessages = {}
        self.id = random.randrange(2 ** 10, 2 ** 15)


    def pickID(self):
        self.id += 1
        return self.id


    def writeMessage(self, message, address):
        if not self.transport:
            from twisted.internet import reactor
            reactor.listenUDP(0, self, maxPacketSize=512)
        self.transport.write(message.toStr(), address)


    def datagramReceived(self, data, addr):
        m = Message()
        m.fromStr(data)
        try:
            d, i = self.liveMessages[m.id]
        except KeyError:
            self.controller.messageReceived(m, self, addr)
        else:
            del self.liveMessages[m.id]
            d.callback(m)
            i.cancel()


    def _reissueQuery(self, message, address, counter, timer):
        d, _ = self.liveMessages[message.id]
        if counter <= 0:
            d.errback(defer.TimeoutError(message.queries))
            del self.liveMessages[message.id]
        else:
            from twisted.internet import reactor
            self.writeMessage(message, address)
            self.liveMessages[message.id] = (
                d,
                reactor.callLater(
                    timer, self._reissueQuery, message, address,
                    counter - 1, timer
                )
            )


    def query(self, address, queries, timeout = None, reissue = None):
        """
        Send out a message with the given queries.
        
        @type name: C{str}
        @param name: The name about which to request information.
        
        @type address: C{tuple} of C{str} and C{int}
        @param address: The address to which to send the query
        
        @type queries: C{list} of C{Query} instances
        @param queries: The queries to transmit
        
        @rtype: C{Deferred}
        """
        from twisted.internet import reactor
        id = self.pickID()
        m = Message(id, recDes=1)
        m.queries = queries

        if timeout is None:
            timeout = self.timeout
        if reissue is None:
            reissue = self.reissue

        d, _ = self.liveMessages[id] = (
            defer.Deferred(),
            reactor.callLater(
                reissue, self._reissueQuery, m, address,
                int(timeout / float(reissue)), reissue
            )
        )
        self.writeMessage(m, address)
        return d


class DNSProtocol(protocol.Protocol):
    id = None
    liveMessages = None

    length = None
    buffer = ''
    d = None


    def __init__(self, controller):
        self.controller = controller
        self.liveMessages = {}
        self.id = random.randrange(2 ** 10, 2 ** 15)


    def pickID(self):
        self.id += 1
        return self.id


    def writeMessage(self, message):
        s = message.toStr()
        self.transport.write(struct.pack('!H', len(s)) + s)


    def connectionMade(self):
        self.controller.connectionMade(self)


    def dataReceived(self, data):
        self.buffer = self.buffer + data
        if self.length is None and len(self.buffer) >= 2:
            self.length = struct.unpack('!H', self.buffer[:2])[0]
            self.buffer = self.buffer[2:]

        if len(self.buffer) == self.length:
            m = Message()
            m.fromStr(self.buffer)
            
            try:
                d = self.liveMessages[m.id]
            except KeyError:
                self.controller.messageReceived(m, self)
            else:
                del self.liveMessages[m.id]
                d.callback(m)


    def query(self, queries, timeout = None):
        """
        Send out a message with the given queries.
        
        @type name: C{str}
        @param name: The name about which to request information.
        
        @type queries: C{list} of C{Query} instances
        @param queries: The queries to transmit
        
        @rtype: C{Deferred}
        """
        id = self.pickID()
        d = self.liveMessages[id] = defer.Deferred()
        m = Message(id, recDes=1)
        m.queries = queries
        self.writeMessage(m)
        return d
