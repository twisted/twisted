
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
Test cases for defer module.
"""

from pyunit import unittest
from twisted.python import defer
from twisted.internet import reactor


class DeferredTestCase(unittest.TestCase):

    def _callback(self, *args, **kw):
        self.callback_results = args, kw
        return args[0]

    def _callback2(self, *args, **kw):
        self.callback2_results = args, kw

    def _errback(self, *args, **kw):
        self.errback_results = args, kw

    def testCallbackWithoutArgs(self):
        self.callback_results = None
        self.errback_results = None
        deferred = defer.Deferred()
        deferred.addCallback(self._callback)
        deferred.callback("hello")
        self.failUnlessEqual(self.errback_results, None)
        self.failUnlessEqual(self.callback_results, (('hello',), {}))

    def testCallbackWithArgs(self):
        self.callback_results = None
        self.errback_results = None
        deferred = defer.Deferred()
        deferred.addCallback(self._callback, "world")
        deferred.callback("hello")
        self.failUnlessEqual(self.errback_results, None)
        self.failUnlessEqual(self.callback_results, (('hello', 'world'), {}))

    def testCallbackWithKwArgs(self):
        self.callback_results = None
        self.errback_results = None
        deferred = defer.Deferred()
        deferred.addCallback(self._callback, world="world")
        deferred.callback("hello")
        self.failUnlessEqual(self.errback_results, None)
        self.failUnlessEqual(self.callback_results,
                             (('hello',), {'world': 'world'}))

    def testTwoCallbacks(self):
        self.callback_results = None
        self.callback2_results = None
        self.errback_results = None
        deferred = defer.Deferred()
        deferred.addCallback(self._callback)
        deferred.addCallback(self._callback2)
        deferred.callback("hello")
        self.failUnlessEqual(self.errback_results, None)
        self.failUnlessEqual(self.callback_results,
                             (('hello',), {}))
        self.failUnlessEqual(self.callback2_results,
                             (('hello',), {}))

    def testDeferredList(self):
        defr1 = defer.Deferred()
        defr2 = defer.Deferred()
        defr3 = defer.Deferred()
        dl = defer.DeferredList([defr1, defr2, defr3])
        result = []
        def cb(resultList, result=result):
            result.extend(resultList)
        dl.addCallbacks(cb, cb)
        defr1.armAndCallback(1)
        defr2.armAndErrback(2)
        defr3.armAndCallback(3)
        self.failUnlessEqual(result, [(defer.SUCCESS, 1),
                                      (defer.FAILURE, 2),
                                      (defer.SUCCESS, 3)])

    def testImmediateSuccess(self):
        l = []
        d = defer.succeed("success")
        d.addCallback(l.append)
        self.assertEquals(l, ["success"])

    def testImmediateFailure(self):
        l = []
        d = defer.fail("fail")
        d.addErrback(l.append)
        self.assertEquals(l, [])
        reactor.iterate()
        self.assertEquals(l, ["fail"])

    def testImmediateFailure(self):
        l = []
        d = defer.fail("fail")
        d.addErrback(l.append)
        self.assertEquals(l, ["fail"])

    def testPausedFailure(self):
        l = []
        d = defer.fail("fail")
        d.pause()
        d.addErrback(l.append)
        self.assertEquals(l, [])
        d.unpause()
        self.assertEquals(l, ["fail"])

    def testUnpauseBeforeCallback(self):
        d = defer.Deferred()
        d.pause()
        d.addCallback(self._callback)
        d.unpause()



testCases = [DeferredTestCase]
