
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
from twisted.internet import reactor, defer
from twisted.python import failure

class GenericError(Exception): pass

class DeferredTestCase(unittest.TestCase):

    def setUp(self):
        self.callback_results = None
        self.errback_results = None
        self.callback2_results = None

    def _callback(self, *args, **kw):
        self.callback_results = args, kw
        return args[0]

    def _callback2(self, *args, **kw):
        self.callback2_results = args, kw

    def _errback(self, *args, **kw):
        self.errback_results = args, kw

    def testCallbackWithoutArgs(self):
        deferred = defer.Deferred()
        deferred.addCallback(self._callback)
        deferred.callback("hello")
        self.failUnlessEqual(self.errback_results, None)
        self.failUnlessEqual(self.callback_results, (('hello',), {}))

    def testCallbackWithArgs(self):
        deferred = defer.Deferred()
        deferred.addCallback(self._callback, "world")
        deferred.callback("hello")
        self.failUnlessEqual(self.errback_results, None)
        self.failUnlessEqual(self.callback_results, (('hello', 'world'), {}))

    def testCallbackWithKwArgs(self):
        deferred = defer.Deferred()
        deferred.addCallback(self._callback, world="world")
        deferred.callback("hello")
        self.failUnlessEqual(self.errback_results, None)
        self.failUnlessEqual(self.callback_results,
                             (('hello',), {'world': 'world'}))

    def testTwoCallbacks(self):
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
        def catch(err):
            return None
        dl.addCallbacks(cb, cb)
        defr1.callback("1")
        defr2.addErrback(catch)
        # "catch" is added to eat the GenericError that will be passed on by
        # the DeferredList's callback on defr2. If left unhandled, the
        # Failure object would cause a log.err() warning about "Unhandled
        # error in Deferred". Twisted's pyunit watches for log.err calls and
        # treats them as failures. So "catch" must eat the error to prevent
        # it from flunking the test.
        defr2.errback(GenericError("2"))
        defr3.callback("3")
        self.failUnlessEqual([result[0],
                    #result[1][1] is now a Failure instead of an Exception
                              (result[1][0], str(result[1][1].value)),
                              result[2]],

                             [(defer.SUCCESS, "1"),
                              (defer.FAILURE, "2"),
                              (defer.SUCCESS, "3")])

    def testDeferredListFireOnOneError(self):
        defr1 = defer.Deferred()
        defr2 = defer.Deferred()
        defr3 = defer.Deferred()
        dl = defer.DeferredList([defr1, defr2, defr3], fireOnOneErrback=1)
        result = []
        def catch(err):
            return None
        dl.addErrback(result.append)
        defr1.callback("1")
        defr2.addErrback(catch)
        defr2.errback(GenericError("2"))
        self.failUnlessEqual([str(result[0].value[0].value), str(result[0].value[1])],

                             ["2", "1"])

    def testTimeOut(self):
        d = defer.Deferred()
        d.setTimeout(1.0)
        l = []
        d.addErrback(l.append)
        # Make sure the reactor is shutdown
        d.addBoth(lambda x, r=reactor: r.crash())

        self.assertEquals(l, [])
        reactor.run()
        self.assertEquals(len(l), 1)
        self.assertEquals(l[0].type, defer.TimeoutError)

    def testImmediateSuccess(self):
        l = []
        d = defer.succeed("success")
        d.addCallback(l.append)
        self.assertEquals(l, ["success"])

    def testImmediateFailure(self):
        l = []
        d = defer.fail(GenericError("fail"))
        d.addErrback(l.append)
        self.assertEquals(str(l[0].value), "fail")

    def testPausedFailure(self):
        l = []
        d = defer.fail(GenericError("fail"))
        d.pause()
        d.addErrback(l.append)
        self.assertEquals(l, [])
        d.unpause()
        self.assertEquals(str(l[0].value), "fail")

    def testUnpauseBeforeCallback(self):
        d = defer.Deferred()
        d.pause()
        d.addCallback(self._callback)
        d.unpause()

    def testReturnDeferred(self):
        d = defer.Deferred()
        d2 = defer.Deferred()
        d2.pause()
        d.addCallback(lambda r, d2=d2: d2)
        d.addCallback(self._callback)
        d.callback(1)
        assert self.callback_results is None, "Should not have been called yet."
        d2.callback(2)
        assert self.callback_results is None, "Still should not have been called yet."
        d2.unpause()
        assert self.callback_results[0][0] == 2, "Result should have been from second deferred:%s"% (self.callback_results,)


class DeferredTestCaseII(unittest.TestCase):
    def setUp(self):
        self.callbackRan = 0

    def testDeferredListEmpty(self):
        """Testing empty DeferredList."""
        dl = defer.DeferredList([])
        dl.addCallback(self.cb_empty)

    def cb_empty(self, res):
        self.callbackRan = 1
        self.failUnlessEqual([], res)

    def tearDown(self):
        self.failUnless(self.callbackRan, "Callback was never run.")

testCases = [DeferredTestCase, DeferredTestCaseII]
