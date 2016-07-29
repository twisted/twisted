# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

from pprint import pformat

from twisted.trial import unittest
from twisted.news import database

MESSAGE_ID = "f83ba57450ed0fd8ac9a472b847e830e"

POST_STRING = """Path: not-for-mail
From: <exarkun@somehost.domain.com>
Subject: a test
Newsgroups: alt.test.nntp
Organization: 
Summary: 
Keywords: 
Message-Id: %s
User-Agent: tin/1.4.5-20010409 ("One More Nightmare") (UNIX) (Linux/2.4.17 (i686))

this is a test
...
lala
moo
-- 
"One World, one Web, one Program." - Microsoft(R) promotional ad
"Ein Volk, ein Reich, ein Fuhrer." - Adolf Hitler
--
 10:56pm up 4 days, 4:42, 1 user, load average: 0.08, 0.08, 0.12
""" % (MESSAGE_ID)

class NewsTests(unittest.TestCase):
    def setUp(self):
        self.backend = database.NewsShelf(None, 'news2.db')
        self.backend.addGroup('alt.test.nntp', 'y')
        self.backend.postRequest(POST_STRING.replace('\n', '\r\n'))


    def testArticleExists(self):
        d = self.backend.articleExistsRequest(MESSAGE_ID)
        d.addCallback(self.assertTrue)
        return d


    def testArticleRequest(self):
        d = self.backend.articleRequest(None, None, MESSAGE_ID)

        def cbArticle(result):
            self.assertTrue(isinstance(result, tuple),
                            'callback result is wrong type: ' + str(result))
            self.assertEqual(len(result), 3,
                              'callback result list should have three entries: ' +
                              str(result))
            self.assertEqual(result[1], MESSAGE_ID,
                              "callback result Message-Id doesn't match: %s vs %s" %
                              (MESSAGE_ID, result[1]))
            body = result[2].read()
            self.assertNotEqual(body.find('\r\n\r\n'), -1,
                             "Can't find \\r\\n\\r\\n between header and body")
            return result

        d.addCallback(cbArticle)
        return d


    def testHeadRequest(self):
        d = self.testArticleRequest()

        def cbArticle(result):
            index = result[0]

            d = self.backend.headRequest("alt.test.nntp", index)
            d.addCallback(cbHead)
            return d

        def cbHead(result):
            self.assertEqual(result[1], MESSAGE_ID,
                              "callback result Message-Id doesn't match: %s vs %s" %
                              (MESSAGE_ID, result[1]))

            self.assertEqual(result[2][-2:], '\r\n',
                              "headers must be \\r\\n terminated.")

        d.addCallback(cbArticle)
        return d


    def testBodyRequest(self):
        d = self.testArticleRequest()

        def cbArticle(result):
            index = result[0]

            d = self.backend.bodyRequest("alt.test.nntp", index)
            d.addCallback(cbBody)
            return d

        def cbBody(result):
            body = result[2].read()
            self.assertEqual(body[0:4], 'this',
                              "message body has been altered: " +
                              pformat(body[0:4]))

        d.addCallback(cbArticle)
        return d
