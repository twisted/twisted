"""
These can only be imported on Python 3.5!
"""

from twisted.internet.defer import Deferred, deferredCoroutine
from twisted.trial.unittest import TestCase
from twisted.internet import reactor


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
