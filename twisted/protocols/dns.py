# -*- test-case-name: twisted.test.test_dns -*-
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

Future Plans: 
    - Get rid of some toplevels, maybe.  
    - Put in a better lookupRecordType implementation.

@author: U{Moshe Zadka<mailto:moshez@twistedmatrix.com>},
         U{Jp Calderone<mailto:exarkun@twistedmatrix.com}
"""

# System imports
import struct, random, types, socket
from math import ceil, floor
try:
    import cStringIO as StringIO
except ImportError:
    import StringIO

AF_INET6 = getattr(socket, 'AF_INET6', 'AF_INET6')

try:
    from Crypto.Util import randpool
except ImportError:
    for randSource in ('random', 'srandom', 'urandom'):
        try:
            f = file('/dev/' + randSource)
            f.read(2)
            f.close()
        except:
            pass
        else:
            def randomSource(r = file('/dev/' + randSource, 'rb').read):
                return struct.unpack('H', r(2))[0]
            break
    else:
        import warnings
        warnings.warn(
            "PyCrypto not available - proceeding with non-cryptographically "
            "secure random source",
            RuntimeWarning,
            1
        )

        def randomSource():
            return random.randint(0, 65535)
else:
    def randomSource(r = randpool.RandomPool().get_bytes):
        return struct.unpack('H', r(2))[0]

# Twisted imports
from twisted.internet import protocol, defer, error
from twisted.python import log, failure
from twisted.python import util as tputil
from twisted.python import components

PORT = 53

QUERY_TYPES = {
    1:  'A',     2:  'NS',    3:  'MD',   4:   'MF',
    5:  'CNAME', 6:  'SOA',   7:  'MB',   8:   'MG',
    9:  'MR',    10: 'NULL',  11: 'WKS',  12:  'PTR',
    13: 'HINFO', 14: 'MINFO', 15: 'MX',   16:  'TXT',

    17: 'RP',    18: 'AFSDB', 
    # 19 through 32?  Eh, I'll get to 'em.
    
    28: 'AAAA',

    33: 'SRV',
    
    38: 'A6', 39: 'DNAME'
}

# "Extended" queries (Hey, half of these are deprecated, good job)
EXT_QUERIES = {
    251: 'IXFR',  252: 'AXFR',       253: 'MAILB',
    254: 'MAILA', 255: 'ALL_RECORDS'
}
REV_TYPES = dict([
    (v, k) for (k, v) in QUERY_TYPES.items() + EXT_QUERIES.items()
])
for (k, v) in REV_TYPES.items():
    exec "%s = %d" % (k, v)
del k, v


QUERY_CLASSES = {
    1: 'IN',  2: 'CS',  3: 'CH',  4: 'HS',  255: 'ANY'
}
REV_CLASSES = dict([
    (v, k) for (k, v) in QUERY_CLASSES.items()
])
for (k, v) in REV_CLASSES.items():
    exec "%s = %d" % (k, v)
del k, v


# Opcodes
OP_QUERY, OP_INVERSE, OP_STATUS, OP_NOTIFY = range(4)

# Response Codes
OK, EFORMAT, ESERVER, ENAME, ENOTIMP, EREFUSED = range(6)

class IRecord(components.Interface):
    """An single entry in a zone of authority.
    
    @cvar TYPE: An indicator of what kind of record this is.
    """

class DomainError(ValueError):
    pass

class AuthoritativeDomainError(ValueError):
    pass

class DNSQueryTimeoutError(defer.TimeoutError):
    def __init__(self, id):
        self.id = id
        defer.TimeoutError.__init__(self)

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


class RRHeader:
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

    __implements__ = (IEncodable,)
 
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
    """
    TYPE = None
    
    __implements__ = (IEncodable, IRecord)
    name = None

    showAttributes = (('name', 'name', '%s'), 'ttl')
    compareAttributes = ('name', 'ttl')

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

class Record_DNAME(SimpleRecord):
    TYPE = DNAME

class Record_A(tputil.FancyEqMixin):
    __implements__ = (IEncodable, IRecord)

    TYPE = A
    address = None

    compareAttributes = ('address', 'ttl')
    
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
        return '<A %s ttl=%s>' % (self.dottedQuad(), self.ttl)


    def dottedQuad(self):
        return socket.inet_ntoa(self.address)


