
import errno, socket

from twisted.internet.interfaces import IReactorSocket
from twisted.internet.error import (
    UnsupportedAddressFamily, UnsupportedSocketType)
from twisted.internet.protocol import ServerFactory
from twisted.internet.test.reactormixins import ReactorBuilder

class AdoptStreamPortErrorsTestsBuilder(ReactorBuilder):
    """
    Builder for testing L{IReactorSocket} implementations.

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


globals().update(AdoptStreamPortErrorsTestsBuilder.makeTestCaseClasses())
