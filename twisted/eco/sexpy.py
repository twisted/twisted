#!/usr/bin/env python

"""S-expressions for python.

This provides a wire-protocol reader and object representation for
s-expressions.
"""

import types
import string
import re
import copy
import cStringIO

from twisted.protocols import protocol

def lispString(st):
    return '"'+string.replace(string.replace(st, '\\', '\\\\'),'"','\\"')+'"'

def pythonString(st):
    assert st[0] == '"' and st[-1] == '"'
    # strip off the quotes
    st = st[1:-1]
    # unescape backslashes
    st = string.replace(st, '\\\\', '\\')
    # unescape quotes
    st = string.replace(st, '\\"', '"')
    return st
    
class Atom:
    """
    class to represent atoms, to distinguish them from strings.
    """
    def __init__(self, st):
        self.string = st
    def __cmp__(self, other):
        if isinstance(other, Atom):
            return cmp(self.string, other.string)
        else:
            return cmp(self.string, other)

    def __hash__(self):
        return hash(self.string)
    
    def __repr__(self):
        return "atom(%s)" % repr(self.string)
    
    def __str__(self):
        return self.string
    


def atom(st):
    """
    return an atom, first checking to see if it's valid
    """
    assert ATOM.match(st), "invalid atom"
    return Atom(st)

# SYMBOL = re.compile(r'[a-zA-Z]([a-zA-Z0-9]|\\.)*')
ATOM = re.compile(r'[^ \-\n\r\t0-9"\\()]([^ \n\r\t"\[\]\\]|\\.)*')
STRING = re.compile(r'"([^\\"]|\\.)*"')
NUMBER = re.compile(r'-?[0-9]+(\.[0-9]*)?')
WHITESPACE = re.compile('[ \n\r\t]+')


class SymbolicExpressionReceiver(protocol.Protocol):
    """
    A reader for lisp-style S-expressions.

    Missing features:
     * the octothorpe supposedly does something special...?
     * symbols and strings are the same in python
     * this doesn't actually run lisp code
    """
    buffer = ''

    def __init__(self):
        self.expq = []

    # I don't ever want to buffer more than 64k of data before bailing.
    maxUnparsedBufferSize = 32 * 1024 
    
    def symbolicExpressionReceived(self, expr):
        """
        This class's raison d'etre, this callback is made when a full
        S-expression is received.  (Note that a full expression may be a single
        token)
        """
        print "unimplemented symbolicExpressionReceived(%s)" % repr(expr)


    def sendSymbolicExpression(self, expr):
        """
        Sends a symbolic expression to the other end.
        """
        assert isinstance(expr, SymbolicExpression)
        if self.connected:
            self.transport.write(str(expr))
        else:
            self.expq.append(expr)

    def connectionMade(self):
        self.listStack = []
        xpq = self.expq
        del self.expq
        for xp in xpq:
            self.sendSymbolicExpression(xp)

    def openParen(self):
        newCurrentSexp = []
        if self.listStack:
            self.listStack[-1].append(newCurrentSexp)
        self.listStack.append(newCurrentSexp)

    def closeParen(self):
        aList = self.listStack.pop()
        if not self.listStack:
            self.symbolicExpressionReceived(aList)

    def _tokenReceived(self, tok):
        if self.listStack:
            self.listStack[-1].append(tok)
        else:
            self.symbolicExpressionReceived(tok)


    def dataReceived(self, data):
        buffer = self.buffer + data
        while buffer:
            # eat any whitespace at the beginning of the string.
            m = WHITESPACE.match(buffer)
            if m:
                buffer = buffer[m.end():]
                continue
            if buffer[0] == '[':
                self.openParen()
                buffer = buffer[1:]
                continue
            if buffer[0] == ']':
                self.closeParen()
                buffer = buffer[1:]
                continue
            m = STRING.match(buffer)
            if m:
                end = m.end()
                st, buffer = buffer[:end], buffer[end:]
                self._tokenReceived(pythonString(st))
                continue
            m = NUMBER.match(buffer)
            if m:
                end = m.end()
                if end != len(buffer):
                    number, buffer = buffer[:end], buffer[end:]
                    # If this fails, the RE is buggy.
                    if '.' in number:
                        number = float(number)
                    else:
                        number = int(number)
                    self._tokenReceived(number)
                    continue
            m = ATOM.match(buffer)
            if m:
                end = m.end()
                if end != len(buffer):
                    symbol, buffer = buffer[:end], buffer[end:]
                    self._tokenReceived(Atom(symbol))
                    continue
            break
        if len(buffer) > self.maxUnparsedBufferSize:
            raise SymbolicExpressionParseError("Too much unparsed data.")
        self.buffer = buffer

class _fromString(SymbolicExpressionReceiver):

    def symbolicExpressionReceived(self, expr):
        self.exp = expr
    
    def __init__(self, st):
        SymbolicExpressionReceiver.__init__(self)
        self.connectionMade()
        self.dataReceived(st)

def fromString(st):
    
    f = _fromString(st)
    return f.exp


