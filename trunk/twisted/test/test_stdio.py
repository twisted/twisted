# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.internet.stdio}.
"""

import os, sys, itertools

from twisted.trial import unittest
from twisted.python import filepath, log
from twisted.python.runtime import platform
from twisted.internet import error, defer, protocol, stdio, reactor
from twisted.test.test_tcp import ConnectionLostNotifyingProtocol


# A short string which is intended to appear here and nowhere else,
# particularly not in any random garbage output CPython unavoidable
# generates (such as in warning text and so forth).  This is searched
# for in the output from stdio_test_lastwrite.py and if it is found at
# the end, the functionality works.
UNIQUE_LAST_WRITE_STRING = 'xyz123abc Twisted is great!'

skipWindowsNopywin32 = None
if platform.isWindows():
    try:
        import win32process
    except ImportError:
        skipWindowsNopywin32 = ("On windows, spawnProcess is not available "
                                "in the absence of win32process.")


class StandardIOTestProcessProtocol(protocol.ProcessProtocol):
    """
    Test helper for collecting output from a child process and notifying
    something when it exits.

    @ivar onConnection: A L{defer.Deferred} which will be called back with
    C{None} when the connection to the child process is established.

    @ivar onCompletion: A L{defer.Deferred} which will be errbacked with the
    failure associated with the child process exiting when it exits.

    @ivar onDataReceived: A L{defer.Deferred} which will be called back with
    this instance whenever C{childDataReceived} is called, or C{None} to
    suppress these callbacks.

    @ivar data: A C{dict} mapping file descriptors to strings containing all
    bytes received from the child process on each file descriptor.
    """
    onDataReceived = None

    def __init__(self):
        self.onConnection = defer.Deferred()
        self.onCompletion = defer.Deferred()
        self.data = {}


    def connectionMade(self):
        self.onConnection.callback(None)


    def childDataReceived(self, name, bytes):
        """
        Record all bytes received from the child process in the C{data}
        dictionary.  Fire C{onDataReceived} if it is not C{None}.
        """
        self.data[name] = self.data.get(name, '') + bytes
        if self.onDataReceived is not None:
            d, self.onDataReceived = self.onDataReceived, None
            d.callback(self)


    def processEnded(self, reason):
        self.onCompletion.callback(reason)



class StandardInputOutputTestCase(unittest.TestCase):

    skip = skipWindowsNopywin32

    def _spawnProcess(self, proto, sibling, *args, **kw):
        """
        Launch a child Python process and communicate with it using the
        given ProcessProtocol.

        @param proto: A L{ProcessProtocol} instance which will be connected
        to the child process.

        @param sibling: The basename of a file containing the Python program
        to run in the child process.

        @param *args: strings which will be passed to the child process on
        the command line as C{argv[2:]}.

        @param **kw: additional arguments to pass to L{reactor.spawnProcess}.

        @return: The L{IProcessTransport} provider for the spawned process.
        """
        import twisted
        subenv = dict(os.environ)
        subenv['PYTHONPATH'] = os.pathsep.join(
            [os.path.abspath(
                    os.path.dirname(os.path.dirname(twisted.__file__))),
             subenv.get('PYTHONPATH', '')
             ])
        args = [sys.executable,
             filepath.FilePath(__file__).sibling(sibling).path,
             reactor.__class__.__module__] + list(args)
        return reactor.spawnProcess(
            proto,
            sys.executable,
            args,
            env=subenv,
            **kw)


    def _requireFailure(self, d, callback):
        def cb(result):
            self.fail("Process terminated with non-Failure: %r" % (result,))
        def eb(err):
            return callback(err)
        return d.addCallbacks(cb, eb)


    def test_loseConnection(self):
        """
        Verify that a protocol connected to L{StandardIO} can disconnect
        itself using C{transport.loseConnection}.
        """
        errorLogFile = self.mktemp()
        log.msg("Child process logging to " + errorLogFile)
        p = StandardIOTestProcessProtocol()
        d = p.onCompletion
        self._spawnProcess(p, 'stdio_test_loseconn.py', errorLogFile)

        def processEnded(reason):
            # Copy the child's log to ours so it's more visible.
            for line in file(errorLogFile):
                log.msg("Child logged: " + line.rstrip())

            self.failIfIn(1, p.data)
            reason.trap(error.ProcessDone)
        return self._requireFailure(d, processEnded)


    def test_readConnectionLost(self):
        """
        When stdin is closed and the protocol connected to it implements
        L{IHalfCloseableProtocol}, the protocol's C{readConnectionLost} method
        is called.
        """
        errorLogFile = self.mktemp()
        log.msg("Child process logging to " + errorLogFile)
        p = StandardIOTestProcessProtocol()
        p.onDataReceived = defer.Deferred()

        def cbBytes(ignored):
            d = p.onCompletion
            p.transport.closeStdin()
            return d
        p.onDataReceived.addCallback(cbBytes)

        def processEnded(reason):
            reason.trap(error.ProcessDone)
        d = self._requireFailure(p.onDataReceived, processEnded)

        self._spawnProcess(
            p, 'stdio_test_halfclose.py', errorLogFile)
        return d


    def test_lastWriteReceived(self):
        """
        Verify that a write made directly to stdout using L{os.write}
        after StandardIO has finished is reliably received by the
        process reading that stdout.
        """
        p = StandardIOTestProcessProtocol()

        # Note: the OS X bug which prompted the addition of this test
        # is an apparent race condition involving non-blocking PTYs.
        # Delaying the parent process significantly increases the
        # likelihood of the race going the wrong way.  If you need to
        # fiddle with this code at all, uncommenting the next line
        # will likely make your life much easier.  It is commented out
        # because it makes the test quite slow.

        # p.onConnection.addCallback(lambda ign: __import__('time').sleep(5))

        try:
            self._spawnProcess(
                p, 'stdio_test_lastwrite.py', UNIQUE_LAST_WRITE_STRING,
                usePTY=True)
        except ValueError, e:
            # Some platforms don't work with usePTY=True
            raise unittest.SkipTest(str(e))

        def processEnded(reason):
            """
            Asserts that the parent received the bytes written by the child
            immediately after the child starts.
            """
            self.assertTrue(
                p.data[1].endswith(UNIQUE_LAST_WRITE_STRING),
                "Received %r from child, did not find expected bytes." % (
                    p.data,))
            reason.trap(error.ProcessDone)
        return self._requireFailure(p.onCompletion, processEnded)


    def test_hostAndPeer(self):
        """
        Verify that the transport of a protocol connected to L{StandardIO}
        has C{getHost} and C{getPeer} methods.
        """
        p = StandardIOTestProcessProtocol()
        d = p.onCompletion
        self._spawnProcess(p, 'stdio_test_hostpeer.py')

        def processEnded(reason):
            host, peer = p.data[1].splitlines()
            self.failUnless(host)
            self.failUnless(peer)
            reason.trap(error.ProcessDone)
        return self._requireFailure(d, processEnded)


    def test_write(self):
        """
        Verify that the C{write} method of the transport of a protocol
        connected to L{StandardIO} sends bytes to standard out.
        """
        p = StandardIOTestProcessProtocol()
        d = p.onCompletion

        self._spawnProcess(p, 'stdio_test_write.py')

        def processEnded(reason):
            self.assertEqual(p.data[1], 'ok!')
            reason.trap(error.ProcessDone)
        return self._requireFailure(d, processEnded)


    def test_writeSequence(self):
        """
        Verify that the C{writeSequence} method of the transport of a
        protocol connected to L{StandardIO} sends bytes to standard out.
        """
        p = StandardIOTestProcessProtocol()
        d = p.onCompletion

        self._spawnProcess(p, 'stdio_test_writeseq.py')

        def processEnded(reason):
            self.assertEqual(p.data[1], 'ok!')
            reason.trap(error.ProcessDone)
        return self._requireFailure(d, processEnded)


    def _junkPath(self):
        junkPath = self.mktemp()
        junkFile = file(junkPath, 'w')
        for i in xrange(1024):
            junkFile.write(str(i) + '\n')
        junkFile.close()
        return junkPath


    def test_producer(self):
        """
        Verify that the transport of a protocol connected to L{StandardIO}
        is a working L{IProducer} provider.
        """
        p = StandardIOTestProcessProtocol()
        d = p.onCompletion

        written = []
        toWrite = range(100)

        def connectionMade(ign):
            if toWrite:
                written.append(str(toWrite.pop()) + "\n")
                proc.write(written[-1])
                reactor.callLater(0.01, connectionMade, None)

        proc = self._spawnProcess(p, 'stdio_test_producer.py')

        p.onConnection.addCallback(connectionMade)

        def processEnded(reason):
            self.assertEqual(p.data[1], ''.join(written))
            self.failIf(toWrite, "Connection lost with %d writes left to go." % (len(toWrite),))
            reason.trap(error.ProcessDone)
        return self._requireFailure(d, processEnded)


    def test_consumer(self):
        """
        Verify that the transport of a protocol connected to L{StandardIO}
        is a working L{IConsumer} provider.
        """
        p = StandardIOTestProcessProtocol()
        d = p.onCompletion

        junkPath = self._junkPath()

        self._spawnProcess(p, 'stdio_test_consumer.py', junkPath)

        def processEnded(reason):
            self.assertEqual(p.data[1], file(junkPath).read())
            reason.trap(error.ProcessDone)
        return self._requireFailure(d, processEnded)


    def test_normalFileStandardOut(self):
        """
        If L{StandardIO} is created with a file descriptor which refers to a
        normal file (ie, a file from the filesystem), L{StandardIO.write}
        writes bytes to that file.  In particular, it does not immediately
        consider the file closed or call its protocol's C{connectionLost}
        method.
        """
        onConnLost = defer.Deferred()
        proto = ConnectionLostNotifyingProtocol(onConnLost)
        path = filepath.FilePath(self.mktemp())
        self.normal = normal = path.open('w')
        self.addCleanup(normal.close)

        kwargs = dict(stdout=normal.fileno())
        if not platform.isWindows():
            # Make a fake stdin so that StandardIO doesn't mess with the *real*
            # stdin.
            r, w = os.pipe()
            self.addCleanup(os.close, r)
            self.addCleanup(os.close, w)
            kwargs['stdin'] = r
        connection = stdio.StandardIO(proto, **kwargs)

        # The reactor needs to spin a bit before it might have incorrectly
        # decided stdout is closed.  Use this counter to keep track of how
        # much we've let it spin.  If it closes before we expected, this
        # counter will have a value that's too small and we'll know.
        howMany = 5
        count = itertools.count()

        def spin():
            for value in count:
                if value == howMany:
                    connection.loseConnection()
                    return
                connection.write(str(value))
                break
            reactor.callLater(0, spin)
        reactor.callLater(0, spin)

        # Once the connection is lost, make sure the counter is at the
        # appropriate value.
        def cbLost(reason):
            self.assertEqual(count.next(), howMany + 1)
            self.assertEqual(
                path.getContent(),
                ''.join(map(str, range(howMany))))
        onConnLost.addCallback(cbLost)
        return onConnLost

    if platform.isWindows():
        test_normalFileStandardOut.skip = (
            "StandardIO does not accept stdout as an argument to Windows.  "
            "Testing redirection to a file is therefore harder.")
