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

import os, types

from twisted.protocols import imap4, loopback
from twisted.internet import defer
from twisted.trial import unittest
from twisted.python import util

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
            '(BODY.PEEK[HEADER.FIELDS.NOT (subject bcc cc)] {100})',

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
            ['BODY.PEEK', ['HEADER.FIELDS.NOT', ['subject', 'bcc', 'cc']], '{100}'],

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
            [1],
            [1, 2],
            [1, 3, 5],
            range(1, 11),
            range(1, 12),
            range(1, 6) + range(10, 21),
            [1] + range(5, 11),
            [1] + range(5, 11) + range(15, 21),
            range(1, 11) + [15] + range(20, 26),
        ]
        
        for (input, expected) in zip(inputs, outputs):
            self.assertEquals(imap4.parseIdList(input), expected)

class SimpleMailbox:
    flags = ('\\Flag1', 'Flag2', '\\AnotherSysFlag', 'LastFlag')
    messages = []
    mUID = 0

    def getFlags(self):
        return self.flags
    
    def getUID(self):
        return 42
    
    def getMessageCount(self):
        return 9
    
    def getRecentCount(self):
        return 3

    def getUnseenCount(self):
        return 4
    
    def isWriteable(self):
        return 1
    
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
        failure.printTraceback(open('failure.log', 'w'))
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
            'FLAGS': ('\\Flag1', 'Flag2', '\\AnotherSysFlag', 'LastFlag'),
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
        d.addCallbacks(strip(delete), self._ebGeneral)
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

    def testRename(self):
        SimpleServer.theAccount.addMailbox('oldmbox')
        def login():
            return self.client.login('testuser', 'password-test')
        def rename():
            return self.client.rename('oldmbox', 'newname')
        
        d = self.connected.addCallback(strip(login))
        d.addCallbacks(strip(rename), self._ebGeneral)
        d.addCallbacks(strip(self._cbStopClient), self._ebGeneral)
        loopback.loopback(self.server, self.client)
        
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
        d.addCallbacks(strip(self._cbStopClient), self._ebGeneral)
        loopback.loopback(self.server, self.client)
        
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
        d.addCallbacks(strip(self._cbStopClient), self._ebGeneral)
        loopback.loopback(self.server, self.client)
        
        self.assertEquals(SimpleServer.theAccount.subscriptions, ['THIS/MBOX'])
    
    def testUnsubscribe(self):
        SimpleServer.theAccount.subscriptions = ['THIS/MBOX', 'THAT/MBOX']
        def login():
            return self.client.login('testuser', 'password-test')
        def unsubscribe():
            return self.client.unsubscribe('this/mbox')
        
        d = self.connected.addCallback(strip(login))
        d.addCallbacks(strip(unsubscribe), self._ebGeneral)
        d.addCallbacks(strip(self._cbStopClient), self._ebGeneral)
        loopback.loopback(self.server, self.client)
        
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
        d.addCallbacks(strip(self._cbStopClient), self._ebGeneral)
        loopback.loopback(self.server, self.client)
        
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
        d.addCallbacks(strip(self._cbStopClient), self._ebGeneral)
        loopback.loopback(self.server, self.client)
        
        self.assertEquals(
            self.statused,
            {'MESSAGES': 9, 'UIDNEXT': '10', 'UNSEEN': 4}
        )

    def testAppend(self):
        infile = util.sibpath(__file__, 'rfc822.message')
        message = open(infile).read()
        SimpleServer.theAccount.addMailbox('root/subthing')
        def login():
            return self.client.login('testuser', 'password-test')
        def append():
            return self.client.append('root/subthing', message, (), 'This Date String Is Illegal')
        
        d = self.connected.addCallback(strip(login))
        d.addCallbacks(strip(append), self._ebGeneral)
        d.addCallbacks(strip(self._cbStopClient), self._ebGeneral)
        loopback.loopback(self.server, self.client)
        
        mb = SimpleServer.theAccount.mailboxes['ROOT/SUBTHING']
        self.assertEquals(
            1,
            len(mb.messages)
        )
        self.assertEquals(
            [(message, (), 'This Date String Is Illegal', 0)],
            mb.messages
        )

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
        d.addCallbacks(strip(self._cbStopClient), self._ebGeneral)
        loopback.loopback(self.server, self.client)
        
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
        d.addCallbacks(strip(self._cbStopClient), self._ebGeneral)
        loopback.loopback(self.server, self.client)
        
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
        d.addCallbacks(strip(self._cbStopClient), self._ebGeneral)
        loopback.loopback(self.server, self.client)
        
        self.assertEquals(len(m.messages), 1)
        self.assertEquals(m.messages[0], ('Message 2', ('AnotherFlag',), None, 1))
        
        self.assertEquals(self.results, [0, 2])
