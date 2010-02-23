# -*- test-case-name: twisted.test.test_banana -*-
# Copyright (c) 2001-2010 Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Banana -- s-exp based protocol.

Future Plans: This module is almost entirely stable.  The same caveat applies
to it as applies to L{twisted.spread.jelly}, however.  Read its future plans
for more details.

@author: Glyph Lefkowitz
"""

import copy, cStringIO, struct

from twisted.internet import protocol
from twisted.persisted import styles
from twisted.python import log

class BananaError(Exception):
    pass

def int2b128(integer, stream):
    if integer == 0:
        stream(chr(0))
        return
    assert integer > 0, "can only encode positive integers"
    while integer:
        stream(chr(integer & 0x7f))
        integer = integer >> 7

cdef _c_b1282int(unsigned char* st, int start, int l):
    e = 1
    i = 0
    cdef int n
    cdef int j
    for j in range(l):
        n = st[start+j]
        i += (n * e)
        e <<= 7
    return i

def b1282int(buf):
    """
    Convert an integer represented as a base 128 string into an C{int} or
    C{long}.

    @param st: The integer encoded in a string.
    @type st: C{str}

    @return: The integer value extracted from the string.
    @rtype: C{int} or C{long}
    """
    cdef unsigned char* st = <unsigned char*><char*>buf
    return _c_b1282int(st, 0, len(buf))

# delimiter characters.
cdef unsigned char LIST     = 0x80
cdef unsigned char INT      = 0x81
cdef unsigned char STRING   = 0x82
cdef unsigned char NEG      = 0x83
cdef unsigned char FLOAT    = 0x84
# "optional" -- these might be refused by a low-level implementation.
cdef unsigned char LONGINT  = 0x85
cdef unsigned char LONGNEG  = 0x86
# really optional; this is is part of the 'pb' vocabulary
cdef unsigned char VOCAB    = 0x87

cdef unsigned char HIGH_BIT_SET = 0x80

def setPrefixLimit(limit):
    """
    Set the limit on the prefix length for all Banana connections
    established after this call.

    The prefix length limit determines how many bytes of prefix a banana
    decoder will allow before rejecting a potential object as too large.

    @type limit: C{int}
    @param limit: The number of bytes of prefix for banana to allow when
    decoding.
    """
    global _PREFIX_LIMIT
    _PREFIX_LIMIT = limit
setPrefixLimit(64)

cdef int SIZE_LIMIT = 640 * 1024   # 640k is all you'll ever need :-)

class Banana(protocol.Protocol, styles.Ephemeral, object):
    knownDialects = ["pb", "none"]

    prefixLimit = None

    def __init__(self, isClient=1):
        self.listStack = []
        self.outgoingSymbols = copy.copy(self.outgoingVocabulary)
        self.outgoingSymbolCount = 0
        self.isClient = isClient
        self.buf = ''

    def setPrefixLimit(self, limit):
        """
        Set the prefix limit for decoding done by this protocol instance.

        @see: L{setPrefixLimit}
        """
        self.prefixLimit = limit
        self._smallestLongInt = -2 ** (limit * 7) + 1
        self._smallestInt = -2 ** 31
        self._largestInt = 2 ** 31 - 1
        self._largestLongInt = 2 ** (limit * 7) - 1


    def connectionReady(self):
        """Surrogate for connectionMade
        Called after protocol negotiation.
        """

    def _selectDialect(self, dialect):
        self.currentDialect = dialect
        self.connectionReady()

    def callExpressionReceived(self, obj):
        if self.currentDialect:
            self.expressionReceived(obj)
        else:
            # this is the first message we've received
            if self.isClient:
                # if I'm a client I have to respond
                for serverVer in obj:
                    if serverVer in self.knownDialects:
                        self.sendEncoded(serverVer)
                        self._selectDialect(serverVer)
                        break
                else:
                    # I can't speak any of those dialects.
                    log.msg("The client doesn't speak any of the protocols "
                            "offered by the server: disconnecting.")
                    self.transport.loseConnection()
            else:
                if obj in self.knownDialects:
                    self._selectDialect(obj)
                else:
                    # the client just selected a protocol that I did not suggest.
                    log.msg("The client selected a protocol the server didn't "
                            "suggest and doesn't know: disconnecting.")
                    self.transport.loseConnection()


    def connectionMade(self):
        self.setPrefixLimit(_PREFIX_LIMIT)
        self.currentDialect = None
        if not self.isClient:
            self.sendEncoded(self.knownDialects)


    def gotItem(self, item):
        l = self.listStack
        if l:
            l[-1][1].append(item)
        else:
            self.callExpressionReceived(item)

    def dataReceived(self, chunk):
        self.buf += chunk
        cdef unsigned char* buf = <unsigned char*><char*>self.buf
        listStack = self.listStack
        gotItem = self.gotItem
        cdef int n = len(self.buf)
        cdef int i = 0
        cdef int typebyte
        cdef int pos
        cdef int size_limit = SIZE_LIMIT
        while i < n:
            orig_i = i
            pos = i
            while pos < n:
                if buf[pos] & HIGH_BIT_SET:
                    break
                pos += 1
            else:
                if pos > self.prefixLimit:
                    raise BananaError("Security precaution: more than %d bytes of prefix" % (self.prefixLimit,))
                self.buf = self.buf[orig_i:]
                return
            typebyte = buf[pos]
            if pos-i > self.prefixLimit:
                raise BananaError("Security precaution: longer than %d bytes worth of prefix" % (self.prefixLimit,))
            num = _c_b1282int(buf, i, pos-i)
            i = pos+1
            if typebyte == LIST:
                if num > SIZE_LIMIT:
                    raise BananaError("Security precaution: List too long.")
                listStack.append((num, []))
            elif typebyte == STRING:
                if num > SIZE_LIMIT:
                    raise BananaError("Security precaution: String too long.")
                if n-i >= num:
                    gotItem(self.buf[i:i+num])
                    i += num
                else:
                    self.buf = self.buf[orig_i:]
                    return
            elif typebyte == INT:
                gotItem(num)
            elif typebyte == LONGINT:
                gotItem(num)
            elif typebyte == LONGNEG:
                gotItem(-num)
            elif typebyte == NEG:
                gotItem(-num)
            elif typebyte == VOCAB:
                gotItem(self.incomingVocabulary[num])
            elif typebyte == FLOAT:
                if n-i >= 8:
                    gotItem(struct.unpack("!d", self.buf[i:i+8])[0])
                    i += 8
                else:
                    self.buf = self.buf[orig_i:]
                    return
            else:
                raise NotImplementedError(("Invalid Type Byte %r" % (typebyte,)))
            while listStack and (len(listStack[-1][1]) == listStack[-1][0]):
                item = listStack.pop()[1]
                gotItem(item)
        self.buf = ''


    def expressionReceived(self, lst):
        """Called when an expression (list, string, or int) is received.
        """
        raise NotImplementedError()


    outgoingVocabulary = {
        # Jelly Data Types
        'None'           :  1,
        'class'          :  2,
        'dereference'    :  3,
        'reference'      :  4,
        'dictionary'     :  5,
        'function'       :  6,
        'instance'       :  7,
        'list'           :  8,
        'module'         :  9,
        'persistent'     : 10,
        'tuple'          : 11,
        'unpersistable'  : 12,

        # PB Data Types
        'copy'           : 13,
        'cache'          : 14,
        'cached'         : 15,
        'remote'         : 16,
        'local'          : 17,
        'lcache'         : 18,

        # PB Protocol Messages
        'version'        : 19,
        'login'          : 20,
        'password'       : 21,
        'challenge'      : 22,
        'logged_in'      : 23,
        'not_logged_in'  : 24,
        'cachemessage'   : 25,
        'message'        : 26,
        'answer'         : 27,
        'error'          : 28,
        'decref'         : 29,
        'decache'        : 30,
        'uncache'        : 31,
        }

    incomingVocabulary = {}
    for k, v in outgoingVocabulary.items():
        incomingVocabulary[v] = k

    def sendEncoded(self, obj):
        io = cStringIO.StringIO()
        self._encode(obj, io.write)
        value = io.getvalue()
        self.transport.write(value)

    def _encode(self, obj, write):
        if isinstance(obj, (list, tuple)):
            if len(obj) > SIZE_LIMIT:
                raise BananaError(
                    "list/tuple is too long to send (%d)" % (len(obj),))
            int2b128(len(obj), write)
            write(chr(LIST))
            for elem in obj:
                self._encode(elem, write)
        elif isinstance(obj, (int, long)):
            if obj < self._smallestLongInt or obj > self._largestLongInt:
                raise BananaError(
                    "int/long is too large to send (%d)" % (obj,))
            if obj < self._smallestInt:
                int2b128(-obj, write)
                write(chr(LONGNEG))
            elif obj < 0:
                int2b128(-obj, write)
                write(chr(NEG))
            elif obj <= self._largestInt:
                int2b128(obj, write)
                write(chr(INT))
            else:
                int2b128(obj, write)
                write(chr(LONGINT))
        elif isinstance(obj, float):
            write(chr(FLOAT))
            write(struct.pack("!d", obj))
        elif isinstance(obj, str):
            # TODO: an API for extending banana...
            if self.currentDialect == "pb" and obj in self.outgoingSymbols:
                symbolID = self.outgoingSymbols[obj]
                int2b128(symbolID, write)
                write(chr(VOCAB))
            else:
                if len(obj) > SIZE_LIMIT:
                    raise BananaError(
                        "string is too long to send (%d)" % (len(obj),))
                int2b128(len(obj), write)
                write(chr(STRING))
                write(obj)
        else:
            raise BananaError("could not send object: %r" % (obj,))


# For use from the interactive interpreter
_i = Banana()
_i.connectionMade()
_i._selectDialect("none")


def encode(lst):
    """Encode a list s-expression."""
    io = cStringIO.StringIO()
    _i.transport = io
    _i.sendEncoded(lst)
    return io.getvalue()


def decode(st):
    """
    Decode a banana-encoded string.
    """
    l = []
    _i.expressionReceived = l.append
    try:
        _i.dataReceived(st)
    finally:
        _i.buf = ''
        del _i.expressionReceived
    return l[0]
