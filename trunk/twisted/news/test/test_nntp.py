# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

from twisted.trial import unittest
from twisted.news import database
from twisted.news import nntp
from twisted.protocols import loopback
from twisted.test import proto_helpers

ALL_GROUPS = ('alt.test.nntp', 0, 1, 'y'),
GROUP = ('0', '1', '0', 'alt.test.nntp', 'group', 'selected')
SUBSCRIPTIONS = ['alt.test.nntp', 'news.testgroup']

POST_STRING = """Path: not-for-mail
From: <exarkun@somehost.domain.com>
Subject: a test
Newsgroups: alt.test.nntp
Organization: 
Summary: 
Keywords: 
User-Agent: tin/1.4.5-20010409 ("One More Nightmare") (UNIX) (Linux/2.4.17 (i686))

this is a test
.
..
...
lala
moo
-- 
"One World, one Web, one Program." - Microsoft(R) promotional ad
"Ein Volk, ein Reich, ein Fuhrer." - Adolf Hitler
--
 10:56pm up 4 days, 4:42, 1 user, load average: 0.08, 0.08, 0.12
"""

class TestNNTPClient(nntp.NNTPClient):
    def __init__(self):
        nntp.NNTPClient.__init__(self)

    def assertEqual(self, foo, bar):
        if foo != bar: raise AssertionError("%r != %r!" % (foo, bar))

    def connectionMade(self):
        nntp.NNTPClient.connectionMade(self)
        self.fetchSubscriptions()


    def gotSubscriptions(self, subscriptions):
        self.assertEqual(len(subscriptions), len(SUBSCRIPTIONS))
        for s in subscriptions:
            assert s in SUBSCRIPTIONS

        self.fetchGroups()

    def gotAllGroups(self, info):
        self.assertEqual(len(info), len(ALL_GROUPS))
        self.assertEqual(info[0], ALL_GROUPS[0])

        self.fetchGroup('alt.test.nntp')


    def getAllGroupsFailed(self, error):
        raise AssertionError("fetchGroups() failed: %s" % (error,))


    def gotGroup(self, info):
        self.assertEqual(len(info), 6)
        self.assertEqual(info, GROUP)

        self.postArticle(POST_STRING)


    def getSubscriptionsFailed(self, error):
        raise AssertionError("fetchSubscriptions() failed: %s" % (error,))


    def getGroupFailed(self, error):
        raise AssertionError("fetchGroup() failed: %s" % (error,))


    def postFailed(self, error):
        raise AssertionError("postArticle() failed: %s" % (error,))


    def postedOk(self):
        self.fetchArticle(1)


    def gotArticle(self, info):
        origBody = POST_STRING.split('\n\n')[1]
        newBody = info.split('\n\n', 1)[1]

        self.assertEqual(origBody, newBody)

        # We're done
        self.transport.loseConnection()


    def getArticleFailed(self, error):
        raise AssertionError("fetchArticle() failed: %s" % (error,))


class NNTPTestCase(unittest.TestCase):
    def setUp(self):
        self.server = nntp.NNTPServer()
        self.server.factory = self
        self.backend = database.NewsShelf(None, 'news.db')
        self.backend.addGroup('alt.test.nntp', 'y')

        for s in SUBSCRIPTIONS:
            self.backend.addSubscription(s)

        self.transport = proto_helpers.StringTransport()
        self.server.makeConnection(self.transport)
        self.client = TestNNTPClient()

    def testLoopback(self):
        return loopback.loopbackAsync(self.server, self.client)

        # XXX This test is woefully incomplete.  It tests the single
        # most common code path and nothing else.  Expand it and the
        # test fairy will leave you a surprise.

        #         reactor.iterate(1) # fetchGroups()
        #         reactor.iterate(1) # fetchGroup()
        #         reactor.iterate(1) # postArticle()


    def test_connectionMade(self):
        """
        When L{NNTPServer} is connected, it sends a server greeting to the
        client.
        """
        self.assertEqual(
            self.transport.value().split('\r\n'), [
                '200 server ready - posting allowed',
                ''])


    def test_LIST(self):
        """
        When L{NTTPServer} receives a I{LIST} command, it sends a list of news
        groups to the client (RFC 3977, section 7.6.1.1).
        """
        self.transport.clear()
        self.server.do_LIST()
        self.assertEqual(
            self.transport.value().split('\r\n'), [
                '215 newsgroups in form "group high low flags"',
                'alt.test.nntp 0 1 y',
                '.',
                ''])


    def test_GROUP(self):
        """
        When L{NNTPServer} receives a I{GROUP} command, it sends a line of
        information about that group to the client (RFC 3977, section 6.1.1.1).
        """
        self.transport.clear()
        self.server.do_GROUP('alt.test.nntp')
        self.assertEqual(
            self.transport.value().split('\r\n'), [
                '211 0 1 0 alt.test.nntp group selected',
                ''])


    def test_LISTGROUP(self):
        """
        When L{NNTPServer} receives a I{LISTGROUP} command, it sends a list of
        message numbers for the messages in a particular group (RFC 3977,
        section 6.1.2.1).
        """
        self.transport.clear()
        self.server.do_LISTGROUP('alt.test.nntp')
        self.assertEqual(
            self.transport.value().split('\r\n'), [
                '211 list of article numbers follow',
                '.',
                ''])


    def test_XROVER(self):
        """
        When L{NTTPServer} receives a I{XROVER} command, it sends a list of
        I{References} header values for the messages in a particular group (RFC
        2980, section 2.11).
        """
        self.server.do_GROUP('alt.test.nntp')
        self.transport.clear()

        self.server.do_XROVER()
        self.assertEqual(
            self.transport.value().split('\r\n'), [
                '221 Header follows',
                '.',
                ''])
