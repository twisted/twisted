
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

# Generic List ENcoding

from twisted.protocols import protocol
from twisted.persisted import styles
import types, copy, cStringIO, math, struct

def int2b128(integer, stream):
    if integer == 0:
        stream(chr(0))
        return
    assert integer > 0, "can only encode positive integers"
    while integer:
        stream(chr(integer & 0x7f))
        integer = integer >> 7

def b1282int(st):
    i = 0l
    place = 0
    for char in st:
        num = ord(char)
        i = i + (num * (128 ** place))
        place = place + 1
    try:
        return int(i)
    except:
        return i

# delimiter characters.
LIST     = chr(0x80)
INT      = chr(0x81)
STRING   = chr(0x82)
SYMBOL   = chr(0x83)
NEG      = chr(0x84)
VOCAB    = chr(0x85)
FLOAT    = chr(0x86)

HIGH_BIT_SET = chr(0x80)

class Banana(protocol.Protocol, styles.Ephemeral):
    def connectionMade(self):
        self.listStack = []

    def gotItem(self, item):
        l = self.listStack
        if l:
            l[-1][1].append(item)
        else:
            self.expressionReceived(item)

    buffer = ''

    def dataReceived(self, chunk):
        buffer = self.buffer + chunk
        listStack = self.listStack
        gotItem = self.gotItem
        while buffer:
            assert self.buffer != buffer, "This ain't right: %s %s" % (repr(self.buffer), repr(buffer))
            self.buffer = buffer
            pos = 0
            for ch in buffer:
                if ch >= HIGH_BIT_SET:
                    break
                pos = pos + 1
            else:
                if pos > 64:
                    raise Exception("Security precaution: more than 64 bytes of prefix")
                return
            num = buffer[:pos]
            typebyte = buffer[pos]
            rest = buffer[pos+1:]
            if len(num) > 64:
                raise Exception("Security precaution: longer than 64 bytes worth of prefix")
            if typebyte == LIST:
                num = b1282int(num)
                listStack.append((num, []))
                buffer = rest
            elif typebyte == STRING:
                num = b1282int(num)
                if num > 640 * 1024: # 640k is all you'll ever need :-)
                    raise Exception("Security precaution: Length identifier too long.")
                if len(rest) >= num:
                    buffer = rest[num:]
                    gotItem(rest[:num])
                else:
                    return
            elif typebyte == INT:
                buffer = rest
                num = b1282int(num)
                gotItem(num)
            elif typebyte == NEG:
                buffer = rest
                num = -b1282int(num)
                gotItem(num)
            elif typebyte == SYMBOL:
                buffer = rest
                num = b1282int(num)
                gotItem(self.incomingVocabulary[num])
            elif typebyte == VOCAB:
                buffer = rest
                num = b1282int(num)
                gotItem(self.incomingVocabulary[-num])
            elif typebyte == FLOAT:
                buffer = rest
                num = float(num)
                gotItem(num)
            else:
                raise NotImplementedError(("Invalid Type Byte %s" % typebyte))
            while listStack and (len(listStack[-1][1]) == listStack[-1][0]):
                item = listStack.pop()[1]
                gotItem(item)
        self.buffer = ''

    def expressionReceived(self, lst):
        """Called when an expression (list, string, or int) is received.
        """
        raise NotImplementedError()


    outgoingVocabulary = {
        # Jelly Data Types
        'None'           :  -1,
        'class'          :  -2,
        'dereference'    :  -3,
        'reference'      :  -4,
        'dictionary'     :  -5,
        'function'       :  -6,
        'instance'       :  -7,
        'list'           :  -8,
        'module'         :  -9,
        'persistent'     : -10,
        'tuple'          : -11,
        'unpersistable'  : -12,

        # PB Data Types
        'copy'           : -13,
        'cache'          : -14,
        'cached'         : -15,
        'remote'         : -16,
        'local'          : -17,
        'lcache'         : -18,

        # PB Protocol Messages
        'version'        : -19,
        'login'          : -20,
        'password'       : -21,
        'challenge'      : -22,
        'logged_in'      : -23,
        'not_logged_in'  : -24,
        'cachemessage'   : -25,
        'message'        : -26,
        'answer'         : -27,
        'error'          : -28,
        'decref'         : -29,
        'decache'        : -30,
        'uncache'        : -31,
        }

    incomingVocabulary = {}
    for k, v in outgoingVocabulary.items():
        incomingVocabulary[v] = k

    def __init__(self):
        self.outgoingSymbols = copy.copy(self.outgoingVocabulary)
        self.outgoingSymbolCount = 0

    def intern(self, sym):
        write = self.transport.write
        self.outgoingSymbolCount = self.outgoingSymbolCount + 1
        self.outgoingSymbols[sym] = self.outgoingSymbolCount

    def sendEncoded(self, obj):
        io = cStringIO.StringIO()
        self._encode(obj, io.write)
        value = io.getvalue()
        self.transport.write(value)

    def _encode(self, obj, write):
        if isinstance(obj, types.ListType) or isinstance(obj, types.TupleType):
            int2b128(len(obj), write)
            write(LIST)
            for elem in obj:
                self._encode(elem, write)
        elif isinstance(obj, types.IntType):
            if obj >= 0:
                int2b128(obj, write)
                write(INT)
            else:
                int2b128(-obj, write)
                write(NEG)
        elif isinstance(obj, types.FloatType):
            write(str(obj))
            write(FLOAT)
        elif isinstance(obj, types.StringType):
            if self.outgoingSymbols.has_key(obj):
                symbolID = self.outgoingSymbols[obj]
                if symbolID < 0:
                    int2b128(-symbolID, write)
                    write(VOCAB)
                else:
                    int2b128(symbolID, write)
                    write(SYMBOL)
            else:
                int2b128(len(obj), write)
                write(STRING)
                write(obj)
        else:
            assert 0, "could not send object: %s" % repr(obj)

class Canana(Banana):
    def connectionMade(self):
        self.state = cBanana.newState()

    def dataReceived(self, chunk):
        buffer = self.buffer + chunk
        processed = cBanana.dataReceived(self.state, buffer, self.expressionReceived)
        self.buffer = buffer[processed:]

Pynana = Banana

try:
    import cBanana
except ImportError:
    #print 'using python banana'
    pass
else:
    #print 'using C banana'
    Banana = Canana

# For use from the interactive interpreter
_i = Banana()
_i.connectionMade()

def encode(lst):
    io = cStringIO.StringIO()
    _i._encode(lst, io.write)
    return io.getvalue()

def decode(st):
    l=[]
    _i.expressionReceived = l.append
    _i.dataReceived(st)
    _i.buffer = ''
    del _i.expressionReceived
    return l[0]
