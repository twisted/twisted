# Copyright (c) 2008 Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for implementations of L{IReactorProcess}.
"""

__metaclass__ = type

import warnings, sys, signal

from twisted.internet.test.reactormixins import ReactorBuilder
from twisted.python.compat import set
from twisted.python.log import msg, err
from twisted.python.runtime import platform
from twisted.python.filepath import FilePath
from twisted.python.failure import Failure
from twisted.internet.defer import Deferred
from twisted.internet.protocol import ProcessProtocol
from twisted.internet.error import ProcessDone, PotentialZombieWarning
from twisted.internet.error import ProcessTerminated


class ProcessTestsBuilderBase(ReactorBuilder):
    def spawnProcess(self, reactor):
        """
        Call C{reactor.spawnProcess} with some simple arguments.  Do this here
        so that code object referenced by the stack frame has a C{co_filename}
        attribute set to this file so that L{TestCase.assertWarns} can be used.
        """
        reactor.spawnProcess(
            ProcessProtocol(), sys.executable, [sys.executable, "-c", ""],
            usePTY=self.usePTY)


    def test_spawnProcessTooEarlyWarns(self):
        """
        C{reactor.spawnProcess} emits a warning if it is called before
        C{reactor.run}.

        If you can figure out a way to make it safe to run
        C{reactor.spawnProcess} before C{reactor.run}, you may delete the
        warning and this test.
        """
        reactor = self.buildReactor()
        self.assertWarns(
            PotentialZombieWarning,
            PotentialZombieWarning.MESSAGE, __file__,
            self.spawnProcess, reactor)


    def test_callWhenRunningSpawnProcessWarningFree(self):
        """
        L{PotentialZombieWarning} is not emitted when the reactor is run after
        C{reactor.callWhenRunning(reactor.spawnProcess, ...)} has been called.
        """
        events = []
        self.patch(warnings, 'warn', lambda *a, **kw: events.append(a))
        reactor = self.buildReactor()
        reactor.callWhenRunning(self.spawnProcess, reactor)
        reactor.callWhenRunning(reactor.stop)
        self.runReactor(reactor)
        self.assertFalse(events)


    if getattr(signal, 'SIGCHLD', None) is None:
        skipMsg = "No SIGCHLD, no zombies possible."
        test_spawnProcessTooEarlyWarns.skip = skipMsg
        test_callWhenRunningSpawnProcessWarningFree.skip = skipMsg


    def test_processExitedWithSignal(self):
        """
        The C{reason} argument passed to L{IProcessProtocol.processExited} is a
        L{ProcessTerminated} instance if the child process exits with a signal.
        """
        sigName = 'TERM'
        sigNum = getattr(signal, 'SIG' + sigName)
        exited = Deferred()
        source = (
            "import sys\n"
            # Talk so the parent process knows the process is running.  This is
            # necessary because ProcessProtocol.makeConnection may be called
            # before this process is exec'd.  It would be unfortunate if we
            # SIGTERM'd the Twisted process while it was on its way to doing
            # the exec.
            "sys.stdout.write('x')\n"
            "sys.stdout.flush()\n"
            "sys.stdin.read()\n")

        class Exiter(ProcessProtocol):
            def childDataReceived(self, fd, data):
                msg('childDataReceived(%d, %r)' % (fd, data))
                self.transport.signalProcess(sigName)

            def childConnectionLost(self, fd):
                msg('childConnectionLost(%d)' % (fd,))

            def processExited(self, reason):
                msg('processExited(%r)' % (reason,))
                # Protect the Deferred from the failure so that it follows
                # the callback chain.  This doesn't use the errback chain
                # because it wants to make sure reason is a Failure.  An
                # Exception would also make an errback-based test pass, and
                # that would be wrong.
                exited.callback([reason])

            def processEnded(self, reason):
                msg('processEnded(%r)' % (reason,))

        reactor = self.buildReactor()
        reactor.callWhenRunning(
            reactor.spawnProcess, Exiter(), sys.executable,
            [sys.executable, "-c", source], usePTY=self.usePTY)

        def cbExited((failure,)):
            # Trapping implicitly verifies that it's a Failure (rather than
            # an exception) and explicitly makes sure it's the right type.
            failure.trap(ProcessTerminated)
            err = failure.value
            if platform.isWindows():
                # Windows can't really /have/ signals, so it certainly can't
                # report them as the reason for termination.  Maybe there's
                # something better we could be doing here, anyway?  Hard to
                # say.  Anyway, this inconsistency between different platforms
                # is extremely unfortunate and I would remove it if I
                # could. -exarkun
                self.assertIdentical(err.signal, None)
                self.assertEqual(err.exitCode, 1)
            else:
                self.assertEqual(err.signal, sigNum)
                self.assertIdentical(err.exitCode, None)

        exited.addCallback(cbExited)
        exited.addErrback(err)
        exited.addCallback(lambda ign: reactor.stop())

        self.runReactor(reactor)



class ProcessTestsBuilder(ProcessTestsBuilderBase):
    """
    Builder defining tests relating to L{IReactorProcess} for child processes
    which do not have a PTY.
    """
    usePTY = False

    keepStdioOpenProgram = FilePath(__file__).sibling('process_helper.py').path
    if platform.isWindows():
        keepStdioOpenArg = "windows"
    else:
        # Just a value that doesn't equal "windows"
        keepStdioOpenArg = ""

    # Define this test here because PTY-using processes only have stdin and
    # stdout and the test would need to be different for that to work.
    def test_childConnectionLost(self):
        """
        L{IProcessProtocol.childConnectionLost} is called each time a file
        descriptor associated with a child process is closed.
        """
        connected = Deferred()
        lost = {0: Deferred(), 1: Deferred(), 2: Deferred()}

        class Closer(ProcessProtocol):
            def makeConnection(self, transport):
                connected.callback(transport)

            def childConnectionLost(self, childFD):
                lost[childFD].callback(None)

        source = (
            "import os, sys\n"
            "while 1:\n"
            "    line = sys.stdin.readline().strip()\n"
            "    if not line:\n"
            "        break\n"
            "    os.close(int(line))\n")

        reactor = self.buildReactor()
        reactor.callWhenRunning(
            reactor.spawnProcess, Closer(), sys.executable,
            [sys.executable, "-c", source], usePTY=self.usePTY)

        def cbConnected(transport):
            transport.write('2\n')
            return lost[2].addCallback(lambda ign: transport)
        connected.addCallback(cbConnected)

        def lostSecond(transport):
            transport.write('1\n')
            return lost[1].addCallback(lambda ign: transport)
        connected.addCallback(lostSecond)

        def lostFirst(transport):
            transport.write('\n')
        connected.addCallback(lostFirst)
        connected.addErrback(err)

        def cbEnded(ignored):
            reactor.stop()
        connected.addCallback(cbEnded)

        self.runReactor(reactor)


    # This test is here because PTYProcess never delivers childConnectionLost.
    def test_processEnded(self):
        """
        L{IProcessProtocol.processEnded} is called after the child process
        exits and L{IProcessProtocol.childConnectionLost} is called for each of
        its file descriptors.
        """
        ended = Deferred()
        lost = []

        class Ender(ProcessProtocol):
            def childDataReceived(self, fd, data):
                msg('childDataReceived(%d, %r)' % (fd, data))
                self.transport.loseConnection()

            def childConnectionLost(self, childFD):
                msg('childConnectionLost(%d)' % (childFD,))
                lost.append(childFD)

            def processExited(self, reason):
                msg('processExited(%r)' % (reason,))

            def processEnded(self, reason):
                msg('processEnded(%r)' % (reason,))
                ended.callback([reason])

        reactor = self.buildReactor()
        reactor.callWhenRunning(
            reactor.spawnProcess, Ender(), sys.executable,
            [sys.executable, self.keepStdioOpenProgram, "child",
             self.keepStdioOpenArg],
            usePTY=self.usePTY)

        def cbEnded((failure,)):
            failure.trap(ProcessDone)
            self.assertEqual(set(lost), set([0, 1, 2]))
        ended.addCallback(cbEnded)

        ended.addErrback(err)
        ended.addCallback(lambda ign: reactor.stop())

        self.runReactor(reactor)


    # This test is here because PTYProcess.loseConnection does not actually
    # close the file descriptors to the child process.  This test needs to be
    # written fairly differently for PTYProcess.
    def test_processExited(self):
        """
        L{IProcessProtocol.processExited} is called when the child process
        exits, even if file descriptors associated with the child are still
        open.
        """
        exited = Deferred()
        allLost = Deferred()
        lost = []

        class Waiter(ProcessProtocol):
            def childDataReceived(self, fd, data):
                msg('childDataReceived(%d, %r)' % (fd, data))

            def childConnectionLost(self, childFD):
                msg('childConnectionLost(%d)' % (childFD,))
                lost.append(childFD)
                if len(lost) == 3:
                    allLost.callback(None)

            def processExited(self, reason):
                msg('processExited(%r)' % (reason,))
                # See test_processExitedWithSignal
                exited.callback([reason])
                self.transport.loseConnection()

        reactor = self.buildReactor()
        reactor.callWhenRunning(
            reactor.spawnProcess, Waiter(), sys.executable,
            [sys.executable, self.keepStdioOpenProgram, "child",
             self.keepStdioOpenArg],
            usePTY=self.usePTY)

        def cbExited((failure,)):
            failure.trap(ProcessDone)
            msg('cbExited; lost = %s' % (lost,))
            self.assertEqual(lost, [])
            return allLost
        exited.addCallback(cbExited)

        def cbAllLost(ignored):
            self.assertEqual(set(lost), set([0, 1, 2]))
        exited.addCallback(cbAllLost)

        exited.addErrback(err)
        exited.addCallback(lambda ign: reactor.stop())

        self.runReactor(reactor)


globals().update(ProcessTestsBuilder.makeTestCaseClasses())



class PTYProcessTestsBuilder(ProcessTestsBuilderBase):
    """
    Builder defining tests relating to L{IReactorProcess} for child processes
    which have a PTY.
    """
    usePTY = True

    if platform.isWindows():
        skip = "PTYs are not supported on Windows."
    elif platform.isMacOSX():
        skippedReactors = {
            "twisted.internet.pollreactor.PollReactor":
                "OS X's poll() does not support PTYs"}


globals().update(PTYProcessTestsBuilder.makeTestCaseClasses())
