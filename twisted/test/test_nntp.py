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
import os, string

from pyunit import unittest
from twisted.news import news, database
from twisted.protocols import nntp, loopback
from twisted.protocols import protocol
from twisted.internet import main

ALL_GROUPS = ('alt.test.nntp', 0, 0, 'y')
GROUP = ('0', '0', '0', 'alt.test.nntp', 'group', 'selected')

POST_STRING = """Path: not-for-mail
From: <exarkun@somehost.domain.com>
Subject: a test
Newsgroups: alt.test.nntp
Organization: 
Summary: 
Keywords: 
User-Agent: tin/1.4.5-20010409 ("One More Nightmare") (UNIX) (Linux/2.4.17 (i686))

this is a test

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
        if foo != bar: raise AssertionError("%s != %s!" % (foo, bar))
    
    def connectionMade(self):
        nntp.NNTPClient.connectionMade(self)
        self.fetchGroups()
    
    def gotAllGroups(self, info):
        self.assertEquals(len(info), 1)
        self.assertEquals(info[0], ALL_GROUPS)
        
        self.fetchGroup('alt.test.nntp')

    def gotGroup(self, info):
        self.assertEquals(len(info), 6)
        self.assertEquals(info, GROUP)
        
        self.postArticle(string.replace(POST_STRING, '\n', '\r\n'))

    def postFailed(self, err):
        raise err

    def postOk(self):
        self.fetchArticle(1)
    
    def gotArticle(self, info):
        self.transport.loseConnection()


class NNTPTestCase(unittest.TestCase):
    def setUp(self):
        # Re-init pickle db, we depend on no articles
        database.PickleStorage.sharedDB = {'alt.test.nntp': {}, 'groups': ['alt.test.nntp']}

    def testLoopback(self):
        server = nntp.NNTPServer(database.PickleStorage)
        client = TestNNTPClient()
        loopback.loopback(server, client)

        # XXX FIXME three things seem to be task.schedule'd here, and I don't
        # really know what they are.
        main.iterate(); main.iterate(); main.iterate()

    def tearDown(self):
        # Clean up the pickle file
        os.remove('news.pickle')
