# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for implementations of L{IReactorUNIX}.
"""

from stat import S_IMODE
from os import stat
from sys import platform
from tempfile import mktemp

try:
    from socket import AF_UNIX
except ImportError:
    AF_UNIX = None

from zope.interface.verify import verifyObject

from twisted.python.hashlib import md5
from twisted.internet.interfaces import IConnector
from twisted.internet.address import UNIXAddress
from twisted.internet.endpoints import UNIXServerEndpoint, UNIXClientEndpoint
from twisted.internet import interfaces
from twisted.internet.protocol import (
    ServerFactory, ClientFactory, DatagramProtocol)
from twisted.internet.test.reactormixins import ReactorBuilder
from twisted.internet.test.test_core import ObjectModelIntegrationMixin
from twisted.internet.test.test_tcp import StreamTransportTestsMixin
from twisted.internet.test.connectionmixins import ConnectionTestsMixin


class UNIXFamilyMixin:
    """
    Test-helper defining mixin for things related to AF_UNIX sockets.
    """
    if AF_UNIX is None:
        skip = "Platform does not support AF_UNIX sockets"

    def _modeTest(self, methodName, path, factory):
        """
        Assert that the mode of the created unix socket is set to the mode
        specified to the reactor method.
        """
        mode = 0600
        reactor = self.buildReactor()
        unixPort = getattr(reactor, methodName)(path, factory, mode=mode)
        unixPort.stopListening()
        self.assertEqual(S_IMODE(stat(path).st_mode), mode)


def _abstractPath(case):
    """
    Return a new, unique abstract namespace path to be listened on.
    """
    # Use the test cases's mktemp to get something unique, but also squash it
    # down to make sure it fits in the unix socket path limit (something around
    # 110 bytes).
    return md5(case.mktemp()).hexdigest()


class UNIXTestsBuilder(UNIXFamilyMixin, ReactorBuilder, ConnectionTestsMixin):
    """
    Builder defining tests relating to L{IReactorUNIX}.
    """
    def serverEndpoint(self, reactor):
        """
        Construct a UNIX server endpoint.
        """
        # self.mktemp() often returns a path which is too long to be used.
        path = mktemp(suffix='.sock', dir='.')
        return UNIXServerEndpoint(reactor, path)


    def clientEndpoint(self, reactor, serverAddress):
        """
        Construct a UNIX client endpoint.
        """
        return UNIXClientEndpoint(reactor, serverAddress.name)


    def test_interface(self):
        """
        L{IReactorUNIX.connectUNIX} returns an object providing L{IConnector}.
        """
        reactor = self.buildReactor()
        connector = reactor.connectUNIX(self.mktemp(), ClientFactory())
        self.assertTrue(verifyObject(IConnector, connector))


    def test_mode(self):
        """
        The UNIX socket created by L{IReactorUNIX.listenUNIX} is created with
        the mode specified.
        """
        self._modeTest('listenUNIX', self.mktemp(), ServerFactory())


    def test_listenOnLinuxAbstractNamespace(self):
        """
        On Linux, a UNIX socket path may begin with C{'\0'} to indicate a socket
        in the abstract namespace.  L{IReactorUNIX.listenUNIX} accepts such a
        path.
        """
        # Don't listen on a path longer than the maximum allowed.
        path = _abstractPath(self)
        reactor = self.buildReactor()
        port = reactor.listenUNIX('\0' + path, ServerFactory())
        self.assertEqual(port.getHost(), UNIXAddress('\0' + path))
    if platform != 'linux2':
        test_listenOnLinuxAbstractNamespace.skip = (
            'Abstract namespace UNIX sockets only supported on Linux.')


    def test_connectToLinuxAbstractNamespace(self):
        """
        L{IReactorUNIX.connectUNIX} also accepts a Linux abstract namespace
        path.
        """
        path = _abstractPath(self)
        reactor = self.buildReactor()
        connector = reactor.connectUNIX('\0' + path, ClientFactory())
        self.assertEqual(
            connector.getDestination(), UNIXAddress('\0' + path))
    if platform != 'linux2':
        test_connectToLinuxAbstractNamespace.skip = (
            'Abstract namespace UNIX sockets only supported on Linux.')



class UNIXDatagramTestsBuilder(UNIXFamilyMixin, ReactorBuilder):
    """
    Builder defining tests relating to L{IReactorUNIXDatagram}.
    """
    # There's no corresponding test_connectMode because the mode parameter to
    # connectUNIXDatagram has been completely ignored since that API was first
    # introduced.
    def test_listenMode(self):
        """
        The UNIX socket created by L{IReactorUNIXDatagram.listenUNIXDatagram}
        is created with the mode specified.
        """
        self._modeTest('listenUNIXDatagram', self.mktemp(), DatagramProtocol())


    def test_listenOnLinuxAbstractNamespace(self):
        """
        On Linux, a UNIX socket path may begin with C{'\0'} to indicate a socket
        in the abstract namespace.  L{IReactorUNIX.listenUNIXDatagram} accepts
        such a path.
        """
        path = _abstractPath(self)
        reactor = self.buildReactor()
        port = reactor.listenUNIXDatagram('\0' + path, DatagramProtocol())
        self.assertEqual(port.getHost(), UNIXAddress('\0' + path))
    if platform != 'linux2':
        test_listenOnLinuxAbstractNamespace.skip = (
            'Abstract namespace UNIX sockets only supported on Linux.')



class UNIXPortTestsBuilder(ReactorBuilder, ObjectModelIntegrationMixin,
                           StreamTransportTestsMixin):
    """
    Tests for L{IReactorUNIX.listenUnix}
    """
    requiredInterfaces = [interfaces.IReactorUNIX]

    def getListeningPort(self, reactor, factory):
        """
        Get a UNIX port from a reactor
        """
        # self.mktemp() often returns a path which is too long to be used.
        path = mktemp(suffix='.sock', dir='.')
        return reactor.listenUNIX(path, factory)


    def getExpectedStartListeningLogMessage(self, port, factory):
        """
        Get the message expected to be logged when a UNIX port starts listening.
        """
        return "%s starting on %r" % (factory, port.getHost().name)


    def getExpectedConnectionLostLogMsg(self, port):
        """
        Get the expected connection lost message for a UNIX port
        """
        return "(UNIX Port %s Closed)" % (repr(port.port),)



globals().update(UNIXTestsBuilder.makeTestCaseClasses())
globals().update(UNIXDatagramTestsBuilder.makeTestCaseClasses())
globals().update(UNIXPortTestsBuilder.makeTestCaseClasses())
