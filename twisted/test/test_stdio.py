# Copyright (c) 2006-2007 Twisted Matrix Laboratories.
# See LICENSE for details.

import os, sys

from twisted.trial import unittest
from twisted.python import filepath
from twisted.internet import error, defer, protocol, reactor


# A short string which is intended to appear here and nowhere else,
# particularly not in any random garbage output CPython unavoidable
# generates (such as in warning text and so forth).  This is searched
# for in the output from stdio_test_lastwrite.py and if it is found at
# the end, the functionality works.
UNIQUE_LAST_WRITE_STRING = 'xyz123abc Twisted is great!'


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
        p = StandardIOTestProcessProtocol()
        d = p.onCompletion
        self._spawnProcess(p, 'stdio_test_loseconn.py')

        def processEnded(reason):
            self.failIfIn(1, p.data)
            reason.trap(error.ProcessDone)
        return self._requireFailure(d, processEnded)


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
            self.assertEquals(p.data[1], 'ok!')
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
            self.assertEquals(p.data[1], 'ok!')
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
            self.assertEquals(p.data[1], ''.join(written))
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
            self.assertEquals(p.data[1], file(junkPath).read())
            reason.trap(error.ProcessDone)
        return self._requireFailure(d, processEnded)