class Record_SOA(tputil.FancyEqMixin, tputil.FancyStrMixin):
    __implements__ = (IEncodable, IRecord)

    compareAttributes = ('serial', 'mname', 'rname', 'refresh', 'expire', 'retry', 'ttl')
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


class Record_NULL:                   # EXPERIMENTAL
    __implements__ = (IEncodable, IRecord)
    TYPE = NULL

    def __init__(self, payload=None, ttl=None):
        self.payload = payload
        self.ttl = str2time(ttl)
    
    
    def encode(self, strio, compDict = None):
        raise NotImplementedError, "Cannot encode or decode NULL records"
    
    
    def decode(self, strio, length = None):
        raise NotImplementedError, "Cannot encode or decode NULL records"


    def __hash__(self):
        return hash(self.payload)
    
    
class Record_WKS(tputil.FancyEqMixin, tputil.FancyStrMixin):                    # OBSOLETE
    __implements__ = (IEncodable, IRecord)
    TYPE = WKS

    compareAttributes = ('address', 'protocol', 'map', 'ttl')
    showAttributes = ('address', 'protocol', 'ttl')

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

    
class Record_AAAA(tputil.FancyEqMixin):               # OBSOLETE (or headed there)
    __implements__ = (IEncodable, IRecord)
    TYPE = AAAA

    compareAttributes = ('address', 'ttl')

    def __init__(self, address = '::', ttl=None):
        self.address = socket.inet_pton(AF_INET6, address)
        self.ttl = str2time(ttl)


    def encode(self, strio, compDict = None):
        strio.write(self.address)


    def decode(self, strio, length = None):
        self.address = readPrecisely(strio, 16)


    def __hash__(self):
        return hash(self.address)


    def __str__(self):
        return '<AAAA %s ttl=%s>' % (socket.inet_ntop(AF_INET6, self.address), self.ttl)


class Record_A6:
    __implements__ = (IEncodable, IRecord)
    TYPE = A6
    
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
        return 0


    def __hash__(self):
        return hash((self.prefixLen, self.suffix[-self.bytes:], self.prefix))


    def __str__(self):
        return '<A6 %s %s (%d) ttl=%s>' % (
            self.prefix,
            socket.inet_ntop(AF_INET6, self.suffix),
            self.prefixLen, self.ttl
        )


class Record_SRV(tputil.FancyEqMixin, tputil.FancyStrMixin):                # EXPERIMENTAL
    __implements__ = (IEncodable, IRecord)
    TYPE = SRV

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



class Record_AFSDB(tputil.FancyStrMixin, tputil.FancyEqMixin):
    __implements__ = (IEncodable, IRecord)
    TYPE = AFSDB

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
    __implements__ = (IEncodable, IRecord)
    TYPE = RP

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
    
    

class Record_HINFO(tputil.FancyStrMixin):
    __implements__ = (IEncodable, IRecord)
    TYPE = HINFO

    showAttributes = ('cpu', 'os', 'ttl')

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
        return 0
    
    
    def __hash__(self):
        return hash((self.os.lower(), self.cpu.lower()))



class Record_MINFO(tputil.FancyEqMixin, tputil.FancyStrMixin):                 # EXPERIMENTAL
    __implements__ = (IEncodable, IRecord)
    TYPE = MINFO
    
    rmailbx = None
    emailbx = None

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
    __implements__ = (IEncodable, IRecord)
    TYPE = MX

    compareAttributes = ('preference', 'exchange', 'ttl')
    showAttributes = ('preference', ('exchange', 'exchange', '%s'), 'ttl')

    def __init__(self, preference=0, exchange='', ttl=None):
        self.preference, self.exchange = int(preference), Name(exchange)
        self.ttl = str2time(ttl)


    def encode(self, strio, compDict = None):
        strio.write(struct.pack('!H', self.preference))
        self.exchange.encode(strio, compDict)


    def decode(self, strio, length = None):
        self.preference = struct.unpack('!H', readPrecisely(strio, 2))[0]
        self.exchange = Name()
        self.exchange.decode(strio)


    def __hash__(self):
        return hash((self.preference, self.exchange))


    
