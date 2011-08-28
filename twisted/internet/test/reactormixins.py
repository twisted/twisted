# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for implementations of L{IReactorTime}.
"""

__metaclass__ = type

import signal

from twisted.internet.defer import TimeoutError
from twisted.trial.unittest import TestCase, SkipTest
from twisted.python.runtime import platform
from twisted.python.reflect import namedAny, fullyQualifiedName
from twisted.python import log
from twisted.python.failure import Failure

# Access private APIs.
if platform.isWindows():
    process = None
else:
    from twisted.internet import process


class ReactorBuilder:
    """
    L{TestCase} mixin which provides a reactor-creation API.  This mixin
    defines C{setUp} and C{tearDown}, so mix it in before L{TestCase} or call
    its methods from the overridden ones in the subclass.

    @cvar skippedReactors: A dict mapping FQPN strings of reactors for
        which the tests defined by this class will be skipped to strings
        giving the skip message.
    @cvar requiredInterfaces: A C{list} of interfaces which the reactor must
        provide or these tests will be skipped.  The default, C{None}, means
        that no interfaces are required.
    @ivar reactorFactory: A no-argument callable which returns the reactor to
        use for testing.
    @ivar originalHandler: The SIGCHLD handler which was installed when setUp
        ran and which will be re-installed when tearDown runs.
    @ivar _reactors: A list of FQPN strings giving the reactors for which
        TestCases will be created.
    """

    _reactors = [
        # Select works everywhere
        "twisted.internet.selectreactor.SelectReactor",
        ]

    if platform.isWindows():
        # PortableGtkReactor is only really interesting on Windows,
        # but not really Windows specific; if you want you can
        # temporarily move this up to the all-platforms list to test
        # it on other platforms.  It's not there in general because
        # it's not _really_ worth it to support on other platforms,
        # since no one really wants to use it on other platforms.
        _reactors.extend([
                "twisted.internet.gtk2reactor.PortableGtkReactor",
                "twisted.internet.win32eventreactor.Win32Reactor",
                "twisted.internet.iocpreactor.reactor.IOCPReactor"])
    else:
        _reactors.extend([
                "twisted.internet.glib2reactor.Glib2Reactor",
                "twisted.internet.gtk2reactor.Gtk2Reactor",
                "twisted.internet.kqreactor.KQueueReactor"])
        if platform.isMacOSX():
            _reactors.append("twisted.internet.cfreactor.CFReactor")
        else:
            _reactors.extend([
                    "twisted.internet.pollreactor.PollReactor",
                    "twisted.internet.epollreactor.EPollReactor"])

    reactorFactory = None
    originalHandler = None
    requiredInterfaces = None
    skippedReactors = {}

    def setUp(self):
        """
        Clear the SIGCHLD handler, if there is one, to ensure an environment
        like the one which exists prior to a call to L{reactor.run}.
        """
        if not platform.isWindows():
            self.originalHandler = signal.signal(signal.SIGCHLD, signal.SIG_DFL)


    def tearDown(self):
        """
        Restore the original SIGCHLD handler and reap processes as long as
        there seem to be any remaining.
        """
        if self.originalHandler is not None:
            signal.signal(signal.SIGCHLD, self.originalHandler)
        if process is not None:
            while process.reapProcessHandlers:
                log.msg(
                    "ReactorBuilder.tearDown reaping some processes %r" % (
                        process.reapProcessHandlers,))
                process.reapAllProcesses()


    def unbuildReactor(self, reactor):
        """
        Clean up any resources which may have been allocated for the given
        reactor by its creation or by a test which used it.
        """
        # Chris says:
        #
        # XXX These explicit calls to clean up the waker (and any other
        # internal readers) should become obsolete when bug #3063 is
        # fixed. -radix, 2008-02-29. Fortunately it should probably cause an
        # error when bug #3063 is fixed, so it should be removed in the same
        # branch that fixes it.
        #
        # -exarkun
        reactor._uninstallHandler()
        if getattr(reactor, '_internalReaders', None) is not None:
            for reader in reactor._internalReaders:
                reactor.removeReader(reader)
                reader.connectionLost(None)
            reactor._internalReaders.clear()

        # Here's an extra thing unrelated to wakers but necessary for
        # cleaning up after the reactors we make.  -exarkun
        reactor.disconnectAll()

        # It would also be bad if any timed calls left over were allowed to
        # run.
        calls = reactor.getDelayedCalls()
        for c in calls:
            c.cancel()


    def buildReactor(self):
        """
        Create and return a reactor using C{self.reactorFactory}.
        """
        try:
            from twisted.internet.cfreactor import CFReactor
            from twisted.internet import reactor as globalReactor
        except ImportError:
            pass
        else:
            if (isinstance(globalReactor, CFReactor)
                and self.reactorFactory is CFReactor):
                raise SkipTest(
                    "CFReactor uses APIs which manipulate global state, "
                    "so it's not safe to run its own reactor-builder tests "
                    "under itself")
        try:
            reactor = self.reactorFactory()
        except:
            # Unfortunately, not all errors which result in a reactor
            # being unusable are detectable without actually
            # instantiating the reactor.  So we catch some more here
            # and skip the test if necessary.  We also log it to aid
            # with debugging, but flush the logged error so the test
            # doesn't fail.
            log.err(None, "Failed to install reactor")
            self.flushLoggedErrors()
            raise SkipTest(Failure().getErrorMessage())
        else:
            if self.requiredInterfaces is not None:
                missing = filter(
                     lambda required: not required.providedBy(reactor),
                     self.requiredInterfaces)
                if missing:
                    self.unbuildReactor(reactor)
                    raise SkipTest("%s does not provide %s" % (
                        fullyQualifiedName(reactor.__class__),
                        ",".join([fullyQualifiedName(x) for x in missing])))
        self.addCleanup(self.unbuildReactor, reactor)
        return reactor


    def runReactor(self, reactor, timeout=None):
        """
        Run the reactor for at most the given amount of time.

        @param reactor: The reactor to run.

        @type timeout: C{int} or C{float}
        @param timeout: The maximum amount of time, specified in seconds, to
            allow the reactor to run.  If the reactor is still running after
            this much time has elapsed, it will be stopped and an exception
            raised.  If C{None}, the default test method timeout imposed by
            Trial will be used.  This depends on the L{IReactorTime}
            implementation of C{reactor} for correct operation.

        @raise TimeoutError: If the reactor is still running after C{timeout}
            seconds.
        """
        if timeout is None:
            timeout = self.getTimeout()

        timedOut = []
        def stop():
            timedOut.append(None)
            reactor.stop()

        reactor.callLater(timeout, stop)
        reactor.run()
        if timedOut:
            raise TimeoutError(
                "reactor still running after %s seconds" % (timeout,))


    def makeTestCaseClasses(cls):
        """
        Create a L{TestCase} subclass which mixes in C{cls} for each known
        reactor and return a dict mapping their names to them.
        """
        classes = {}
        for reactor in cls._reactors:
            shortReactorName = reactor.split(".")[-1]
            name = (cls.__name__ + "." + shortReactorName).replace(".", "_")
            class testcase(cls, TestCase):
                __module__ = cls.__module__
                if reactor in cls.skippedReactors:
                    skip = cls.skippedReactors[reactor]
                try:
                    reactorFactory = namedAny(reactor)
                except:
                    skip = Failure().getErrorMessage()
            testcase.__name__ = name
            classes[testcase.__name__] = testcase
        return classes
    makeTestCaseClasses = classmethod(makeTestCaseClasses)


__all__ = ['ReactorBuilder']
