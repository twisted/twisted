
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

from twisted.protocols import protocol

import string, struct, StringIO

QUERY, IQUERY, STATUS = range(3)
OK, EFORMAT, ESERVER, ENAME, ENOTIMP, EREFUSED = range(6)

def readPrecisely( file, l ):
    buff = file.read( l )
    if len( buff ) < l:
        raise EOFError
    return buff


class Name:
    def __init__( self, name = '' ):
        self.name = name

    def Encode( self, strio, compDict = None ):
        name = self.name
        while name:
            if compDict is not None:
                if compDict.has_key( name ):
                    strio.write(
                        struct.pack( "!H", 0xc000 | compDict[ name ] ) )
                    return
                else:
                    compDict[ name ] = strio.tell() + Message.headerSize
            ind = string.find( name, '.' )
            if ind > 0:
                label,name = name[:ind],name[ind + 1:]
            else:
                label,name = name,''
                ind = len(label)
            strio.write( chr( ind ) )
            strio.write( label )
        strio.write( chr( 0 ) )

    def Decode( self, strio ):
        self.name = ''
        off = 0
        while 1:
            l = ord( readPrecisely( strio, 1 ) )
            if l == 0:
                if off > 0:
                    strio.seek( off )
                return
            if ( l >> 6 ) == 3:
                new_off = ( ( l & 63 ) << 8
                            | ord( readPrecisely( strio, 1 ) ) )
                if ( off == 0 ):
                    off = strio.tell()
                strio.seek( new_off )
                continue
            label = readPrecisely( strio, l )
            if self.name == '':
                self.name = label
            else:
                self.name = self.name + '.' + label

    def __repr__( self ):
        return self.name

class Query:
    def __init__( self, name = '', type = 0, cls = 0 ):
        self.name = Name( name )
        self.type = type
        self.cls = cls

    def Encode( self, strio, compDict = None ):
        self.name.Encode( strio, compDict )
        strio.write( struct.pack( "!HH", self.type, self.cls ) )

    def Decode( self, strio ):
        self.name.Decode( strio )
        buff = readPrecisely( strio, 4 )
        ( self.type, self.cls ) = struct.unpack( "!HH", buff )

class RR:
    fmt = "!HHIH"

    def __init__( self, name = '', type = 0, cls = 0, ttl = 0,
                  data = '' ):
        self.name = Name( name )
        self.type = type
        self.cls = cls
        self.ttl = ttl
        self.data = data

    def Encode( self, strio, compDict = None ):
        self.name.Encode( strio, compDict )
        strio.write( struct.pack( self.fmt, self.type, self.cls,
                                  self.ttl, len( self.data ) ) )
        strio.write( data )

    def Decode( self, strio ):
        self.name.Decode( strio )
        l = struct.calcsize( self.fmt )
        buff = readPrecisely( strio, l )
        ( self.type, self.cls, self.ttl, l ) = struct.unpack( self.fmt,
                                                              buff )
        self.data = readPrecisely( strio, l )

class Message:
    headerFmt = "!H2B4H"
    headerSize = struct.calcsize( headerFmt )

    def __init__(self, id = 0, answer = 0, opCode = 0, recDes = 0, recAv = 0,
                 auth = 0, rCode = OK, trunc = 0, maxSize = 512):
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

    def addQuery( self, name, type = 1, cls = 1 ):
        self.queries.append( Query( name, type, cls ) )

    def Encode( self, strio ):
        compDict = {}
        body_tmp = StringIO.StringIO()
        for q in self.queries:
            q.Encode( body_tmp, compDict )
        body = body_tmp.getvalue()
        size = len( body ) + self.headerSize
        if self.maxSize and size > self.maxSize:
            self.trunc = 1
            body = body[:maxSize - self.headerSize]
        byte3 = ( ( ( self.answer & 1 ) << 7 )
                  | ( ( self.opCode & 0xf ) << 3 )
                  | ( ( self.auth & 1 ) << 2 )
                  | ( ( self.trunc & 1 ) << 1 )
                  | ( self.recDes & 1 ) )
        byte4 = ( ( ( self.recAv & 1 ) << 7 )
                  | ( self.rCode & 0xf ) )
        strio.write( struct.pack( self.headerFmt, self.id, byte3, byte4,
                                  len( self.queries ), 0, 0, 0) )
        strio.write( body )

    def Decode( self, strio ):
        self.maxSize = 0
        header = readPrecisely( strio, self.headerSize )
        ( self.id, byte3, byte4, nqueries, nans,
          nns, nadd ) = struct.unpack( self.headerFmt, header )
        self.answer = ( byte3 >> 7 ) & 1
        self.opCode = ( byte3 >> 3 ) & 0xf
        self.auth = ( byte3 >> 2 ) & 1
        self.trunc = ( byte3 >> 1 ) & 1
        self.recDes = byte3 & 1
        self.recAv = ( byte4 >> 7 ) & 1
        self.rCode = byte4 & 0xf

        eof = 0

        for list, num, cls in ( ( self.queries, nqueries, Query ),
                                ( self.answers, nans, RR ),
                                ( self.ns, nns, RR ),
                                ( self.add, nadd, RR ) ):
            list[:] = []
            if not eof:
                for i in range( num ):
                    element = cls()
                    try:
                        element.Decode( strio )
                    except EOFError:
                        eof = 1
                        break
                    else:
                        list.append( element )

    def toStr( self ):
        strio = StringIO.StringIO()
        self.Encode( strio )
        return strio.getvalue()

    def fromStr( self, str ):
        strio = StringIO.StringIO( str )
        self.Decode( strio )


class DNS( protocol.Protocol ):
    underlying = "udp"

    def dataReceived( self, data ):
        message = Message()
        message.fromStr( data )
        if message.answer == 0:
            message.answer = 1
            message.rCode = ENOTIMP
            self.writeMessage( message )
            self.transport.loseConnection()
        else:
            self.factory.boss.accomplish( message.id,
                                          message )
            self.transport.loseConnection()

    def writeMessage( self, message ):
        if not self.connected:
            raise "Not connected"
        self.transport.write( message.toStr() )

    def query( self, name, callback ):
        id = self.factory.boss.addPending( callback )
        message = Message( id )
        message.addQuery( name )
        self.writeMessage( message )


class DNSOnTCP( DNS ):
    underlying = "tcp"
    _query = None

    def connectionMade( self ):
        if self._query:
            apply(self.query, self._query)
            self._query = None
        self.buffer = ''

    def connectionLost( self ):
        del self.buffer

    def dataReceived( self, data ):
        self.buffer = self.buffer + data
        while len( self.buffer ) >= 2:
            size = struct.unpack( "!H", self.buffer[ : 2 ] )[ 0 ]
            if len( self.buffer ) >= size + 2:
                DNS.dataReceived( self, self.buffer[ 2 : size + 2 ] )
                self.buffer = self.buffer[ size + 2 : ]

    def setQuery(self, name, callback):
        self._query = name, callback

    def writeMessage(self, message):
        if not self.connected:
            raise "Not connected"
        str = message.toStr()
        self.transport.write( struct.pack( "!H", len( str ) )
                              + str )
