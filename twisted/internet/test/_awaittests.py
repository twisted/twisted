"""
These can only be imported on Python 3.5!
"""

from twisted.internet.defer import Deferred, deferredCoroutine
from twisted.trial.unittest import TestCase
from twisted.internet import reactor


class AwaitTests(TestCase):

    @deferredCoroutine
    async def test_basic(self):
        """
        foooo L{foo}
        """


        d = Deferred()

        reactor.callLater(0, d.callback, "foo")

        res = await d


        self.assertEqual(res, "foo")
