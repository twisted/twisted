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
ATOM = re.compile(r'[^ \n\r\t0-9"\\()]([^ \n\r\t"\[\]()\\]|\\.)*')
STRING = re.compile(r'"([^\\"]|\\.)*"')
NUMBER = re.compile(r'-?[0-9]+(\.[0-9]*)?')
WHITESPACE = re.compile('[ \n\r\t]+')


class SymbolicExpressionReceiver(protocol.Protocol):
    buffer = ''

    def __init__(self):
        self.expq = []
        self.quoteLevel = 0
        self.quotes = []
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

    def openQuote(self, name):
        newCurrentSexp = [Atom(name)]
        self.quotes.append(newCurrentSexp)
        if self.listStack:
            self.listStack[-1].append(newCurrentSexp)
        self.listStack.append(newCurrentSexp)



    def closeParen(self):
        aList = self.listStack.pop()
        for i in range(len(self.quotes)):
            if aList is self.quotes[i][1]:                
                del self.quotes[i]
                i = self.listStack.pop()
                if not self.listStack:
                    self._sexpRecv(i)
                break
        if not self.listStack:                
            self._sexpRecv(aList)

    def _tokenReceived(self, tok):
                
        if self.listStack:
            self.listStack[-1].append(tok)
            if self.quotes and self.listStack[-1] is self.quotes[-1]:
                del self.quotes[-1]
                i = self.listStack.pop()
                if not self.listStack:
                    self._sexpRecv(i)
        else:
                self._sexpRecv(tok)


    def _sexpRecv(self, xp):
        self.symbolicExpressionReceived(xp)

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
            if buffer[0] == '(':
                self.quoteLevel = self.quoteLevel + 1
                self.openParen()
                self.listStack[-1].append(Atom("backquote"))
                self.openParen()
                buffer = buffer[1:]
                continue
            if buffer[0] == ')':
                self.quoteLevel = self.quoteLevel - 1
                if self.quoteLevel < 0:
                    raise Error("Too many )s")
                self.closeParen()
                self.closeParen()
                buffer = buffer[1:]
                continue
            if buffer[0] == ",":
                if buffer[1] == "@":
                    self.openQuote("unquote-splice")
                    buffer = buffer[2:]
                else:
                    self.openQuote("unquote")
                    buffer = buffer[1:]
                continue
            if buffer[0] == "'":
                self.openQuote("quote")
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

    def connectionLost(self):
        if self.listStack:
            self.symbolicExpressionReceived(self.listStack[-1])
                                                       
class _fromString(SymbolicExpressionReceiver):

    def __init__(self, st):
        self.exps = []
        SymbolicExpressionReceiver.__init__(self)
        self.connectionMade()
        self.dataReceived(st)
        self.connectionLost()

    def symbolicExpressionReceived(self, expr):
        self.exps.append(expr)
    

def fromString(st):    
    f = _fromString(st)
    return f.exps


