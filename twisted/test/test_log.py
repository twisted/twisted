# Twisted, the Framework of Your Internet
# Copyright (C) 2001-2002 Matthew W. Lefkowitz
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
#

from twisted.trial import unittest

from twisted.python import log
from twisted.python import failure
from twisted.python.compat import *

class LogTest(unittest.TestCase):

    def setUp(self):
        self.catcher = []
        log.addObserver(self.catcher.append)

    def tearDown(self):
        log.removeObserver(self.catcher.append)

    def testObservation(self):
        catcher = self.catcher
        log.msg("test", testShouldCatch=True)
        i = catcher.pop()
        self.assertEquals(i["message"][0], "test")
        self.assertEquals(i["testShouldCatch"], True)
        self.failUnless(i.has_key("time"))
        self.assertEquals(len(catcher), 0)

    def testContext(self):
        catcher = self.catcher
        log.callWithContext({"subsystem": "not the default",
                             "subsubsystem": "a",
                             "other": "c"},
                            log.callWithContext,
                            {"subsubsystem": "b"}, log.msg, "foo", other="d")
        i = catcher.pop()
        self.assertEquals(i['subsubsystem'], 'b')
        self.assertEquals(i['subsystem'], 'not the default')
        self.assertEquals(i['other'], 'd')
        self.assertEquals(i['message'][0], 'foo')

    def testErrors(self):
        for e, ig in [("hello world","hello world"),
                      (KeyError(), KeyError),
                      (failure.Failure(RuntimeError()), RuntimeError)]:
            log.err(e)
            i = self.catcher.pop()
            self.assertEquals(i['isError'], 1)
            log.flushErrors(ig)
