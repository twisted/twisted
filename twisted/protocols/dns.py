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
UDP DNS protocol implementation.

Stability: Unstable

Future plans: TCP protocol implementation, intelligent handling of
  more RR types.

@author: U{Moshe Zadka<mailto:moshez@twistedmatrix.com>},
         U{Jp Calderone<mailto:exarkun@twistedmatrix.com}
"""

# System imports
import StringIO, random, struct

# Twisted imports
from twisted.internet import protocol, defer

QUERY_TYPES = {
    1:  'A',     2:  'NS',    3:  'MD',   4:   'MF',
    5:  'CNAME', 6:  'SOA',   7:  'MB',   8:   'MG',
    9:  'MR',    10: 'NULL',  11: 'MKS',  12:  'PTR',
    13: 'HINFO', 14: 'MINFO', 15: 'MX',   16: 'TXT',
    
    252: 'AFRX', 253: 'MAILB', 254: 'MAILA', 255: 'ALL_RECORDS'
}
REV_TYPES = dict([
    (v, k) for (k, v) in QUERY_TYPES.items()
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
QUERY, IQUERY, STATUS = range(3)

# Response Codes
OK, EFORMAT, ESERVER, ENAME, ENOTIMP, EREFUSED = range(6)


def readPrecisely( file, l ):
    buff = file.read( l )
    if len( buff ) < l:
        raise EOFError
    return buff


class Name:
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


    def decode(self, strio):
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


    def __str__(self):
        return '<Name %r>' % (self.name,)


    def __repr__(self):
        return 'Name(%r)' % (self.name,)


class Query:
    """
    Represent a single DNS query.

    @ivar name: The name about which this query is requesting information.
    @ivar type: The query type.
    @ivar cls: The query class.
    """

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


    def decode(self, strio):
        self.name.decode(strio)
        buff = readPrecisely(strio, 4)
        self.type, self.cls = struct.unpack("!HH", buff)
    
    
    def __str__(self):
        return '<Query %s %s %d>' % (self.name, QUERY_TYPES[self.type], self.cls)


    def __repr__(self):
        return 'Query(%r, %r, %r)' % (self.name.name, self.type, self.cls)


class RR:
    """
    A resource record.
    
    @cvar fmt: C{str} specifying the byte format of an RR.
    
    @ivar name: The name about which this reply contains information.
    @ivar type: The query type of the original request.
    @ivar cls: The query class of the original request.
    @ivar ttl: The time-to-live for this record.
    @ivar data: Query Type specific reply information.
    
      For A requests, a dotted-quad IP addresses in C{str} form
      For NS requests, a hostname
      For MX requests, a C{tuple} of C{(preference, hostname)}
      
      For all other requests, a C{str} containing the reply data.
    """

    fmt = "!HHIH"
    
    name = None
    type = None
    cls = None
    ttl = None
    data = None

    def __init__(self, name='', type=A, cls=IN, ttl=0, data = ''):
        """
        @type name: C{str}
        @param name: The name about which this reply contains information.
        
        @type type: C{int}
        @param type: The query type.
        
        @type cls: C{int}
        @param cls: The query class.
        
        @type ttl: C{int}
        @param ttl: Time to live for this record.
        
        @type data: C{str}
        @param data: Encoded data string.
        """
        self.name = Name(name)
        self.type = type
        self.cls = cls
        self.ttl = ttl
        self.data = data

    def encode(self, strio, compDict=None):
        self.name.encode(strio, compDict)
        strio.write(struct.pack(self.fmt, self.type, self.cls,
                                self.ttl, len( self.data)))
        strio.write(self.data)

    def decode(self, strio):
        self.name.decode(strio)
        l = struct.calcsize(self.fmt)
        buff = readPrecisely(strio, l)
        self.type, self.cls, self.ttl, l = struct.unpack(self.fmt, buff )
        
        if self.type == MX:
            pref = struct.unpack('!H', readPrecisely(strio, 2))[0]
            name = Name()
            name.decode(strio)
            self.data = pref, name
        elif self.type == NS:
            self.data = Name()
            self.data.decode(strio)
        elif self.type == A:
            quads = map(ord, readPrecisely(strio, l))
            self.data = '.'.join(map(str, quads))
        else:
            self.data = readPrecisely(strio, l)


        # Moshe - temp
        self.strio = strio
        self.strioOff = strio.tell()-l
    
    
    def __str__(self):
        return '<RR %s %s %s %d>' % (
            self.name, QUERY_TYPES[self.type],
            QUERY_CLASSES[self.cls], self.ttl
        )

    def __repr__(self):
        return 'RR(%r, %d, %d, %d, %r)' % (
            self.name.name, self.type, self.cls,
            self.ttl, self.data
        )


class Message:
    headerFmt = "!H2B4H"
    headerSize = struct.calcsize( headerFmt )

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
            body = body[:maxSize - self.headerSize]
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


    def decode(self, strio):
        self.maxSize = 0
        header = readPrecisely(strio, self.headerSize)
        (self.id, byte3, byte4, nqueries, nans,
         nns, nadd) = struct.unpack(self.headerFmt, header)
        self.answer = ( byte3 >> 7 ) & 1
        self.opCode = ( byte3 >> 3 ) & 0xf
        self.auth = ( byte3 >> 2 ) & 1
        self.trunc = ( byte3 >> 1 ) & 1
        self.recDes = byte3 & 1
        self.recAv = ( byte4 >> 7 ) & 1
        self.rCode = byte4 & 0xf

        eof = 0

        for list, num, cls in ( (self.queries, nqueries, Query),
                                (self.answers, nans, RR),
                                (self.ns, nns, RR),
                                (self.add, nadd, RR) ):
            list[:] = []
            if not eof:
                for i in range(num):
                    element = cls()
                    try:
                        element.decode(strio)
                    except EOFError:
                        eof = 1
                        break
                    else:
                        list.append(element)


    def toStr(self):
        strio = StringIO.StringIO()
        self.encode(strio)
        return strio.getvalue()


    def fromStr(self, str):
        strio = StringIO.StringIO(str)
        self.decode(strio)


class DNSClientProtocol(protocol.ConnectedDatagramProtocol):
    id = 1000

    def __init__(self):
        self.liveMessages = {}


    def datagramReceived(self, data):
        m = Message()
        m.fromStr(data)
        if not m.answer:
            return # XXX - Log this?
        if not self.liveMessages.has_key(m.id):
            return # XXX - Log this?
        
        self.liveMessages[m.id].callback(m)
        del self.liveMessages[m.id]


    def writeMessage(self, message):
        self.transport.write(message.toStr())


    def query(self, name, type=ALL_RECORDS, cls=IN):
        """
        Send out a query message.
        
        @type name: C{str}
        @param name: The name about which to request information.
        
        @type type: C{int}
        @param type: Query type
        
        @type cls: C{int}
        @param cls: Query class
        
        @rtype: C{Deferred}
        """
        d = self.liveMessages[self.id] = defer.Deferred()
        m = Message(self.id, recDes=1)
        m.addQuery(name, type, cls)
        self.writeMessage(m)
        self.id = self.id + 1
        return d
