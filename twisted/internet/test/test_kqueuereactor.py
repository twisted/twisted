# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.internet.kqueuereactor}.
"""

from __future__ import division, absolute_import

import errno

from zope.interface import implementer

from twisted.trial.unittest import TestCase

try:
    from twisted.internet.kqreactor import KQueueReactor, _IKQueue
    kqueueSkip = None
except ImportError:
    kqueueSkip = "KQueue not available."


def _fakeKEvent(*args, **kwargs):
    """
    Do nothing.
    """
    pass



def makeFakeKQueue(testKQueue, testKEvent):
    """
    Create a fake that implements L{_IKQueue}.
    """
    @implementer(_IKQueue)
    class FakeKQueue(object):
        kqueue = testKQueue
        kevent = testKEvent

    return FakeKQueue()



class KQueueTests(TestCase):
    """
    These are tests for L{KQueueReactor}'s implementation, not its real world
    behaviour. For that, look at
    L{twisted.internet.test.reactormixins.ReactorBuilder}.
    """
    skip = kqueueSkip

    def test_EINTR(self):
        """
        L{KQueueReactor} should handle L{errno.EINTR} by returning.
        """
        class FakeKQueue(object):
            """
            A fake KQueue that raises L{errno.EINTR} when C{control} is called.
            """
            def control(self, *args, **kwargs):
                raise OSError(errno.EINTR, "Interrupted")

        reactor = KQueueReactor(makeFakeKQueue(FakeKQueue, _fakeKEvent))
        result = reactor.doKEvent(0)

        self.assertEqual(result, None)
