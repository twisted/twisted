# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.internet.kqueuereactor}.
"""

from __future__ import division, absolute_import

import errno

from zope.interface import implementer

from twisted.trial.unittest import TestCase
from twisted.python.constants import NamedConstant, Names
from twisted.internet.kqreactor import KQueueReactor, _IKQueueProvider



class KQueueFlags(Names):
    """
    Flags that are used by the KQueue reactor.
    """
    KQ_FILTER_READ = NamedConstant()
    KQ_FILTER_WRITE = NamedConstant()
    KQ_EV_DELETE = NamedConstant()
    KQ_EV_ADD = NamedConstant()
    KQ_EV_EOF = NamedConstant()



def _fakeKEvent(*args, **kwargs):
    """
    Do nothing.
    """
    pass



def makeFakeKQueue(testKQueue, testKEvent):
    """
    Create a fake that implements L{_IKQueueProvider}.
    """
    @implementer(_IKQueueProvider)
    class FakeKQueueProvider(object):
        kqueue = testKQueue
        kevent = testKEvent

        KQ_FILTER_READ = KQueueFlags.KQ_FILTER_READ
        KQ_FILTER_WRITE = KQueueFlags.KQ_FILTER_WRITE
        KQ_EV_DELETE = KQueueFlags.KQ_EV_DELETE
        KQ_EV_ADD = KQueueFlags.KQ_EV_ADD
        KQ_EV_EOF = KQueueFlags.KQ_EV_EOF

    return FakeKQueueProvider



class KQueueTests(TestCase):
    """
    These are tests for L{KQueueReactor}'s implementation, not its real world
    behaviour. For that, look at
    L{twisted.internet.test.reactormixins.ReactorBuilder}.
    """
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
