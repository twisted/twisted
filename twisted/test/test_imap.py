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
Test case for twisted.protocols.imap4
"""

from __future__ import nested_scopes

try:
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO

import os
import sys
import types

from twisted.protocols.imap4 import MessageSet
from twisted.protocols import imap4
from twisted.protocols import smtp
from twisted.protocols import loopback
from twisted.internet import defer
from twisted.trial import unittest
from twisted.python import util
from twisted.python import components
from twisted.python.util import sibpath

from twisted import cred
import twisted.cred.error
import twisted.cred.checkers
import twisted.cred.credentials
import twisted.cred.portal

try:
    from ssl_helpers import ClientTLSContext, ServerTLSContext
except ImportError:
    ClientTLSContext = ServerTLSContext = None

def strip(f):
    return lambda result, f=f: f()

def sortNest(l):
    l = l[:]
    l.sort()
    for i in range(len(l)):
        if isinstance(l[i], types.ListType):
            l[i] = sortNest(l[i])
        elif isinstance(l[i], types.TupleType):
            l[i] = tuple(sortNest(list(l[i])))
    return l

class IMAP4UTF7TestCase(unittest.TestCase):
    tests = [
        ['Hello world', 'Hello world'],
        ['Hello & world', 'Hello &- world'],
        ['Hello\xffworld', 'Hello&,w-world'],
        ['\xff\xfe\xfd\xfc', '&,,79,A-'],
    ]

    def testEncode(self):
        for (input, output) in self.tests:
            self.assertEquals(input.encode('imap4-utf-7'), output)

    def testDecode(self):
        for (input, output) in self.tests:
            # XXX - Piece of *crap* 2.1
            self.assertEquals(input, imap4.decoder(output)[0])

class IMAP4HelperTestCase(unittest.TestCase):
    def testMessageSet(self):
        m1 = MessageSet()
        m2 = MessageSet()

        self.assertEquals(m1, m2)
        
        m1 = m1 + (1, 3)
        self.assertEquals(len(m1), 3)
        self.assertEquals(list(m1), [1, 2, 3])
        
        m2 = m2 + (1, 3)
        self.assertEquals(m1, m2)
        self.assertEquals(list(m1 + m2), [1, 2, 3])

    def testQuotedSplitter(self):
        cases = [
            '''Hello World''',
            '''Hello "World!"''',
            '''World "Hello" "How are you?"''',
            '''"Hello world" How "are you?"''',
            '''foo bar "baz buz" NIL''',
            '''foo bar "baz buz" "NIL"''',
            '''foo NIL "baz buz" bar''',
            '''foo "NIL" "baz buz" bar''',
            '''"NIL" bar "baz buz" foo''',
        ]
        
        answers = [
            ['Hello', 'World'],
            ['Hello', 'World!'],
            ['World', 'Hello', 'How are you?'],
            ['Hello world', 'How', 'are you?'],
            ['foo', 'bar', 'baz buz', None],
            ['foo', 'bar', 'baz buz', 'NIL'],
            ['foo', None, 'baz buz', 'bar'],
            ['foo', 'NIL', 'baz buz', 'bar'],
            ['NIL', 'bar', 'baz buz', 'foo'],
        ]
        
        errors = [
            '"mismatched quote',
            'mismatched quote"',
            'mismatched"quote',
            '"oops here is" another"',
        ]
        
        for s in errors:
            self.assertRaises(imap4.MismatchedQuoting, imap4.splitQuoted, s)
        
        for (case, expected) in zip(cases, answers):
            self.assertEquals(imap4.splitQuoted(case), expected)


    def testStringCollapser(self):
        cases = [
            ['a', 'b', 'c', 'd', 'e'],
            ['a', ' ', '"', 'b', 'c', ' ', '"', ' ', 'd', 'e'],
            [['a', 'b', 'c'], 'd', 'e'],
            ['a', ['b', 'c', 'd'], 'e'],
            ['a', 'b', ['c', 'd', 'e']],
            ['"', 'a', ' ', '"', ['b', 'c', 'd'], '"', ' ', 'e', '"'],
            ['a', ['"', ' ', 'b', 'c', ' ', ' ', '"'], 'd', 'e'],
        ]
        
        answers = [
            ['abcde'],
            ['a', 'bc ', 'de'],
            [['abc'], 'de'],
            ['a', ['bcd'], 'e'],
            ['ab', ['cde']],
            ['a ', ['bcd'], ' e'],
            ['a', [' bc  '], 'de'],
        ]
        
        for (case, expected) in zip(cases, answers):
            self.assertEquals(imap4.collapseStrings(case), expected)

    def testParenParser(self):
        s = '\r\n'.join(['xx'] * 4)    
        cases = [
            '(BODY.PEEK[HEADER.FIELDS.NOT (subject bcc cc)] {%d}\r\n%s)' % (len(s), s,),

#            '(FLAGS (\Seen) INTERNALDATE "17-Jul-1996 02:44:25 -0700" '
#            'RFC822.SIZE 4286 ENVELOPE ("Wed, 17 Jul 1996 02:23:25 -0700 (PDT)" '
#            '"IMAP4rev1 WG mtg summary and minutes" '
#            '(("Terry Gray" NIL "gray" "cac.washington.edu")) '
#            '(("Terry Gray" NIL "gray" "cac.washington.edu")) '
#            '(("Terry Gray" NIL "gray" "cac.washington.edu")) '
#            '((NIL NIL "imap" "cac.washington.edu")) '
#            '((NIL NIL "minutes" "CNRI.Reston.VA.US") '
#            '("John Klensin" NIL "KLENSIN" "INFOODS.MIT.EDU")) NIL NIL '
#            '"<B27397-0100000@cac.washington.edu>") '
#            'BODY ("TEXT" "PLAIN" ("CHARSET" "US-ASCII") NIL NIL "7BIT" 3028 92))',

            '(FLAGS (\Seen) INTERNALDATE "17-Jul-1996 02:44:25 -0700" '
            'RFC822.SIZE 4286 ENVELOPE ("Wed, 17 Jul 1996 02:23:25 -0700 (PDT)" '
            '"IMAP4rev1 WG mtg summary and minutes" '
            '(("Terry Gray" NIL gray cac.washington.edu)) '
            '(("Terry Gray" NIL gray cac.washington.edu)) '
            '(("Terry Gray" NIL gray cac.washington.edu)) '
            '((NIL NIL imap cac.washington.edu)) '
            '((NIL NIL minutes CNRI.Reston.VA.US) '
            '("John Klensin" NIL KLENSIN INFOODS.MIT.EDU)) NIL NIL '
            '<B27397-0100000@cac.washington.edu>) '
            'BODY (TEXT PLAIN (CHARSET US-ASCII) NIL NIL 7BIT 3028 92))',
        ]
        
        answers = [
            ['BODY.PEEK', ['HEADER.FIELDS.NOT', ['subject', 'bcc', 'cc']], s],

            ['FLAGS', [r'\Seen'], 'INTERNALDATE',
            '17-Jul-1996 02:44:25 -0700', 'RFC822.SIZE', '4286', 'ENVELOPE',
            ['Wed, 17 Jul 1996 02:23:25 -0700 (PDT)', 
            'IMAP4rev1 WG mtg summary and minutes', [["Terry Gray", None,
            "gray", "cac.washington.edu"]], [["Terry Gray", None,
            "gray", "cac.washington.edu"]], [["Terry Gray", None,
            "gray", "cac.washington.edu"]], [[None, None, "imap",
            "cac.washington.edu"]], [[None, None, "minutes",
            "CNRI.Reston.VA.US"], ["John Klensin", None, "KLENSIN",
            "INFOODS.MIT.EDU"]], None, None,
            "<B27397-0100000@cac.washington.edu>"], "BODY", ["TEXT", "PLAIN",
            ["CHARSET", "US-ASCII"], None, None, "7BIT", "3028", "92"]],
        ]

        for (case, expected) in zip(cases, answers):
            self.assertEquals(imap4.parseNestedParens(case), [expected])
        
        for (case, expected) in zip(answers, cases):
            self.assertEquals('(' + imap4.collapseNestedLists(case) + ')', expected)

    def testFetchParserSimple(self):
        cases = [
            ['ENVELOPE', 'Envelope'],
            ['FLAGS', 'Flags'],
            ['INTERNALDATE', 'InternalDate'],
            ['RFC822.HEADER', 'RFC822Header'],
            ['RFC822.SIZE', 'RFC822Size'],
            ['RFC822.TEXT', 'RFC822Text'],
            ['RFC822', 'RFC822'],
            ['UID', 'UID'],
            ['BODYSTRUCTURE', 'BodyStructure'],
        ]
        
        for (inp, outp) in cases:
            p = imap4._FetchParser()
            p.parseString(inp)
            self.assertEquals(len(p.result), 1)
            self.failUnless(isinstance(p.result[0], getattr(p, outp)))

    def testFetchParserMacros(self):
        cases = [
            ['ALL', (4, ['flags', 'internaldate', 'rfc822.size', 'envelope'])],
            ['FULL', (5, ['flags', 'internaldate', 'rfc822.size', 'envelope', 'body'])], 
            ['FAST', (3, ['flags', 'internaldate', 'rfc822.size'])],
        ]

        for (inp, outp) in cases:
            p = imap4._FetchParser()
            p.parseString(inp)
            self.assertEquals(len(p.result), outp[0])
            p = [str(p).lower() for p in p.result]
            p.sort()
            outp[1].sort()
            self.assertEquals(p, outp[1])

    def testFetchParserBody(self):
        P = imap4._FetchParser
        
        p = P()
        p.parseString('BODY')
        self.assertEquals(len(p.result), 1)
        self.failUnless(isinstance(p.result[0], p.Body))
        self.assertEquals(p.result[0].peek, False)
        self.assertEquals(p.result[0].header, None)
        
        p = P()
        p.parseString('BODY.PEEK')
        self.assertEquals(len(p.result), 1)
        self.failUnless(isinstance(p.result[0], p.Body))
        self.assertEquals(p.result[0].peek, True)

        p = P()
        p.parseString('BODY[HEADER]')
        self.assertEquals(len(p.result), 1)
        self.failUnless(isinstance(p.result[0], p.Body))
        self.assertEquals(p.result[0].peek, False)
        self.failUnless(isinstance(p.result[0].header, p.Header))
        self.assertEquals(p.result[0].header.negate, False)
        self.assertEquals(p.result[0].header.fields, None)

        p = P()
        p.parseString('BODY.PEEK[HEADER]')
        self.assertEquals(len(p.result), 1)
        self.failUnless(isinstance(p.result[0], p.Body))
        self.assertEquals(p.result[0].peek, True)
        self.failUnless(isinstance(p.result[0].header, p.Header))
        self.assertEquals(p.result[0].header.negate, False)
        self.assertEquals(p.result[0].header.fields, None)

        p = P()
        p.parseString('BODY[HEADER.FIELDS (Subject Cc Message-Id)]')
        self.assertEquals(len(p.result), 1)
        self.failUnless(isinstance(p.result[0], p.Body))
        self.assertEquals(p.result[0].peek, False)
        self.failUnless(isinstance(p.result[0].header, p.Header))
        self.assertEquals(p.result[0].header.negate, False)
        self.assertEquals(p.result[0].header.fields, ['SUBJECT', 'CC', 'MESSAGE-ID'])

        p = P()
        p.parseString('BODY.PEEK[HEADER.FIELDS (Subject Cc Message-Id)]')
        self.assertEquals(len(p.result), 1)
        self.failUnless(isinstance(p.result[0], p.Body))
        self.assertEquals(p.result[0].peek, True)
        self.failUnless(isinstance(p.result[0].header, p.Header))
        self.assertEquals(p.result[0].header.negate, False)
        self.assertEquals(p.result[0].header.fields, ['SUBJECT', 'CC', 'MESSAGE-ID'])

        p = P()
        p.parseString('BODY.PEEK[HEADER.FIELDS.NOT (Subject Cc Message-Id)]')
        self.assertEquals(len(p.result), 1)
        self.failUnless(isinstance(p.result[0], p.Body))
        self.assertEquals(p.result[0].peek, True)
        self.failUnless(isinstance(p.result[0].header, p.Header))
        self.assertEquals(p.result[0].header.negate, True)
        self.assertEquals(p.result[0].header.fields, ['SUBJECT', 'CC', 'MESSAGE-ID'])
        
        p = P()
        p.parseString('BODY[1.MIME]<10.50>')
        self.assertEquals(len(p.result), 1)
        self.failUnless(isinstance(p.result[0], p.Body))
        self.assertEquals(p.result[0].peek, False)
        self.failUnless(isinstance(p.result[0].mime, p.MIME))
        self.assertEquals(p.result[0].mime.part, (0,))
        self.assertEquals(p.result[0].partialBegin, 10)
        self.assertEquals(p.result[0].partialLength, 50)

        p = P()
        p.parseString('BODY.PEEK[1.3.9.11.HEADER.FIELDS.NOT (Message-Id Date)]<103.69>')
        self.assertEquals(len(p.result), 1)
        self.failUnless(isinstance(p.result[0], p.Body))
        self.assertEquals(p.result[0].peek, True)
        self.failUnless(isinstance(p.result[0].header, p.Header))
        self.assertEquals(p.result[0].header.part, (0, 2, 8, 10))
        self.assertEquals(p.result[0].header.fields, ['MESSAGE-ID', 'DATE'])
        self.assertEquals(p.result[0].partialBegin, 103)
        self.assertEquals(p.result[0].partialLength, 69)


    def testFiles(self):
        inputStructure = [
            'foo', 'bar', 'baz', StringIO('this is a file\r\n'), 'buz'
        ]
        
        output = 'foo bar baz {16}\r\nthis is a file\r\n buz'
        
        self.assertEquals(imap4.collapseNestedLists(inputStructure), output)
    
    def testLiterals(self):
        cases = [
            ('({10}\r\n0123456789)', [['0123456789']]),
        ]
        
        for (case, expected) in cases:
            self.assertEquals(imap4.parseNestedParens(case), expected)

    def testQueryBuilder(self):
        inputs = [
            imap4.Query(flagged=1),
            imap4.Query(sorted=1, unflagged=1, deleted=1),
            imap4.Or(imap4.Query(flagged=1), imap4.Query(deleted=1)),
            imap4.Query(before='today'),
            imap4.Or(
                imap4.Query(deleted=1),
                imap4.Query(unseen=1),
                imap4.Query(new=1)
            ),
            imap4.Or(
                imap4.Not(
                    imap4.Or(
                        imap4.Query(sorted=1, since='yesterday', smaller=1000),
                        imap4.Query(sorted=1, before='tuesday', larger=10000),
                        imap4.Query(sorted=1, unseen=1, deleted=1, before='today'),
                        imap4.Not(
                            imap4.Query(subject='spam')
                        ),
                    ),
                ),
                imap4.Not(
                    imap4.Query(uid='1:5')
                ),
            )
        ]
        
        outputs = [
            'FLAGGED',
            '(DELETED UNFLAGGED)',
            '(OR FLAGGED DELETED)',
            '(BEFORE "today")',
            '(OR DELETED (OR UNSEEN NEW))',
            '(OR (NOT (OR (SINCE "yesterday" SMALLER 1000) ' # Continuing
            '(OR (BEFORE "tuesday" LARGER 10000) (OR (BEFORE ' # Some more
            '"today" DELETED UNSEEN) (NOT (SUBJECT "spam")))))) ' # And more
            '(NOT (UID 1:5)))',
        ]
        
        for (query, expected) in zip(inputs, outputs):
            self.assertEquals(query, expected)
    
    def testIdListParser(self):
        inputs = [
            '1:*',
            '5:*',
            '1:2,5:*',
            '1',
            '1,2',
            '1,3,5',
            '1:10',
            '1:10,11',
            '1:5,10:20',
            '1,5:10',
            '1,5:10,15:20',
            '1:10,15,20:25',
        ]
        
        outputs = [
            MessageSet(1, None),
            MessageSet(5, None),
            MessageSet(5, None) + MessageSet(1, 2),
            MessageSet(1),
            MessageSet(1, 2),
            MessageSet(1) + MessageSet(3) + MessageSet(5),
            MessageSet(1, 10),
            MessageSet(1, 11),
            MessageSet(1, 5) + MessageSet(10, 20),
            MessageSet(1) + MessageSet(5, 10),
            MessageSet(1) + MessageSet(5, 10) + MessageSet(15, 20),
            MessageSet(1, 10) + MessageSet(15) + MessageSet(20, 25),
        ]
        
        lengths = [
            None, None, None,
            1, 2, 3, 10, 11, 16, 7, 13, 17,
        ]
        
        for (input, expected) in zip(inputs, outputs):
            self.assertEquals(imap4.parseIdList(input), expected)

        for (input, expected) in zip(inputs, lengths):
            try:
                L = len(imap4.parseIdList(input))
            except TypeError:
                L = None
            self.assertEquals(L, expected,
                "len(%r) = %r != %r" % (input, L, expected))

class SimpleMailbox:
    flags = ('\\Flag1', 'Flag2', '\\AnotherSysFlag', 'LastFlag')
    messages = []
    mUID = 0
    rw = 1

    def __init__(self):
        self.listeners = []
        self.addListener = self.listeners.append
        self.removeListener = self.listeners.remove

    def getFlags(self):
        return self.flags
    
    def getUIDValidity(self):
        return 42
    
    def getUIDNext(self):
        return len(self.messages) + 1
    
    def getMessageCount(self):
        return 9
    
    def getRecentCount(self):
        return 3

    def getUnseenCount(self):
        return 4
    
    def isWriteable(self):
        return self.rw
    
    def destroy(self):
        pass
    
    def getHierarchicalDelimiter(self):
        return '/'
    
    def requestStatus(self, names):
        r = {}
        if 'MESSAGES' in names:
            r['MESSAGES'] = self.getMessageCount()
        if 'RECENT' in names:
            r['RECENT'] = self.getRecentCount()
        if 'UIDNEXT' in names:
            r['UIDNEXT'] = self.getMessageCount() + 1
        if 'UIDVALIDITY' in names:
            r['UIDVALIDITY'] = self.getUID()
        if 'UNSEEN' in names:
            r['UNSEEN'] = self.getUnseenCount()
        return defer.succeed(r)
    
    def addMessage(self, message, flags, date = None):
        self.messages.append((message, flags, date, self.mUID))
        self.mUID += 1
        return defer.succeed(None)
    
    def expunge(self):
        delete = []
        for i in self.messages:
            if '\\Deleted' in i[1]:
                delete.append(i)
        for i in delete:
            self.messages.remove(i)
        return [i[3] for i in delete]
    
class Account(imap4.MemoryAccount):
    def _emptyMailbox(self, name, id):
        return SimpleMailbox()
    
    def select(self, name, rw=1):
        mbox = imap4.MemoryAccount.select(self, name)
        if mbox is not None:
            mbox.rw = rw
        return mbox

class SimpleServer(imap4.IMAP4Server):
    def authenticateLogin(self, username, password):
        if username == 'testuser' and password == 'password-test':
            return imap4.IAccount, self.theAccount, lambda: None
        raise cred.error.UnauthorizedLogin()

class SimpleClient(imap4.IMAP4Client):
    startedTLS = False

    def __init__(self, deferred, contextFactory = None):
        imap4.IMAP4Client.__init__(self, contextFactory)
        self.deferred = deferred
        self.events = []

    def connectionMade(self):
        self.deferred.callback(None)
    
    def modeChanged(self, writeable):
        self.events.append(['modeChanged', writeable])
        self.transport.loseConnection()
    
    def flagsChanged(self, newFlags):
        self.events.append(['flagsChanged', newFlags])
        self.transport.loseConnection()
    
    def newMessages(self, exists, recent):
        self.events.append(['newMessages', exists, recent])
        self.transport.loseConnection()

    # Let us notice when TLS is started
    def _IMAP4Client__cbLoginTLS(self, *args):
        r = imap4.IMAP4Client._IMAP4Client__cbLoginTLS(self, *args)
        self.startedTLS = True
        return r

class IMAP4HelperMixin:
    serverCTX = None
    clientCTX = None

    def setUp(self):
        d = defer.Deferred()
        self.server = SimpleServer(contextFactory=self.serverCTX)
        self.client = SimpleClient(d, contextFactory=self.clientCTX)
        self.connected = d

        SimpleMailbox.messages = []
        theAccount = Account('testuser')
        theAccount.mboxType = SimpleMailbox
        SimpleServer.theAccount = theAccount

    def tearDown(self):
        del self.server
        del self.client
        del self.connected

    def _cbStopClient(self, ignore):
        self.client.transport.loseConnection()

    def _ebGeneral(self, failure):
        self.client.transport.loseConnection()
        self.server.transport.loseConnection()
        failure.printTraceback(open('failure.log', 'w'))
        failure.printTraceback()
        raise failure.value
    
    def loopback(self):
        loopback.loopback(self.server, self.client)

class IMAP4ServerTestCase(IMAP4HelperMixin, unittest.TestCase):
    def testCapability(self):
        caps = {}
        def getCaps():
            def gotCaps(c):
                caps.update(c)
                self.server.transport.loseConnection()
            return self.client.getCapabilities().addCallback(gotCaps)
        self.connected.addCallback(strip(getCaps)).addErrback(self._ebGeneral)
        self.loopback()
        
        self.assertEquals({'IMAP4rev1': None}, caps)
    
    def testCapabilityWithAuth(self):
        caps = {}
        self.server.challengers['CRAM-MD5'] = cred.credentials.CramMD5Credentials
        def getCaps():
            def gotCaps(c):
                caps.update(c)
                self.server.transport.loseConnection()
            return self.client.getCapabilities().addCallback(gotCaps)
        self.connected.addCallback(strip(getCaps)).addErrback(self._ebGeneral)
        self.loopback()
        
        self.assertEquals({'IMAP4rev1': None, 'AUTH': ['CRAM-MD5']}, caps)
    
    def testLogout(self):
        self.loggedOut = 0
        def logout():
            def setLoggedOut():
                self.loggedOut = 1
            self.client.logout().addCallback(strip(setLoggedOut))
        self.connected.addCallback(strip(logout)).addErrback(self._ebGeneral)
        self.loopback()
        
        self.assertEquals(self.loggedOut, 1)

    def testNoop(self):
        self.responses = None
        def noop():
            def setResponses(responses):
                self.responses = responses
                self.server.transport.loseConnection()
            self.client.noop().addCallback(setResponses)
        self.connected.addCallback(strip(noop)).addErrback(self._ebGeneral)
        self.loopback()
        
        self.assertEquals(self.responses, [])

    def testLogin(self):
        def login():
            d = self.client.login('testuser', 'password-test')
            d.addCallback(self._cbStopClient)
        self.connected.addCallback(strip(login)).addErrback(self._ebGeneral)
        self.loopback()
        
        self.assertEquals(self.server.account, SimpleServer.theAccount)
        self.assertEquals(self.server.state, 'auth')

    def testFailedLogin(self):
        def login():
            d = self.client.login('testuser', 'wrong-password')
            d.addBoth(self._cbStopClient)

        self.connected.addCallback(strip(login)).addErrback(self._ebGeneral)
        self.loopback()

        self.assertEquals(self.server.account, None)
        self.assertEquals(self.server.state, 'unauth')

    def testSelect(self):
        SimpleServer.theAccount.addMailbox('test-mailbox')
        self.selectedArgs = None
        def login():
            return self.client.login('testuser', 'password-test')
        def select():
            def selected(args):
                self.selectedArgs = args
                self._cbStopClient(None)
            d = self.client.select('test-mailbox')
            d.addCallback(selected)
            return d

        d = self.connected.addCallback(strip(login))
        d.addCallback(strip(select))
        d.addErrback(self._ebGeneral)
        self.loopback()
        
        mbox = SimpleServer.theAccount.mailboxes['TEST-MAILBOX']
        self.assertEquals(self.server.mbox, mbox)
        self.assertEquals(self.selectedArgs, {
            'EXISTS': 9, 'RECENT': 3, 'UIDVALIDITY': 42,
            'FLAGS': ('\\Flag1', 'Flag2', '\\AnotherSysFlag', 'LastFlag'),
            'READ-WRITE': 1
        })

    def testExamine(self):
        SimpleServer.theAccount.addMailbox('test-mailbox')
        self.examinedArgs = None
        def login():
            return self.client.login('testuser', 'password-test')
        def examine():
            def examined(args):
                self.examinedArgs = args
                self._cbStopClient(None)
            d = self.client.examine('test-mailbox')
            d.addCallback(examined)
            return d

        d = self.connected.addCallback(strip(login))
        d.addCallback(strip(examine))
        d.addErrback(self._ebGeneral)
        self.loopback()
        
        mbox = SimpleServer.theAccount.mailboxes['TEST-MAILBOX']
        self.assertEquals(self.server.mbox, mbox)
        self.assertEquals(self.examinedArgs, {
            'EXISTS': 9, 'RECENT': 3, 'UIDVALIDITY': 42,
            'FLAGS': ('\\Flag1', 'Flag2', '\\AnotherSysFlag', 'LastFlag'),
            'READ-WRITE': 0
        })

    def testCreate(self):
        succeed = ('testbox', 'test/box', 'test/', 'test/box/box', 'INBOX')
        fail = ('testbox', 'test/box')
        
        def cb(): self.result.append(1)
        def eb(failure): self.result.append(0)
        
        def login():
            return self.client.login('testuser', 'password-test')
        def create():
            for name in succeed + fail:
                d = self.client.create(name)
                d.addCallback(strip(cb)).addErrback(eb)
            d.addCallbacks(self._cbStopClient, self._ebGeneral)

        self.result = []
        d = self.connected.addCallback(strip(login)).addCallback(strip(create))
        self.loopback()
        
        self.assertEquals(self.result, [1] * len(succeed) + [0] * len(fail))
        mbox = SimpleServer.theAccount.mailboxes.keys()
        answers = ['inbox', 'testbox', 'test/box', 'test', 'test/box/box']
        mbox.sort()
        answers.sort()
        self.assertEquals(mbox, [a.upper() for a in answers])

    def testDelete(self):
        SimpleServer.theAccount.addMailbox('delete/me')
        
        def login():
            return self.client.login('testuser', 'password-test')
        def delete():
            return self.client.delete('delete/me')
        d = self.connected.addCallbacks(strip(login))
        d.addCallbacks(strip(delete), self._ebGeneral)
        d.addCallbacks(self._cbStopClient, self._ebGeneral)
        self.loopback()
        
        self.assertEquals(SimpleServer.theAccount.mailboxes.keys(), [])

    def testNonExistentDelete(self):
        def login():
            return self.client.login('testuser', 'password-test')
        def delete():
            return self.client.delete('delete/me')
        def deleteFailed(failure):
            self.failure = failure

        self.failure = None
        d = self.connected.addCallback(strip(login))
        d.addCallback(strip(delete)).addErrback(deleteFailed)
        d.addCallbacks(self._cbStopClient, self._ebGeneral)
        self.loopback()
        
        self.assertEquals(str(self.failure.value), 'No such mailbox')

    def testIllegalDelete(self):
        m = SimpleMailbox()
        m.flags = (r'\Noselect',)
        SimpleServer.theAccount.addMailbox('delete', m)
        SimpleServer.theAccount.addMailbox('delete/me')

        def login():
            return self.client.login('testuser', 'password-test')
        def delete():
            return self.client.delete('delete')
        def deleteFailed(failure):
            self.failure = failure

        self.failure = None
        d = self.connected.addCallback(strip(login))
        d.addCallback(strip(delete)).addErrback(deleteFailed)
        d.addCallbacks(self._cbStopClient, self._ebGeneral)
        self.loopback()
        
        self.assertEquals(str(self.failure.value), "Hierarchically inferior mailboxes exist and \\Noselect is set")

    def testRename(self):
        SimpleServer.theAccount.addMailbox('oldmbox')
        def login():
            return self.client.login('testuser', 'password-test')
        def rename():
            return self.client.rename('oldmbox', 'newname')
        
        d = self.connected.addCallback(strip(login))
        d.addCallbacks(strip(rename), self._ebGeneral)
        d.addCallbacks(self._cbStopClient, self._ebGeneral)
        self.loopback()
        
        self.assertEquals(SimpleServer.theAccount.mailboxes.keys(), ['NEWNAME'])
    
    def testHierarchicalRename(self):
        SimpleServer.theAccount.create('oldmbox/m1')
        SimpleServer.theAccount.create('oldmbox/m2')
        def login():
            return self.client.login('testuser', 'password-test')
        def rename():
            return self.client.rename('oldmbox', 'newname')
        
        d = self.connected.addCallback(strip(login))
        d.addCallbacks(strip(rename), self._ebGeneral)
        d.addCallbacks(self._cbStopClient, self._ebGeneral)
        self.loopback()
        
        mboxes = SimpleServer.theAccount.mailboxes.keys()
        expected = ['newname', 'newname/m1', 'newname/m2']
        mboxes.sort()
        self.assertEquals(mboxes, [s.upper() for s in expected])

    def testSubscribe(self):
        def login():
            return self.client.login('testuser', 'password-test')
        def subscribe():
            return self.client.subscribe('this/mbox')
        
        d = self.connected.addCallback(strip(login))
        d.addCallbacks(strip(subscribe), self._ebGeneral)
        d.addCallbacks(self._cbStopClient, self._ebGeneral)
        self.loopback()
        
        self.assertEquals(SimpleServer.theAccount.subscriptions, ['THIS/MBOX'])
    
    def testUnsubscribe(self):
        SimpleServer.theAccount.subscriptions = ['THIS/MBOX', 'THAT/MBOX']
        def login():
            return self.client.login('testuser', 'password-test')
        def unsubscribe():
            return self.client.unsubscribe('this/mbox')
        
        d = self.connected.addCallback(strip(login))
        d.addCallbacks(strip(unsubscribe), self._ebGeneral)
        d.addCallbacks(self._cbStopClient, self._ebGeneral)
        self.loopback()
        
        self.assertEquals(SimpleServer.theAccount.subscriptions, ['THAT/MBOX'])

    def _listSetup(self, f):
        SimpleServer.theAccount.addMailbox('root/subthing')
        SimpleServer.theAccount.addMailbox('root/another-thing')
        SimpleServer.theAccount.addMailbox('non-root/subthing')
        
        def login():
            return self.client.login('testuser', 'password-test')
        def listed(answers):
            self.listed = answers
        
        self.listed = None
        d = self.connected.addCallback(strip(login))
        d.addCallbacks(strip(f), self._ebGeneral)
        d.addCallbacks(listed, self._ebGeneral)
        d.addCallbacks(self._cbStopClient, self._ebGeneral)
        self.loopback()
        
        return self.listed

    def testList(self):
        def list():
            return self.client.list('root', '%')
        listed = self._listSetup(list)
        self.assertEquals(
            sortNest(listed),
            sortNest([
                (SimpleMailbox.flags, "/", "ROOT/SUBTHING"),
                (SimpleMailbox.flags, "/", "ROOT/ANOTHER-THING")
            ])
        )

    def testLSub(self):
        SimpleServer.theAccount.subscribe('ROOT/SUBTHING')
        def lsub():
            return self.client.lsub('root', '%')
        listed = self._listSetup(lsub)
        self.assertEquals(listed, [(SimpleMailbox.flags, "/", "ROOT/SUBTHING")])

    def testStatus(self):
        SimpleServer.theAccount.addMailbox('root/subthing')
        def login():
            return self.client.login('testuser', 'password-test')
        def status():
            return self.client.status('root/subthing', 'MESSAGES', 'UIDNEXT', 'UNSEEN')
        def statused(result):
            self.statused = result
        
        self.statused = None
        d = self.connected.addCallback(strip(login))
        d.addCallbacks(strip(status), self._ebGeneral)
        d.addCallbacks(statused, self._ebGeneral)
        d.addCallbacks(self._cbStopClient, self._ebGeneral)
        self.loopback()
        
        self.assertEquals(
            self.statused,
            {'MESSAGES': 9, 'UIDNEXT': '10', 'UNSEEN': 4}
        )
    
    def testFailedStatus(self):
        def login():
            return self.client.login('testuser', 'password-test')
        def status():
            return self.client.status('root/nonexistent', 'MESSAGES', 'UIDNEXT', 'UNSEEN')
        def statused(result):
            self.statused = result
        def failed(failure):
            self.failure = failure

        self.statused = self.failure = None
        d = self.connected.addCallback(strip(login))
        d.addCallbacks(strip(status), self._ebGeneral)
        d.addCallbacks(statused, failed)
        d.addCallbacks(self._cbStopClient, self._ebGeneral)
        self.loopback()
        
        self.assertEquals(
            self.statused, None
        )
        self.assertEquals(
            self.failure.value.args,
            ('Could not open mailbox',)
        )

    def testFullAppend(self):
        infile = util.sibpath(__file__, 'rfc822.message')
        message = open(infile)
        SimpleServer.theAccount.addMailbox('root/subthing')
        def login():
            return self.client.login('testuser', 'password-test')
        def append():
            return self.client.append(
                'root/subthing',
                message,
                ('\\SEEN', '\\DELETED'),
                'Tue, 17 Jun 2003 11:22:16 -0600 (MDT)',
            )
        
        d = self.connected.addCallback(strip(login))
        d.addCallbacks(strip(append), self._ebGeneral)
        d.addCallbacks(self._cbStopClient, self._ebGeneral)
        self.loopback()
        
        mb = SimpleServer.theAccount.mailboxes['ROOT/SUBTHING']
        self.assertEquals(1, len(mb.messages))
        self.assertEquals(
            (['\\SEEN', '\\DELETED'], 'Tue, 17 Jun 2003 11:22:16 -0600 (MDT)', 0),
            mb.messages[0][1:]
        )
        self.assertEquals(open(infile).read(), mb.messages[0][0].getvalue())

    def testPartialAppend(self):
        infile = util.sibpath(__file__, 'rfc822.message')
        message = open(infile)
        SimpleServer.theAccount.addMailbox('PARTIAL/SUBTHING')
        def login():
            return self.client.login('testuser', 'password-test')
        def append():
            message = file(infile)
            continuation = defer.Deferred()
            continuation.addCallback(self.client._IMAP4Client__cbContinueAppend, message)
            continuation.addCallback(self.client._IMAP4Client__cbFinishAppend)
            continuation.addErrback(self.client._IMAP4Client__ebContinueAppend)
            return self.client.sendCommand(
                imap4.Command(
                    'APPEND',
                    'PARTIAL/SUBTHING (\\SEEN) "Right now" {%d}' % os.path.getsize(infile),
                    continuation
                )
            ).addCallback(self.client._IMAP4Client__cbAppend)
        
        d = self.connected.addCallback(strip(login))
        d.addCallbacks(strip(append), self._ebGeneral)
        d.addCallbacks(self._cbStopClient, self._ebGeneral)
        d.setTimeout(5)
        self.loopback()
        
        mb = SimpleServer.theAccount.mailboxes['PARTIAL/SUBTHING']
        self.assertEquals(1, len(mb.messages))
        self.assertEquals(
            (['\\SEEN'], 'Right now', 0),
            mb.messages[0][1:]
        )
        self.assertEquals(open(infile).read(), mb.messages[0][0].getvalue())
    
    def testCheck(self):
        SimpleServer.theAccount.addMailbox('root/subthing')
        def login():
            return self.client.login('testuser', 'password-test')
        def select():
            return self.client.select('root/subthing')
        def check():
            return self.client.check()
        
        d = self.connected.addCallback(strip(login))
        d.addCallbacks(strip(select), self._ebGeneral)
        d.addCallbacks(strip(check), self._ebGeneral)
        d.addCallbacks(self._cbStopClient, self._ebGeneral)
        self.loopback()
        
        # Okay, that was fun

    def testClose(self):
        m = SimpleMailbox()
        m.messages = [
            ('Message 1', ('\\Deleted', 'AnotherFlag'), None, 0),
            ('Message 2', ('AnotherFlag',), None, 1),
            ('Message 3', ('\\Deleted',), None, 2),
        ]
        SimpleServer.theAccount.addMailbox('mailbox', m)
        def login():
            return self.client.login('testuser', 'password-test')
        def select():
            return self.client.select('mailbox')
        def close():
            return self.client.close()
        
        d = self.connected.addCallback(strip(login))
        d.addCallbacks(strip(select), self._ebGeneral)
        d.addCallbacks(strip(close), self._ebGeneral)
        d.addCallbacks(self._cbStopClient, self._ebGeneral)
        self.loopback()
        
        self.assertEquals(len(m.messages), 1)
        self.assertEquals(m.messages[0], ('Message 2', ('AnotherFlag',), None, 1))

    def testExpunge(self):
        m = SimpleMailbox()
        m.messages = [
            ('Message 1', ('\\Deleted', 'AnotherFlag'), None, 0),
            ('Message 2', ('AnotherFlag',), None, 1),
            ('Message 3', ('\\Deleted',), None, 2),
        ]
        SimpleServer.theAccount.addMailbox('mailbox', m)
        def login():
            return self.client.login('testuser', 'password-test')
        def select():
            return self.client.select('mailbox')
        def expunge():
            return self.client.expunge()
        def expunged(results):
            self.results = results
        
        self.results = None
        d = self.connected.addCallback(strip(login))
        d.addCallbacks(strip(select), self._ebGeneral)
        d.addCallbacks(strip(expunge), self._ebGeneral)
        d.addCallbacks(expunged, self._ebGeneral)
        d.addCallbacks(self._cbStopClient, self._ebGeneral)
        self.loopback()
        
        self.assertEquals(len(m.messages), 1)
        self.assertEquals(m.messages[0], ('Message 2', ('AnotherFlag',), None, 1))
        
        self.assertEquals(self.results, [0, 2])

class TestRealm:
    theAccount = None

    def requestAvatar(self, avatarId, mind, *interfaces):
        return imap4.IAccount, self.theAccount, lambda: None

class TestChecker:
    credentialInterfaces = (cred.credentials.IUsernameHashedPassword,)

    users = {
        'testuser': 'secret'
    }

    def requestAvatarId(self, credentials):
        if components.implements(credentials, cred.credentials.IUsernameHashedPassword):
            if credentials.username in self.users:
                return defer.maybeDeferred(
                    credentials.checkPassword, self.users[credentials.username]
            ).addCallback(self._cbCheck, credentials.username)
        raise NotImplementedError

    def _cbCheck(self, result, username):
        if result:
            return username
        raise cred.error.UnauthorizedLogin()
    
class AuthenticatorTestCase(IMAP4HelperMixin, unittest.TestCase):
    def setUp(self):
        IMAP4HelperMixin.setUp(self)
        
        realm = TestRealm()
        realm.theAccount = Account('testuser')
        portal = cred.portal.Portal(realm)
        portal.registerChecker(TestChecker())
        self.server.portal = portal

        self.server.challengers['CRAM-MD5'] = cred.credentials.CramMD5Credentials

        cAuth = imap4.CramMD5ClientAuthenticator('testuser')

        self.client.registerAuthenticator(cAuth)
        self.authenticated = 0
        self.account = realm.theAccount

    def testCramMD5(self):
        def auth():
            return self.client.authenticate('secret')
        def authed():
            self.authenticated = 1

        d = self.connected.addCallback(strip(auth))
        d.addCallbacks(strip(authed), self._ebGeneral)
        d.addCallbacks(self._cbStopClient, self._ebGeneral)
        self.loopback()
        
        self.assertEquals(self.authenticated, 1)
        self.assertEquals(self.server.account, self.account)
    
    def testFailedCramMD5(self):
        def misauth():
            return self.client.authenticate('not the secret')
        def authed():
            self.authenticated = 1
        def misauthed():
            self.authenticated = -1
        
        d = self.connected.addCallback(strip(misauth))
        d.addCallbacks(strip(authed), strip(misauthed))
        d.addCallbacks(self._cbStopClient, self._ebGeneral)
        self.loopback()

        self.assertEquals(self.authenticated, -1)
        self.assertEquals(self.server.account, None)


class UnsolicitedResponseTestCase(IMAP4HelperMixin, unittest.TestCase):
    def testReadWrite(self):
        def login():
            return self.client.login('testuser', 'password-test')
        def loggedIn():
            self.server.modeChanged(1)
        
        d = self.connected.addCallback(strip(login))
        d.addCallback(strip(loggedIn)).addErrback(self._ebGeneral)
        self.loopback()
        
        E = self.client.events
        self.assertEquals(E, [['modeChanged', 1]])
        
    def testReadOnly(self):
        def login():
            return self.client.login('testuser', 'password-test')
        def loggedIn():
            self.server.modeChanged(0)
        
        d = self.connected.addCallback(strip(login))
        d.addCallback(strip(loggedIn)).addErrback(self._ebGeneral)
        self.loopback()
        
        E = self.client.events
        self.assertEquals(E, [['modeChanged', 0]])

    def testFlagChange(self):
        flags = {
            1: ['\\Answered', '\\Deleted'],
            5: [],
            10: ['\\Recent']
        }
        def login():
            return self.client.login('testuser', 'password-test')
        def loggedIn():
            self.server.flagsChanged(flags)

        d = self.connected.addCallback(strip(login))
        d.addCallback(strip(loggedIn)).addErrback(self._ebGeneral)
        self.loopback()
        
        E = self.client.events
        expect = [['flagsChanged', {x[0]: x[1]}] for x in flags.items()]
        E.sort()
        expect.sort()
        self.assertEquals(E, expect)

    def testNewMessages(self):
        def login():
            return self.client.login('testuser', 'password-test')
        def loggedIn():
            self.server.newMessages(10, None)

        d = self.connected.addCallback(strip(login))
        d.addCallback(strip(loggedIn)).addErrback(self._ebGeneral)
        self.loopback()
        
        E = self.client.events
        self.assertEquals(E, [['newMessages', 10, None]])

    def testNewRecentMessages(self):
        def login():
            return self.client.login('testuser', 'password-test')
        def loggedIn():
            self.server.newMessages(None, 10)

        d = self.connected.addCallback(strip(login))
        d.addCallback(strip(loggedIn)).addErrback(self._ebGeneral)
        self.loopback()
        
        E = self.client.events
        self.assertEquals(E, [['newMessages', None, 10]])

    def testNewMessagesAndRecent(self):
        def login():
            return self.client.login('testuser', 'password-test')
        def loggedIn():
            self.server.newMessages(20, 10)

        d = self.connected.addCallback(strip(login))
        d.addCallback(strip(loggedIn)).addErrback(self._ebGeneral)
        self.loopback()
        
        E = self.client.events
        self.assertEquals(E, [['newMessages', 20, None], ['newMessages', None, 10]])

class StringTransport:
    disconnecting = 0

    def __init__(self):
        self.io = StringIO()
    
    def write(self, data):
        self.io.write(data)
    
    def writeSequence(self, data):
        self.io.write(''.join(data))
    
    def loseConnection(self):
        pass
    
    def getPeer(self):
        return ('StringIO', repr(self.io))
    
    def getHost(self):
        return ('StringIO', repr(self.io))
    

class HandCraftedTestCase(unittest.TestCase):
    def testTrailingLiteral(self):
        transport = StringTransport()
        c = imap4.IMAP4Client()
        c.makeConnection(transport)
        c.lineReceived('* OK SERVER BANNER')

        d = c.login('blah', 'blah')
        c.dataReceived('0001 OK CAPABILITY\r\n0002 OK LOGIN\r\n')
        self.failUnless(unittest.deferredResult(d))
        
        d = c.select('inbox')
        c.lineReceived('0003 OK SELECT')
        self.failUnless(unittest.deferredResult(d))
        
        d = c.fetchMessage('1')
        c.dataReceived('* 1 FETCH (RFC822 {10}\r\n0123456789\r\n RFC822.SIZE 10)\r\n')
        c.dataReceived('0004 OK FETCH\r\n')
        self.failUnless(unittest.deferredResult(d))

class FakeyServer(imap4.IMAP4Server):
    state = 'select'
    timeout = None
    
    def sendServerGreeting(self):
        pass

class FetchSearchStoreCopyTestCase(unittest.TestCase, IMAP4HelperMixin):
    def setUp(self):
        self.expected = self.result = None
        self.server_received_query = None
        self.server_received_uid = None
        self.server_received_parts = None
        self.server_received_messages = None
        
        self.server = imap4.IMAP4Server()
        self.server.state = 'select'
        self.server.mbox = self
        self.connected = defer.Deferred()
        self.client = SimpleClient(self.connected)
    
    def search(self, query, uid):
        self.server_received_query = query
        self.server_received_uid = uid
        return self.expected
    
    def _searchWork(self, uid):
        def search():
            return self.client.search(self.query, uid=uid)
        def result(R):
            self.result = R

        self.connected.addCallback(strip(search)
        ).addCallback(result
        ).addCallback(self._cbStopClient
        ).addErrback(self._ebGeneral)

        loopback.loopbackTCP(self.server, self.client)
        
        # Ensure no short-circuiting wierdness is going on
        self.failIf(self.result is self.expected)
        
        self.assertEquals(self.result, self.expected)
        self.assertEquals(self.uid, self.server_received_uid)
        self.assertEquals(
            imap4.parseNestedParens(self.query),
            self.server_received_query
        )

    def testSearch(self):
        self.query = imap4.Or(
            imap4.Query(header=('subject', 'substring')),
            imap4.Query(larger=1024, smaller=4096),
        )
        self.expected = [1, 4, 5, 7]
        self.uid = 0
        self._searchWork(0)

    def testUIDSearch(self):
        self.query = imap4.Or(
            imap4.Query(header=('subject', 'substring')),
            imap4.Query(larger=1024, smaller=4096),
        )
        self.uid = 1
        self.expected = [1, 2, 3]
        self._searchWork(1)

    def getUID(self, msg):
        try:
            return self.expected[msg]['UID']
        except (TypeError, IndexError):
            return self.expected[msg-1]
        except KeyError:
            return 42

    def fetch(self, messages, parts, uid):
        self.server_received_uid = uid
        self.server_received_parts = [str(p).upper() for p in parts]
        self.server_received_messages = str(messages)
        return self.expected
    
    def _fetchWork(self, fetch):
        def result(R):
            self.result = R

        self.connected.addCallback(strip(fetch)
        ).addCallback(result
        ).addCallback(self._cbStopClient
        ).addErrback(self._ebGeneral)

        loopback.loopbackTCP(self.server, self.client)
        
        # Ensure no short-circuiting wierdness is going on
        self.failIf(self.result is self.expected)
        
        self.parts and self.parts.sort()
        self.server_received_parts and self.server_received_parts.sort()
        
        if self.uid:
            for (k, v) in self.expected.items():
                v['UID'] = str(k)
        
        self.assertEquals(self.result, self.expected)
        self.assertEquals(self.uid, self.server_received_uid)
        self.assertEquals(self.parts, self.server_received_parts)
        self.assertEquals(imap4.parseIdList(self.messages),
                          imap4.parseIdList(self.server_received_messages))

    def testFetchUID(self):
        def fetch():
            return self.client.fetchUID(self.messages)
        
        self.expected = {
            1: {'UID': '10'},
            2: {'UID': '20'},
            3: {'UID': '21'},
            4: {'UID': '101'},
            101: {'UID': '202'}
        }
        self.messages = '1:56,60,103:109'
        self.parts = ['UID']
        self.uid = 0
        self._fetchWork(fetch)

    def testFetchFlags(self, uid=0):
        def fetch():
            return self.client.fetchFlags(self.messages, uid=uid)
        
        self.expected = {
            32: {'FLAGS': ['\\RECENT']},
            64: {'FLAGS': ['\\DELETED', '\\UNSEEN']},
            128: {'FLAGS': []}
        }
        self.messages = '5:102,202:*'
        self.parts = ['FLAGS']
        self.uid = uid
        self._fetchWork(fetch)
    
    def testFetchFlagsUID(self):
        self.testFetchFlags(1)

    def testFetchInternalDate(self, uid=0):
        def fetch():
            return self.client.fetchInternalDate(self.messages, uid=uid)
        
        self.expected = {
            10: {'INTERNALDATE': '20-Oct-1981 03:25:19 -0500'},
            20: {'INTERNALDATE': '15-Feb-1985 01:30:05 +0900'},
            21: {'INTERNALDATE': '01-Jun-1992 13:51:48 -0100'},
        }
        self.messages = '1,69,72,103'
        self.parts = ['INTERNALDATE']
        self.uid = uid
        self._fetchWork(fetch)
    
    def testFetchInternalDateUID(self):
        self.testFetchInternalDate(1)

    def testFetchEnvelope(self, uid=0):
        def fetch():
            return self.client.fetchEnvelope(self.messages, uid=uid)
        
        self.expected = {
            102: {'ENVELOPE': 'some data'},
        }
        self.messages = '72:102,103'
        self.parts = ['ENVELOPE']
        self.uid = uid
        self._fetchWork(fetch)

    def testFetchEnvelopeUID(self):
        self.testFetchEnvelope(1)
    
    def testFetchBodyStructure(self, uid=0):
        def fetch():
            return self.client.fetchBodyStructure(self.messages, uid=uid)
        
        self.expected = {
            103: {'BODYSTRUCTURE': 'lots of gross information'},
        }
        self.messages = '1:*'
        self.parts = ['BODYSTRUCTURE']
        self.uid = uid
        self._fetchWork(fetch)
    
    def testFetchBodyStructureUID(self):
        self.testFetchBodyStructure(1)
    
    def testFetchSimplifiedBody(self, uid=0):
        def fetch():
            return self.client.fetchSimplifiedBody(self.messages, uid=uid)
        
        self.expected = {
            2: {'BODY': 'XXX fill this in bucko'},
        }
        self.messages = '2,5,10'
        self.parts = ['BODY']
        self.uid = uid
        self._fetchWork(fetch)
    
    def testFetchSimplifiedBodyUID(self):
        self.testFetchSimplifiedBody(1)

    def testFetchMessage(self, uid=0):
        def fetch():
            return self.client.fetchMessage(self.messages, uid=uid)
        
        self.expected = {
            29281: {'RFC822': 'XXX fill this in bucko'},
        }
        self.messages = '19884,1,23872,666:777'
        self.parts = ['RFC822']
        self.uid = uid
        self._fetchWork(fetch)
    
    def testFetchMessageUID(self):
        self.testFetchMessage(1)

    def testFetchHeaders(self, uid=0):
        def fetch():
            return self.client.fetchHeaders(self.messages, uid=uid)
        
        self.expected = {
            19: {'RFC822.HEADER': 'XXX put some headers here'},
        }
        self.messages = '2:3,4:5,6:*'
        self.parts = ['RFC822.HEADER']
        self.uid = uid
        self._fetchWork(fetch)
    
    def testFetchHeadersUID(self):
        self.testFetchHeaders(1)

    def testFetchBody(self, uid=0):
        def fetch():
            return self.client.fetchBody(self.messages, uid=uid)
        
        self.expected = {
            1: {'RFC822.TEXT': 'XXX put some body here'},
        }
        self.messages = '1,2,3,4,5,6,7'
        self.parts = ['RFC822.TEXT']
        self.uid = uid
        self._fetchWork(fetch)
    
    def testFetchBodyUID(self):
        self.testFetchBody(1)

    def testFetchSize(self, uid=0):
        def fetch():
            return self.client.fetchSize(self.messages, uid=uid)
        
        self.expected = {
            1: {'RFC822.SIZE': '12345'},
        }
        self.messages = '1:100,2:*'
        self.parts = ['RFC822.SIZE']
        self.uid = uid
        self._fetchWork(fetch)
    
    def testFetchSizeUID(self):
        self.testFetchSize(1)
    
    def testFetchFull(self, uid=0):
        def fetch():
            return self.client.fetchFull(self.messages, uid=uid)
        
        self.expected = {
            1: {
                'FLAGS': 'XXX put some flags here',
                'INTERNALDATE': 'Sun, 25 Jul 2010 06:20:30 -0400 (EDT)',
                'RFC822.SIZE': '12345',
                'ENVELOPE': 'XXX envelope',
                'BODY': 'XXX body',
            },
            3: {
                'FLAGS': 'XXX put some flags here',
                'INTERNALDATE': 'Mon, 14 Apr 2003 19:43:44 -0400',
                'RFC822.SIZE': '12345',
                'ENVELOPE': 'XXX envelope',
                'BODY': 'XXX body',
            }
        }
        self.messages = '1,3'
        self.parts = ['FLAGS', 'INTERNALDATE', 'RFC822.SIZE', 'ENVELOPE', 'BODY']
        self.uid = uid
        self._fetchWork(fetch)
    
    def testFetchFullUID(self):
        self.testFetchFull(1)

    def testFetchAll(self, uid=0):
        def fetch():
            return self.client.fetchAll(self.messages, uid=uid)
        
        self.expected = {
            1: {
                'ENVELOPE': 'the envelope looks like this',
                'RFC822.SIZE': '1023',
                'INTERNALDATE': 'Tuesday',
                'FLAGS': [],
            }, 2: {
                'ENVELOPE': 'another envelope',
                'RFC822.SIZE': '3201',
                'INTERNALDATE': 'Friday',
                'FLAGS': ['\\SEEN', '\\DELETED'],
            }
        }
        self.messages = '1,2:3'
        self.parts = ['ENVELOPE', 'RFC822.SIZE', 'INTERNALDATE', 'FLAGS']
        self.uid = uid
        self._fetchWork(fetch)

    def testFetchAllUID(self):
        self.testFetchFull(1)
    
    def testFetchFast(self, uid=0):
        def fetch():
            return self.client.fetchFast(self.messages, uid=uid)
        
        self.expected = {
            1: {
                'FLAGS': [],
                'INTERNALDATE': '19 Mar 2003 19:22:21 -0500',
                'RFC822.SIZE': '12345',
            },
        }
        self.messages = '1'
        self.parts = ['FLAGS', 'INTERNALDATE', 'RFC822.SIZE']
        self.uid = uid
        self._fetchWork(fetch)
    
    def testFetchFastUID(self):
        self.testFetchFast(1)
        
class TLSTestCase(IMAP4HelperMixin, unittest.TestCase):
    serverCTX = ServerTLSContext()
    clientCTX = ClientTLSContext()

    def loopback(self):
        loopback.loopbackTCP(self.server, self.client)

    def testAPileOfThings(self):
        SimpleServer.theAccount.addMailbox('inbox')
        called = []
        def login():
            called.append(None)
            return self.client.login('testuser', 'password-test')
        def list():
            called.append(None)
            return self.client.list('inbox', '%')
        def status():
            called.append(None)
            return self.client.status('inbox', 'UIDNEXT')
        def examine():
            called.append(None)
            return self.client.examine('inbox')
        def logout():
            called.append(None)
            return self.client.logout()
        
        self.client.requireTransportSecurity = True

        methods = [login, list, status, examine, logout]
        map(self.connected.addCallback, map(strip, methods))
        self.connected.addCallbacks(self._cbStopClient, self._ebGeneral)
        self.loopback()
        
        self.assertEquals(self.server.startedTLS, True)
        self.assertEquals(self.client.startedTLS, True)
        self.assertEquals(len(called), len(methods))

if ClientTLSContext is None:
    for case in (TLSTestCase,):
        case.skip = "OpenSSL not present"
