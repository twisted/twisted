# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

from twisted.trial import unittest
from twisted.news import database
from twisted.news import nntp
from twisted.protocols import loopback

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

    def assertEquals(self, foo, bar):
        if foo != bar: raise AssertionError("%r != %r!" % (foo, bar))
    
    def connectionMade(self):
        nntp.NNTPClient.connectionMade(self)
        self.fetchSubscriptions()


    def gotSubscriptions(self, subscriptions):
        self.assertEquals(len(subscriptions), len(SUBSCRIPTIONS))
        for s in subscriptions:
            assert s in SUBSCRIPTIONS

        self.fetchGroups()
    
    def gotAllGroups(self, info):
        self.assertEquals(len(info), len(ALL_GROUPS))
        self.assertEquals(info[0], ALL_GROUPS[0])
        
        self.fetchGroup('alt.test.nntp')
    
    
    def getAllGroupsFailed(self, error):
        raise AssertionError("fetchGroups() failed: %s" % (error,))


    def gotGroup(self, info):
        self.assertEquals(len(info), 6)
        self.assertEquals(info, GROUP)
        
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

        self.assertEquals(origBody, newBody)
        
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

        self.client = TestNNTPClient()

    def testLoopback(self):
        return loopback.loopbackAsync(self.server, self.client)

        # XXX This test is woefully incomplete.  It tests the single
        # most common code path and nothing else.  Expand it and the
        # test fairy will leave you a surprise.

        #         reactor.iterate(1) # fetchGroups()
        #         reactor.iterate(1) # fetchGroup()
        #         reactor.iterate(1) # postArticle()