# Oh god, Record_TXT how I hate thee.
class Record_TXT(tputil.FancyEqMixin, tputil.FancyStrMixin):
    __implements__ = (IEncodable, IRecord)

    TYPE = TXT

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
                "Decoded %d bytes in TXT record, but rdlength is %d" % (
                    soFar, length
                )
            )


    def __hash__(self):
        return hash(tuple(self.data))
    
    
    
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
    resends = None
    
    timeout = 10
    reissue = 2
    
    def __init__(self, controller):
        self.controller = controller
        self.liveMessages = {}
        self.resends = {}
        self.id = random.randrange(2 ** 10, 2 ** 15)

    def pickID(self):
        while 1:
            self.id += randomSource() % (2 ** 10)
            self.id %= 2 ** 16
            if not self.liveMessages.has_key(self.id):
                break
        return self.id
     
    def stopProtocol(self):
        self.liveMessages = {}
        self.resends = {}
        self.transport = None

    def startProtocol(self):
        self.liveMessages = {}
        self.resends = {}

    def writeMessage(self, message, address):
        if not self.transport:
            # XXX transport might not get created automatically, use callLater?
            from twisted.internet import reactor
            reactor.listenUDP(0, self, maxPacketSize=512)
        self.transport.write(message.toStr(), address)


    def datagramReceived(self, data, addr):
        m = Message()
        m.fromStr(data)
        try:
            d = self.liveMessages[m.id]
        except KeyError, e:
            if not self.resends.has_key(m.id):
                self.controller.messageReceived(m, self, addr)
        else:
            del self.liveMessages[m.id]
            try:
                d.callback(m)
            except:
                log.err()


    def query(self, address, queries, timeout = 10, id = None):
        """
        Send out a message with the given queries.
        
        @type address: C{tuple} of C{str} and C{int}
        @param address: The address to which to send the query
        
        @type queries: C{list} of C{Query} instances
        @param queries: The queries to transmit
        
        @rtype: C{Deferred}
        """
        if id is None:
            id = self.pickID()
        else:
            self.resends[id] = 1
        m = Message(id, recDes=1)
        m.queries = queries
        d = self.liveMessages[id] = defer.Deferred()
        d.setTimeout(timeout, self._clearFailed, id)
        self.writeMessage(m, address)
        return d
        
    def _clearFailed(self, deferred, id):
        try:
            del self.liveMessages[id]
        except:
            pass
        deferred.errback(failure.Failure(DNSQueryTimeoutError(id)))


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
        while 1:
            self.id += randomSource() % (2 ** 10)
            self.id %= 2 ** 16
            if not self.liveMessages.has_key(self.id):
                break
        return self.id


    def writeMessage(self, message):
        s = message.toStr()
        self.transport.write(struct.pack('!H', len(s)) + s)


    def connectionMade(self):
        self.controller.connectionMade(self)


    def dataReceived(self, data):
        self.buffer = self.buffer + data

        while self.buffer:
            if self.length is None and len(self.buffer) >= 2:
                self.length = struct.unpack('!H', self.buffer[:2])[0]
                self.buffer = self.buffer[2:]

            if len(self.buffer) >= self.length:
                myChunk = self.buffer[:self.length]
                m = Message()
                m.fromStr(myChunk)

                try:
                    d = self.liveMessages[m.id]
                except KeyError:
                    self.controller.messageReceived(m, self)
                else:
                    del self.liveMessages[m.id]
                    try:
                        d.callback(m)
                    except:
                        log.err()

                self.buffer = self.buffer[self.length:]
                self.length = None
            else:
                break



    def query(self, queries, timeout = None):
        """
        Send out a message with the given queries.
        
        @type queries: C{list} of C{Query} instances
        @param queries: The queries to transmit
        
        @rtype: C{Deferred}
        """
        id = self.pickID()
        d = self.liveMessages[id] = defer.Deferred()
        if timeout is not None:
            d.setTimeout(timeout)
        m = Message(id, recDes=1)
        m.queries = queries
        self.writeMessage(m)
        return d
