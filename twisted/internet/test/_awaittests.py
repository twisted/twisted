# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for C{await} support in Deferreds.

These tests can only work and be imported on Python 3.5!
"""

from twisted.internet.defer import Deferred, deferredCoroutine, sleep
from twisted.trial.unittest import TestCase
from twisted.test.proto_helpers import Clock


class AwaitTests(TestCase):

    def test_basic(self):
        """
        L{deferredCoroutine} allows a function to C{await} on a L{Deferred}.
        """
        @deferredCoroutine
        async def run():
            d = Deferred()
            d.callback("foo")
            res = await d
            return res

        d = run()
        res = self.successResultOf(d)
        self.assertEqual(res, "foo")


    def test_exception(self):
        """
        An exception in a function wrapped with L{deferredCoroutine} will cause
        the returned L{Deferred} to fire with a failure.
        """
        @deferredCoroutine
        async def run():
            d = Deferred()
            d.callback("foo")
            res = await d
            raise ValueError("Oh no!")

        d = run()
        res = self.failureResultOf(d)
        self.assertEqual(type(res.value), ValueError)
        self.assertEqual(res.value.args, ("Oh no!",))


    def test_twoDeep(self):
        """
        An exception in a function wrapped with L{deferredCoroutine} will cause
        the returned L{Deferred} to fire with a failure.
        """
        reactor = Clock()
        sections = []

        @deferredCoroutine
        async def runone():
            sections.append(2)
            await sleep(1, reactor=reactor)
            sections.append(3)
            return "Yay!"


        @deferredCoroutine
        async def run():
            sections.append(1)
            result = await runone()
            sections.append(4)
            await sleep(1, reactor=reactor)
            sections.append(5)
            return result

        d = run()

        reactor.advance(0.9)
        self.assertEqual(sections, [1, 2])

        reactor.advance(0.1)
        self.assertEqual(sections, [1, 2, 3, 4])

        reactor.advance(0.9)
        self.assertEqual(sections, [1, 2, 3, 4])

        reactor.advance(0.1)
        self.assertEqual(sections, [1, 2, 3, 4, 5])

        res = self.successResultOf(d)
        self.assertEqual(res, "Yay!")
