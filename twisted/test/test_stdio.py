# Copyright (c) 2006 Twisted Matrix Laboratories.
# See LICENSE for details.

import os, sys

from twisted.trial import unittest
from twisted.python import filepath
from twisted.internet import error, defer, protocol, reactor


class StandardIOTestProcessProtocol(protocol.ProcessProtocol):
    def __init__(self):
        self.onConnection = defer.Deferred()
        self.onCompletion = defer.Deferred()


    def connectionMade(self):
        self.data = {}
        self.onConnection.callback(None)


    def childDataReceived(self, name, bytes):
        self.data[name] = self.data.get(name, '') + bytes


    def processEnded(self, reason):
        for k in self.data.keys():
            self.data[k] = ''.join(self.data[k])
        self.onCompletion.callback(reason)



class StandardInputOutputTestCase(unittest.TestCase):
    def _spawnProcess(self, proto, sibling, *args):
        import twisted
        subenv = dict(os.environ)
        subenv['PYTHONPATH'] = os.pathsep.join(
            [os.path.abspath(
                    os.path.dirname(os.path.dirname(twisted.__file__))),
             subenv.get('PYTHONPATH', '')
             ])
        return reactor.spawnProcess(
            proto,
            sys.executable,
            [sys.executable,
             filepath.FilePath(__file__).sibling(sibling).path,
             reactor.__class__.__module__] + list(args),
            env=subenv,
            )


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
