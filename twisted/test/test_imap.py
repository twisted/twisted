# -*- coding: Latin-1 -*-

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
    pass

class SimpleServer(imap4.IMAP4Server):
    def authenticateLogin(self, username, password):
        if username == 'testuser' and password == 'password-test':
            return 'This is my mailbox'
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
    
    def _cbStopClient(self):
        self.client.transport.loseConnection()

    def _ebGeneral(self, failure):
        self.client.transport.loseConnection()
        self.server.transport.loseConnection()
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
        
        self.assertEquals(self.server.mbox, 'This is my mailbox')
