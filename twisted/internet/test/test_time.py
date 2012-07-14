# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for implementations of L{IReactorTime}.
"""

__metaclass__ = type

from twisted.python.runtime import platform
from twisted.internet.test.reactormixins import ReactorBuilder
from twisted.internet.interfaces import IReactorTime


class TimeTestsBuilder(ReactorBuilder):
    """
    Builder for defining tests relating to L{IReactorTime}.
    """
    requiredInterfaces = (IReactorTime,)

    def test_delayedCallStopsReactor(self):
        """
        The reactor can be stopped by a delayed call.
        """
        reactor = self.buildReactor()
        reactor.callLater(0, reactor.stop)
        reactor.run()



class GlibTimeTestsBuilder(ReactorBuilder):
    """
    Builder for defining tests relating to L{IReactorTime} for reactors based
    off glib.
    """
    requiredInterfaces = (IReactorTime,)

    if platform.isWindows():
        _reactors = ["twisted.internet.gtk2reactor.PortableGtkReactor"]
    else:
        _reactors = ["twisted.internet.glib2reactor.Glib2Reactor",
                     "twisted.internet.gtk2reactor.Gtk2Reactor"]

    def test_timeout_add(self):
        """
        A C{reactor.callLater} call scheduled from a C{gobject.timeout_add}
        call is run on time.
        """
        import gobject
        reactor = self.buildReactor()

        result = []
        def gschedule():
            reactor.callLater(0, callback)
            return 0
        def callback():
            result.append(True)
            reactor.stop()

        reactor.callWhenRunning(gobject.timeout_add, 10, gschedule)
        self.runReactor(reactor, 5)
        self.assertEqual(result, [True])


globals().update(TimeTestsBuilder.makeTestCaseClasses())
globals().update(GlibTimeTestsBuilder.makeTestCaseClasses())
