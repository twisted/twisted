
import errno, socket

from twisted.python.log import err
from twisted.internet.interfaces import IReactorSocket
from twisted.internet.error import UnsupportedAddressFamily
from twisted.internet.protocol import ServerFactory
from twisted.internet.test.reactormixins import (
    ReactorBuilder, needsRunningReactor)


class AdoptStreamPortErrorsTestsBuilder(ReactorBuilder):
    """
    Builder for testing L{IReactorSocket.adoptStreamPort} implementations.

    Generally only tests for failure cases are found here.  Success cases for
    this interface are tested elsewhere.  For example, the success case for
    I{AF_INET} is in L{twisted.internet.test.test_tcp}, since that case should
    behave exactly the same as L{IReactorTCP.listenTCP}.
    """
    requiredInterfaces = [IReactorSocket]

    def test_invalidDescriptor(self):
        """
        An implementation of L{IReactorSocket.adoptStreamPort} raises
        L{socket.error} if passed an integer which is not associated with a
        socket.
        """
        reactor = self.buildReactor()

        probe = socket.socket()
        fileno = probe.fileno()
        probe.close()

        exc = self.assertRaises(
            socket.error,
            reactor.adoptStreamPort, fileno, socket.AF_INET, ServerFactory())
        self.assertEqual(exc.args[0], errno.EBADF)


    def test_invalidAddressFamily(self):
        """
        An implementation of L{IReactorSocket.adoptStreamPort} raises
        L{UnsupportedAddressFamily} if passed an address family it does not
        support.
        """
        reactor = self.buildReactor()

        port = socket.socket()
        port.listen(1)
        self.addCleanup(port.close)

        arbitrary = 2 ** 16 + 7

        self.assertRaises(
            UnsupportedAddressFamily,
            reactor.adoptStreamPort, port.fileno(), arbitrary, ServerFactory())


    def test_stopOnlyCloses(self):
        """
        When the L{IListeningPort} returned by L{IReactorSocket.adoptStreamPort}
        is stopped using C{stopListening}, the underlying socket is closed but
        not shutdown.  This allows another process which still has a reference
        to it to continue accepting connections over it.
        """
        reactor = self.buildReactor()

        portSocket = socket.socket()
        self.addCleanup(portSocket.close)

        portSocket.listen(1)
        portSocket.setblocking(False)

        # The file descriptor is duplicated by adoptStreamPort
        port = reactor.adoptStreamPort(
            portSocket.fileno(), portSocket.family, ServerFactory())
        d = port.stopListening()
        def stopped(ignored):
            # Should still be possible to accept a connection on portSocket.  If
            # it was shutdown, the exception would be EINVAL instead.
            exc = self.assertRaises(socket.error, portSocket.accept)
            self.assertEqual(exc.args[0], errno.EAGAIN)
        d.addCallback(stopped)
        d.addErrback(err, "Failed to accept on original port.")

        needsRunningReactor(
            reactor,
            lambda: d.addCallback(lambda ignored: reactor.stop()))

        reactor.run()



class AdoptStreamConnectionErrorsTestsBuilder(ReactorBuilder):
    """
    Builder for testing L{IReactorSocket.adoptStreamConnection}
    implementations.

    Generally only tests for failure cases are found here.  Success cases for
    this interface are tested elsewhere.  For example, the success case for
    I{AF_INET} is in L{twisted.internet.test.test_tcp}, since that case should
    behave exactly the same as L{IReactorTCP.listenTCP}.
    """
    requiredInterfaces = [IReactorSocket]

    def test_invalidAddressFamily(self):
        """
        An implementation of L{IReactorSocket.adoptStreamConnection} raises
        L{UnsupportedAddressFamily} if passed an address family it does not
        support.
        """
        reactor = self.buildReactor()

        connection = socket.socket()
        self.addCleanup(connection.close)

        arbitrary = 2 ** 16 + 7

        self.assertRaises(
            UnsupportedAddressFamily,
            reactor.adoptStreamConnection, connection.fileno(), arbitrary,
            ServerFactory())



globals().update(AdoptStreamPortErrorsTestsBuilder.makeTestCaseClasses())
globals().update(AdoptStreamConnectionErrorsTestsBuilder.makeTestCaseClasses())
