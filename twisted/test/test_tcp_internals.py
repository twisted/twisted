# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Whitebox tests for TCP APIs.
"""

import errno, socket, os

try:
    import resource
except ImportError:
    resource = None

from twisted.trial.unittest import TestCase
from twisted.python import log
from twisted.internet.tcp import ECONNABORTED, ENOMEM, ENFILE, EMFILE, ENOBUFS, EINPROGRESS, Port
from twisted.internet.protocol import ServerFactory
from twisted.python.runtime import platform
from twisted.internet import reactor, interfaces
from twisted.internet.task import Clock



class PlatformAssumptionsTestCase(TestCase):
    """
    Test assumptions about platform behaviors.
    """
    socketLimit = 8192

    def setUp(self):
        self.openSockets = []
        if resource is not None:
            # On some buggy platforms we might leak FDs, and the test will
            # fail creating the initial two sockets we *do* want to
            # succeed. So, we make the soft limit the current number of fds
            # plus two more (for the two sockets we want to succeed). If we've
            # leaked too many fds for that to work, there's nothing we can
            # do.
            from twisted.internet.process import _listOpenFDs
            newLimit = len(_listOpenFDs()) + 2
            self.originalFileLimit = resource.getrlimit(resource.RLIMIT_NOFILE)
            resource.setrlimit(resource.RLIMIT_NOFILE, (newLimit, self.originalFileLimit[1]))
            self.socketLimit = newLimit + 100


    def tearDown(self):
        while self.openSockets:
            self.openSockets.pop().close()
        if resource is not None:
            # OS X implicitly lowers the hard limit in the setrlimit call
            # above.  Retrieve the new hard limit to pass in to this
            # setrlimit call, so that it doesn't give us a permission denied
            # error.
            currentHardLimit = resource.getrlimit(resource.RLIMIT_NOFILE)[1]
            newSoftLimit = min(self.originalFileLimit[0], currentHardLimit)
            resource.setrlimit(resource.RLIMIT_NOFILE, (newSoftLimit, currentHardLimit))


    def socket(self):
        """
        Create and return a new socket object, also tracking it so it can be
        closed in the test tear down.
        """
        s = socket.socket()
        self.openSockets.append(s)
        return s


    def test_acceptOutOfFiles(self):
        """
        Test that the platform accept(2) call fails with either L{EMFILE} or
        L{ENOBUFS} when there are too many file descriptors open.
        """
        # Make a server to which to connect
        port = self.socket()
        port.bind(('127.0.0.1', 0))
        serverPortNumber = port.getsockname()[1]
        port.listen(5)

        # Make a client to use to connect to the server
        client = self.socket()
        client.setblocking(False)

        # Use up all the rest of the file descriptors.
        for i in xrange(self.socketLimit):
            try:
                self.socket()
            except socket.error, e:
                if e.args[0] in (EMFILE, ENOBUFS):
                    # The desired state has been achieved.
                    break
                else:
                    # Some unexpected error occurred.
                    raise
        else:
            self.fail("Could provoke neither EMFILE nor ENOBUFS from platform.")

        # Non-blocking connect is supposed to fail, but this is not true
        # everywhere (e.g. freeBSD)
        self.assertIn(client.connect_ex(('127.0.0.1', serverPortNumber)),
                      (0, EINPROGRESS))

        # Make sure that the accept call fails in the way we expect.
        exc = self.assertRaises(socket.error, port.accept)
        self.assertIn(exc.args[0], (EMFILE, ENOBUFS))
    if platform.getType() == "win32":
        test_acceptOutOfFiles.skip = (
            "Windows requires an unacceptably large amount of resources to "
            "provoke this behavior in the naive manner.")



class ResourceExhaustionTestCase(TestCase):
    """
    Tests for resource exhaustion failure conditions.
    """

    class FakeSocket(object):
        """
        Pretend to be a socket in an overloaded system.
        """
        def __init__(self, socketErrorNumber):
            self.socketErrorNumber = socketErrorNumber

        def accept(self):
            raise socket.error(
                self.socketErrorNumber, os.strerror(self.socketErrorNumber))


    class FakeReactor(Clock):
        """
        A reactor that supports time, and adding and removing readers.
        """
        def __init__(self):
            Clock.__init__(self)
            self.readers = set()

        def addReader(self, reader):
            self.readers.add(reader)

        def removeReader(self, reader):
            if reader in self.readers:
                self.readers.remove(reader)

        def removeWriter(self, writer):
            pass


    def setUp(self):
        self.reactor = self.FakeReactor()
        self.ports = []
        self.messages = []
        log.addObserver(self.messages.append)


    def tearDown(self):
        log.removeObserver(self.messages.append)


    def port(self, portNumber, factory, interface):
        """
        Create, start, and return a new L{Port}, also tracking it so it can
        be stopped in the test tear down.
        """
        p = Port(portNumber, factory, interface=interface, reactor=self.reactor)
        p.startListening()
        return p


    def _acceptFailureTest(self, socketErrorNumber, shouldStopListening=True):
        """
        Test behavior in the face of an exception from C{accept(2)}.

        On any exception which indicates the platform is unable or unwilling
        to allocate further resources to us, the existing port should remain
        listening, a message should be logged, and the exception should not
        propagate outward from doRead.

        @param socketErrorNumber: The errno to simulate from accept.
        """
        factory = ServerFactory()
        port = self.port(0, factory, interface='127.0.0.1')
        def cleanup():
            port.stopListening()
            self.reactor.advance(0.01)
        self.addCleanup(cleanup)
        self.assertIn(port, self.reactor.readers)

        # When we fail to accept(), we log an error message but do not throw
        # an exception:
        originalSocket = port.socket
        try:
            port.socket = self.FakeSocket(socketErrorNumber)

            port.doRead()

            expectedFormat = "Could not accept new connection (%s)"
            expectedErrorCode = errno.errorcode[socketErrorNumber]
            expectedMessage = expectedFormat % (expectedErrorCode,)
            for msg in self.messages:
                if msg.get('message') == (expectedMessage,):
                    break
            else:
                self.fail("Log event for failed accept not found in "
                          "%r" % (self.messages,))
        finally:
            port.socket = originalSocket

        if shouldStopListening:
            # Additionally, in order to prevent busy looping in the reactor as
            # we try and fail to accept(), we remove the port from the reactor
            # for a second, at which point hopefully the resource will have
            # freed up:
            self.assertNotIn(port, self.reactor.readers)
            self.reactor.advance(1)
            self.assertIn(port, self.reactor.readers)
        else:
            self.assertIn(port, self.reactor.readers)


    def test_tooManyFilesFromAccept(self):
        """
        C{accept(2)} can fail with C{EMFILE} when there are too many open file
        descriptors in the process.  Test that this doesn't negatively impact
        any other existing connections, and that the port temporarily stops
        listening to prevent busy looping in the event loop.

        C{EMFILE} mainly occurs on Linux when the open file rlimit is
        encountered.
        """
        return self._acceptFailureTest(EMFILE)


    def test_noBufferSpaceFromAccept(self):
        """
        Similar to L{test_tooManyFilesFromAccept}, but test the case where
        C{accept(2)} fails with C{ENOBUFS}.

        This mainly occurs on Windows and FreeBSD, but may be possible on
        Linux and other platforms as well.
        """
        return self._acceptFailureTest(ENOBUFS)


    def test_connectionAbortedFromAccept(self):
        """
        Similar to L{test_tooManyFilesFromAccept}, but test the case where
        C{accept(2)} fails with C{ECONNABORTED}.

        It is not clear whether this is actually possible for TCP connections
        on modern versions of Linux. If it is, the port should not stop
        listening when it occurs because it is not a resource issue.
        """
        return self._acceptFailureTest(ECONNABORTED, False)


    def test_noFilesFromAccept(self):
        """
        Similar to L{test_tooManyFilesFromAccept}, but test the case where
        C{accept(2)} fails with C{ENFILE}.

        This can occur on Linux when the system has exhausted (!) its supply
        of inodes.
        """
        return self._acceptFailureTest(ENFILE)
    if platform.getType() == 'win32':
        test_noFilesFromAccept.skip = "Windows accept(2) cannot generate ENFILE"


    def test_noMemoryFromAccept(self):
        """
        Similar to L{test_tooManyFilesFromAccept}, but test the case where
        C{accept(2)} fails with C{ENOMEM}.

        On Linux at least, this can sensibly occur, even in a Python program
        (which eats memory like no ones business), when memory has become
        fragmented or low memory has been filled (d_alloc calls
        kmem_cache_alloc calls kmalloc - kmalloc only allocates out of low
        memory).
        """
        return self._acceptFailureTest(ENOMEM)
    if platform.getType() == 'win32':
        test_noMemoryFromAccept.skip = "Windows accept(2) cannot generate ENOMEM"


    def test_noRestartReadingIfPortStopped(self):
        """
        If the port has temporarily stopped reading as a result of resource
        exhaustion, it should not restart reading if the port was closed in
        the interim.
        """
        factory = ServerFactory()
        port = self.port(0, factory, interface='127.0.0.1')
        self.assertIn(port, self.reactor.readers)

        # When we fail to accept(), we log an error message but do not throw
        # an exception:
        originalSocket = port.socket
        try:
            port.socket = self.FakeSocket(EMFILE)
            port.doRead()
        finally:
            port.socket = originalSocket

        self.assertNotIn(port, self.reactor.readers)
        # Stop listening; after a second, the port should not be re-added to
        # readers:
        port.stopListening()
        self.reactor.advance(1)
        self.assertNotIn(port, self.reactor.readers)

if not interfaces.IReactorFDSet.providedBy(reactor):
    skipMsg = 'This test only applies to reactors that implement IReactorFDset'
    PlatformAssumptionsTestCase.skip = skipMsg
    ResourceExhaustionTestCase.skip = skipMsg

