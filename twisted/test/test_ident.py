
# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.


"""
Test cases for twisted.protocols.ident module.
"""

import struct

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

if struct.pack('=L', 1)[0] == '\x01':
    _addr1 = '0100007F'
    _addr2 = '04030201'
else:
    _addr1 = '7F000001'
    _addr2 = '01020304'

class ProcMixinTestCase(unittest.TestCase):
    line = ('4: %s:0019 %s:02FA 0A 00000000:00000000 '
            '00:00000000 00000000     0        0 10927 1 f72a5b80 '
            '3000 0 0 2 -1') % (_addr1, _addr2)

    def testDottedQuadFromHexString(self):
        p = ident.ProcServerMixin()
        self.assertEquals(p.dottedQuadFromHexString(_addr1), '127.0.0.1')

    def testUnpackAddress(self):
        p = ident.ProcServerMixin()
        self.assertEquals(p.unpackAddress(_addr1 + ':0277'), ('127.0.0.1', 631))

    def testLineParser(self):
        p = ident.ProcServerMixin()
        self.assertEquals(
            p.parseLine(self.line),
            (('127.0.0.1', 25), ('1.2.3.4', 762), 0))

    def testExistingAddress(self):
        username = []
        p = ident.ProcServerMixin()
        p.entries = lambda: iter([self.line])
        p.getUsername = lambda uid: (username.append(uid), 'root')[1]
        self.assertEquals(
            p.lookup(('127.0.0.1', 25), ('1.2.3.4', 762)),
            (p.SYSTEM_NAME, 'root'))
        self.assertEquals(username, [0])

    def testNonExistingAddress(self):
        p = ident.ProcServerMixin()
        p.entries = lambda: iter([self.line])
        self.assertRaises(ident.NoUser, p.lookup, ('127.0.0.1', 26), ('1.2.3.4', 762))
        self.assertRaises(ident.NoUser, p.lookup, ('127.0.0.1', 25), ('1.2.3.5', 762))
        self.assertRaises(ident.NoUser, p.lookup, ('127.0.0.1', 25), ('1.2.3.4', 763))
