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

from twisted.protocols import imap4, loopback
from twisted.internet import defer
from twisted.trial import unittest

def strip(f):
    return lambda result: f()

class IMAP4HelperTestCase(unittest.TestCase):
    def testQuotedSplitter(self):
        cases = [
            '''Hello World''',
            '''Hello "World!"''',
            '''World "Hello" "How are you?"''',
            '''"Hello world" How "are you?"''',
        ]
        
        answers = [
            ['Hello', 'World'],
            ['Hello', 'World!'],
            ['World', 'Hello', 'How are you?'],
            ['Hello world', 'How', 'are you?'],
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
        cases = [
            '(FLAGS (\Seen) INTERNALDATE "17-Jul-1996 02:44:25 -0700"'
            'RFC822.SIZE 4286 ENVELOPE ("Wed, 17 Jul 1996 02:23:25 -0700 (PDT)" '
            '"IMAP4rev1 WG mtg summary and minutes" '
            '(("Terry Gray" NIL "gray" "cac.washington.edu")) '
            '(("Terry Gray" NIL "gray" "cac.washington.edu")) '
            '(("Terry Gray" NIL "gray" "cac.washington.edu")) '
            '((NIL NIL "imap" "cac.washington.edu")) '
            '((NIL NIL "minutes" "CNRI.Reston.VA.US") '
            '("John Klensin" NIL "KLENSIN" "INFOODS.MIT.EDU")) NIL NIL '
            '"<B27397-0100000@cac.washington.edu>") '
            'BODY ("TEXT" "PLAIN" ("CHARSET" "US-ASCII") NIL NIL "7BIT" 3028 92))',
        ]
        
        answers = [
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
            self.assertEquals(imap4.parseNestedParens(case), expected)

class SimpleMailbox:
    flags = ('\\Flag1', 'Flag2', 'LastFlag')

    def getFlags(self):
        return self.flags
    
    def getUID(self):
        return 42
    
    def getMessageCount(self):
        return 9
    
    def getRecentCount(self):
        return 3
    
    def isWriteable(self):
        return 1
    
    def destroy(self):
        pass

class SimpleServer(imap4.IMAP4Server):
    def authenticateLogin(self, username, password):
        if username == 'testuser' and password == 'password-test':
            return self.theAccount
        return None

class SimpleClient(imap4.IMAP4Client):
    def __init__(self, deferred):
        imap4.IMAP4Client.__init__(self)
        self.deferred = deferred

    def connectionMade(self):
        self.deferred.callback(None)

class IMAP4ServerTestCase(unittest.TestCase):
    def setUp(self):
        d = defer.Deferred()
        self.server = SimpleServer()
        self.client = SimpleClient(d)
        self.connected = d

        theAccount = imap4.Account()
        theAccount.mboxType = SimpleMailbox
        SimpleServer.theAccount = theAccount

    
    def tearDown(self):
        del self.server
        del self.client
        del self.connected

    def _cbStopClient(self):
        self.client.transport.loseConnection()

    def _ebGeneral(self, failure):
        self.client.transport.loseConnection()
        self.server.transport.loseConnection()
        failure.printTraceback(file('failure.log', 'w'))
        raise failure.value

    def testCapability(self):
        caps = {}
        def getCaps():
            def gotCaps(c):
                caps.update(c)
                self.server.transport.loseConnection()
            return self.client.getCapabilities().addCallback(gotCaps)
        self.connected.addCallback(strip(getCaps)).addErrback(self._ebGeneral)
        loopback.loopback(self.server, self.client)
        
        refCaps = self.server.CAPABILITIES.copy()
        refCaps['IMAP4rev1'] = None
        self.assertEquals(refCaps, caps)
    
    def testLogout(self):
        self.loggedOut = 0
        def logout():
            def setLoggedOut():
                self.loggedOut = 1
            self.client.logout().addCallback(strip(setLoggedOut))
        self.connected.addCallback(strip(logout)).addErrback(self._ebGeneral)
        loopback.loopback(self.server, self.client)
        
        self.assertEquals(self.loggedOut, 1)

    def testNoop(self):
        self.responses = None
        def noop():
            def setResponses(responses):
                self.responses = responses
                self.server.transport.loseConnection()
            self.client.noop().addCallback(setResponses)
        self.connected.addCallback(strip(noop)).addErrback(self._ebGeneral)
        loopback.loopback(self.server, self.client)
        
        self.assertEquals(self.responses, [])

    def testAuthenticate(self):
        raise unittest.SkipTest, "No authentication schemes implemented to test"

        self.authenticated = 0
        def auth():
            def setAuth():
                self.authenticated = 1
                self.server.transport.loseConnection()
            d = self.client.authenticate('secret')
            d.addCallback(strip(setAuth))
            d.addErrbacks(self._ebGeneral)
        self.connected.addCallback(strip(auth)).addErrback(self._ebGeneral)
        loopback.loopback(self.server, self.client)
        
        self.assertEquals(self.authenticated, 1)

    def testLogin(self):
        def login():
            d = self.client.login('testuser', 'password-test')
            d.addCallback(strip(self._cbStopClient))
        self.connected.addCallback(strip(login)).addErrback(self._ebGeneral)
        loopback.loopback(self.server, self.client)
        
        self.assertEquals(self.server.account, SimpleServer.theAccount)
        self.assertEquals(self.server.state, 'auth')

    def testFailedLogin(self):
        def login():
            d = self.client.login('testuser', 'wrong-password')
            d.addBoth(strip(self._cbStopClient))

        self.connected.addCallback(strip(login)).addErrback(self._ebGeneral)
        loopback.loopback(self.server, self.client)

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
                self._cbStopClient()
            d = self.client.select('test-mailbox')
            d.addCallback(selected)
            return d

        d = self.connected.addCallback(strip(login))
        d.addCallback(strip(select))
        d.addErrback(self._ebGeneral)
        loopback.loopback(self.server, self.client)
        
        mbox = SimpleServer.theAccount.mailboxes['TEST-MAILBOX']
        self.assertEquals(self.server.mbox, mbox)
        self.assertEquals(self.selectedArgs, {
            'EXISTS': 9, 'RECENT': 3, 'UID': 42,
            'FLAGS': ('\\Flag1', 'Flag2', 'LastFlag'),
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
                self._cbStopClient()
            d = self.client.examine('test-mailbox')
            d.addCallback(examined)
            return d

        d = self.connected.addCallback(strip(login))
        d.addCallback(strip(examine))
        d.addErrback(self._ebGeneral)
        loopback.loopback(self.server, self.client)
        
        mbox = SimpleServer.theAccount.mailboxes['TEST-MAILBOX']
        self.assertEquals(self.server.mbox, mbox)
        self.assertEquals(self.examinedArgs, {
            'EXISTS': 9, 'RECENT': 3, 'UID': 42,
            'FLAGS': ('\\Flag1', 'Flag2', 'LastFlag'),
            'READ-WRITE': 0
        })

    def testCreate(self):
        succeed = ('testbox', 'test/box', 'test/', 'test/box/box')
        fail = ('INBOX', 'testbox', 'test/box')
        
        def cb(): self.result.append(1)
        def eb(failure): self.result.append(0)
        
        def login():
            return self.client.login('testuser', 'password-test')
        def create():
            for name in succeed + fail:
                d = self.client.create(name)
                d.addCallback(strip(cb)).addErrback(eb)
            d.addCallbacks(strip(self._cbStopClient), self._ebGeneral)

        self.result = []
        d = self.connected.addCallback(strip(login)).addCallback(strip(create))
        loopback.loopback(self.server, self.client)
        
        self.assertEquals(self.result, [1] * len(succeed) + [0] * len(fail))
        mbox = SimpleServer.theAccount.mailboxes.keys()
        answers = ['testbox', 'test/box', 'test', 'test/box/box']
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
        d.addCallback(strip(delete))
        d.addCallbacks(strip(self._cbStopClient), self._ebGeneral)
        loopback.loopback(self.server, self.client)
        
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
        d.addCallbacks(strip(self._cbStopClient), self._ebGeneral)
        loopback.loopback(self.server, self.client)
        
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
        d.addCallbacks(strip(self._cbStopClient), self._ebGeneral)
        loopback.loopback(self.server, self.client)
        
        self.assertEquals(str(self.failure.value), "Hierarchically inferior mailboxes exist and \\Noselect is set")
