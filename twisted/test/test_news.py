# Twisted, the Framework of Your Internet
# Copyright (C) 2003 Matthew W. Lefkowitz
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
import os, types
from pprint import pformat

from twisted.trial import unittest
from twisted.news import news, database
from twisted.internet import reactor

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

class NewsTestCase(unittest.TestCase):
    def callback(self, result):
        self.result = result

    def errback(self, failure):
        try:
            self.fail('Errback called: ' + str(failure))
        except Exception, e:
            self.error = sys.exc_info()
            raise

    def timeout(self):
        reactor.crash()
        self.fail('Timed out')

    def setUp(self):
        self.backend = database.NewsShelf(None, 'news2.db')
        self.backend.addGroup('alt.test.nntp', 'y')
        self.backend.postRequest(POST_STRING.replace('\n', '\r\n'))

    def tearDown(self):
        try:
            del self.result
        except:
            pass
        try:
            del self.error
        except:
            pass

    def testArticleExists(self):
        d = self.backend.articleExistsRequest(MESSAGE_ID)
        self.assert_(d.result)

    def testArticleRequest(self):
        d = self.backend.articleRequest(None, None, MESSAGE_ID)
        d.addCallbacks(self.callback, self.errback)

        id = reactor.callLater(5, self.timeout)
        while not hasattr(self, 'result') and not hasattr(self, 'error'):
            reactor.iterate()
        try:
            id.cancel()
        except ValueError: pass

        error = getattr(self, 'error', None)
        if error:
            raise error[0], error[1], error[2]

        self.failUnless(type(self.result) == types.TupleType,
                        'callback result is wrong type: ' + str(self.result))
        self.failUnless(len(self.result) == 3,
                        'callback result list should have three entries: ' +
                        str(self.result))
        self.failUnless(self.result[1] == MESSAGE_ID,
                        "callback result Message-Id doesn't match: %s vs %s" %
                        (MESSAGE_ID, self.result[1]))
        body = self.result[2].read()
        self.failUnless(body.find('\r\n\r\n'),
                        "Can't find \\r\\n\\r\\n between header and body")

    def testHeadRequest(self):
        self.testArticleRequest()
        index = self.result[0]

        try: del self.result
        except: pass

        try: del self.error
        except: pass

        d = self.backend.headRequest("alt.test.nntp", index)
        d.addCallbacks(self.callback, self.errback)

        id = reactor.callLater(5, self.timeout)
        while not hasattr(self, 'result') and not hasattr(self, 'error'):
            reactor.iterate()
        try:
            id.cancel()
        except ValueError: pass

        error = getattr(self, 'error', None)
        if error:
            raise error[0], error[1], error[2]

        self.failUnless(self.result[1] == MESSAGE_ID,
                        "callback result Message-Id doesn't match: %s vs %s" %
                        (MESSAGE_ID, self.result[1]))

        self.failUnless(self.result[2][-2:] == '\r\n',
                        "headers must be \\r\\n terminated.")

    def testBodyRequest(self):
        self.testArticleRequest()
        index = self.result[0]

        try: del self.result
        except: pass

        try: del self.error
        except: pass

        d = self.backend.bodyRequest("alt.test.nntp", index)
        d.addCallbacks(self.callback, self.errback)

        id = reactor.callLater(5, self.timeout)
        while not hasattr(self, 'result') and not hasattr(self, 'error'):
            reactor.iterate()
        try:
            id.cancel()
        except ValueError: pass

        error = getattr(self, 'error', None)
        if error:
            raise error[0], error[1], error[2]

        body = self.result[2].read()
        self.failUnless(body[0:4] == 'this', "message body has been altered: " +
                        pformat(body[0:4]))
