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
import os, string, shutil

from twisted.trial import unittest

goodnews = False
try:
    from lowdown import news as ldnews, database as lddatabase, nntp as ldnntp
    from twisted.news import news, database
    from twisted.protocols import nntp
except ImportError, e:
    goodnews = e


class TestCompatibility(unittest.TestCase):
    def testCompatibility(self):
        self.assertIdentical(news, ldnews)
        self.assertIdentical(database, lddatabase)
        self.assertIdentical(nntp.NNTPServer, ldnntp.NNTPServer)
        
if goodnews:
    TestCompatibility.skip = "Couldn't find third-party LowDown package. %s" % goodnews
