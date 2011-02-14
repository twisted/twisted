# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for implementations of L{IReactorWin32Events}.
"""

try:
    import win32event
except ImportError:
    win32event = None

from zope.interface.verify import verifyObject

from twisted.internet.interfaces import IReactorWin32Events
from twisted.internet.test.reactormixins import ReactorBuilder


class Win32EventsTestsBuilder(ReactorBuilder):
    """
    Builder defining tests relating to L{IReactorWin32Events}.
    """
    requiredInterfaces = [IReactorWin32Events]

    def test_interface(self):
        """
        An instance of the reactor has all of the methods defined on
        L{IReactorWin32Events}.
        """
        reactor = self.buildReactor()
        verifyObject(IReactorWin32Events, reactor)


    def test_addEvent(self):
        """
        When an event which has been added to the reactor is set, the action
        associated with the event is invoked.
        """
        reactor = self.buildReactor()
        event = win32event.CreateEvent(None, False, False, None)
        class Listener(object):
            success = False

            def logPrefix(self):
                return 'Listener'

            def occurred(self):
                self.success = True
                reactor.stop()

        listener = Listener()
        reactor.addEvent(event, listener, 'occurred')
        reactor.callWhenRunning(win32event.SetEvent, event)
        self.runReactor(reactor)
        self.assertTrue(listener.success)


globals().update(Win32EventsTestsBuilder.makeTestCaseClasses())
