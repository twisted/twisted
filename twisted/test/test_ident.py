
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
Test cases for twisted.protocols.ident module.
"""

from twisted.protocols import ident
from twisted.python import failure
from twisted.internet import error
from twisted.internet import defer
from twisted.python import log

from twisted.trial import unittest
from twisted.test.proto_helpers import StringTransport

class ClassParserTestCase(unittest.TestCase):
    def testErrors(self):
        p = ident.IdentClient()
        
        L = []
        d = defer.Deferred()
        d.addErrback(L.append)
        p.queries.append((d, 123, 456))
        p.lineReceived('123, 456 : ERROR : UNKNOWN-ERROR')
        self.failUnless(L[0].value.__class__ is ident.IdentError, "%s is the wrong exception" % (L[0],))
        
        L = []
        d = defer.Deferred()
        d.addErrback(L.append)
        p.queries.append((d, 234, 456))
        p.lineReceived('234, 456 : ERROR : NO-USER')
        self.failUnless(L[0].value.__class__ is ident.NoUser, "%s is the wrong exception" % (L[0],))
        
        L = []
        d = defer.Deferred()
        d.addErrback(L.append)
        p.queries.append((d, 345, 567))
        p.lineReceived('345, 567 :  ERROR : INVALID-PORT')
        self.failUnless(L[0].value.__class__ is ident.InvalidPort, "%s is the wrong exception" % (L[0],))
        
        L = []
        d = defer.Deferred()
        d.addErrback(L.append)
        p.queries.append((d, 567, 789))
        p.lineReceived('567, 789 : ERROR : HIDDEN-USER')
        self.failUnless(L[0].value.__class__ is ident.HiddenUser, "%s is the wrong exception" % (L[0],))
    
    def testLostConnection(self):
        p = ident.IdentClient()
        
        L = []
        d = defer.Deferred()
        d.addErrback(L.append)
        p.queries.append((d, 765, 432))
        p.connectionLost(failure.Failure(error.ConnectionLost()))
        self.failUnless(L[0].value.__class__ is ident.IdentError)


class TestIdentServer(ident.IdentServer):
    def lookup(self, serverAddress, clientAddress):
        return self.resultValue

class TestErrorIdentServer(ident.IdentServer):
    def lookup(self, serverAddress, clientAddress):
        raise self.exceptionType()

class NewException(RuntimeError):
    pass

class ServerParserTestCase(unittest.TestCase):
    def testErrors(self):
        p = TestErrorIdentServer()
        p.makeConnection(StringTransport())
        L = []
        p.sendLine = L.append

        p.exceptionType = ident.IdentError
        p.lineReceived('123, 345')
        self.assertEquals(L[0], '123, 345 : ERROR : UNKNOWN-ERROR')
        
        p.exceptionType = ident.NoUser
        p.lineReceived('432, 210')
        self.assertEquals(L[1], '432, 210 : ERROR : NO-USER')
        
        p.exceptionType = ident.InvalidPort
        p.lineReceived('987, 654')
        self.assertEquals(L[2], '987, 654 : ERROR : INVALID-PORT')
        
        p.exceptionType = ident.HiddenUser
        p.lineReceived('756, 827')
        self.assertEquals(L[3], '756, 827 : ERROR : HIDDEN-USER')
        
        p.exceptionType = NewException
        p.lineReceived('987, 789')
        self.assertEquals(L[4], '987, 789 : ERROR : UNKNOWN-ERROR')
        errs = log.flushErrors(NewException)
        self.assertEquals(len(errs), 1)

    def testSuccess(self):
        p = TestIdentServer()
        p.makeConnection(StringTransport())
        L = []
        p.sendLine = L.append
        
        p.resultValue = ('SYS', 'USER')
        p.lineReceived('123, 456')
        self.assertEquals(L[0], '123, 456 : USERID : SYS : USER')
