# Copyright (c) 2006-2010 Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Whitebox tests for UDP APIs.
"""

import errno, socket, os

from twisted.trial.unittest import TestCase

from twisted.internet.udp import EWOULDBLOCK, EAGAIN, Port
from twisted.internet.protocol import DatagramProtocol
from twisted.python.runtime import platform
from twisted.internet import reactor, interfaces


class PlatformAssumptionsTestCase(TestCase):
    """
    Test assumptions about platform behaviors.
    """
    sendToLimit = 2048

    def test_sendToWouldBlock(self):
        """
        Test that the platform sendto(2) call fails with either L{EWOULDBLOCK}
        or L{EAGAIN} when the buffer is full.
        """
        # Make a server to which to connect
        port = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        port.bind(('127.0.0.1', 0))
        serverPortNumber = port.getsockname()[1]

        # Make a client to use to sendto to the server
        client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        client.setblocking(False)
        data = '*' * 1024
        addr = ('127.0.0.1', serverPortNumber)

        # Use up the buffer.
        for x in xrange(self.sendToLimit):
            try:
                client.sendto(data, addr)
            except socket.error, e:
                if e.args[0] in (EWOULDBLOCK, EAGAIN):
                    # The desired state has been achieved.
                    break
                else:
                    # Some unexpected error occurred.
                    raise
        else:
            self.fail("Could provoke neither EMFILE nor ENOBUFS from platform.")
    if platform.getType() != "win32":
        test_sendToWouldBlock.skip = (
            "Only Windows seems to be able to reliably provoke this behavior"
            "in the naive manner.")



class SelectReactorTestCase(TestCase):
    """
    Tests for select-specific failure conditions.
    """

    def _sendToFailureTest(self, socketErrorNumber):
        """
        Test behavior in the face of an exception from C{sendto(2)}.

        On any exception which indicates the platform is unable or unwilling
        to allocate further resources to us, the existing port should remain
        listening, and the exception should not propagate outward from write.

        @param socketErrorNumber: The errno to simulate from sendto.
        """
        class FakeSocket(object):
            """
            Pretend to be a socket in an overloaded system.
            """
            def sendto(self, data, addr):
                raise socket.error(
                    socketErrorNumber, os.strerror(socketErrorNumber))

        protocol = DatagramProtocol()
        port = Port(0, protocol, interface='127.0.0.1')
        port._bindSocket()
        serverPortNumber = port.getHost().port
        originalSocket = port.socket
        try:
            port.socket = FakeSocket()

            port.write('*', ('127.0.0.1', serverPortNumber))
        finally:
            port.socket = originalSocket


    def test_wouldBlockFromSendTo(self):
        """
        C{sendto(2)} can fail with C{EWOULDBLOCK} when there the send buffer is
        full. Test that this doesn't negatively impact any other existing
        connections.

        C{EWOULDBLOCK} mainly occurs on Windows, but occurs on other platforms
        when the speed of the interfaces is different.
        """
        return self._sendToFailureTest(EWOULDBLOCK)


    def test_againFromSendTo(self):
        """
        Similar to L{test_eWouldBlockFromSendTo}, but test the case where
        C{sendto(2)} fails with C{EAGAIN}.

        C{EAGAIN} and C{EWOULDBLOCK} are equal on Windows, Linux, OS X and
        FreeBSD, but may differ elsewhere.
        """
        return self._sendToFailureTest(EAGAIN)


if not interfaces.IReactorFDSet.providedBy(reactor):
    skipMsg = 'This test only applies to reactors that implement IReactorFDset'
    PlatformAssumptionsTestCase.skip = skipMsg
    SelectReactorTestCase.skip = skipMsg

