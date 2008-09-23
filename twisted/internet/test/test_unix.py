# Copyright (c) 2008 Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for implementations of L{IReactorUNIX}.
"""

from stat import S_IMODE
from os import stat
from socket import socket, SOCK_DGRAM
try:
    from socket import AF_UNIX
except ImportError:
    AF_UNIX = None

from twisted.trial import util
from twisted.internet.protocol import ServerFactory, DatagramProtocol
from twisted.internet.protocol import ConnectedDatagramProtocol
from twisted.internet.test.reactormixins import ReactorBuilder


_deprecatedModeMessage = (
    'The mode parameter of %(interface)s.%(method)s will be removed.  Do '
    'not pass a value for it.  Set permissions on the containing directory '
    'before calling %(interface)s.%(method)s, instead.')


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


    def _deprecatedModeTest(self, interfaceName, methodName, path, factory):
        """
        Assert that a deprecation warning is emitted when a value is specified
        for the mode parameter to the indicated reactor method.
        """
        reactor = self.buildReactor()
        method = getattr(reactor, methodName)
        port = self.assertWarns(
            DeprecationWarning,
            _deprecatedModeMessage % dict(
                interface=interfaceName, method=methodName),
            __file__,
            lambda: method(path, factory, mode=0246))
        port.stopListening()



class UNIXTestsBuilder(UNIXFamilyMixin, ReactorBuilder):
    """
    Builder defining tests relating to L{IReactorUNIX}.
    """
    def test_mode(self):
        """
        The UNIX socket created by L{IReactorUNIX.listenUNIX} is created with
        the mode specified.
        """
        self._modeTest('listenUNIX', self.mktemp(), ServerFactory())
    test_mode.suppress = [
        util.suppress(category=DeprecationWarning,
                      message=_deprecatedModeMessage % dict(
                interface='IReactorUNIX',
                method='listenUNIX'))]


    def test_deprecatedMode(self):
        """
        Passing any value for the C{mode} parameter of L{listenUNIX} causes a
        deprecation warning to be emitted.
        """
        self._deprecatedModeTest(
            'IReactorUNIX', 'listenUNIX', self.mktemp(), ServerFactory())



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
    test_listenMode.suppress = [
        util.suppress(category=DeprecationWarning,
                      message=_deprecatedModeMessage % dict(
                interface='IReactorUNIXDatagram',
                method='listenUNIXDatagram'))]


    def test_deprecatedListenMode(self):
        """
        Passing any value for the C{mode} parameter of L{listenUNIXDatagram}
        causes a deprecation warning to be emitted.
        """
        self._deprecatedModeTest(
            'IReactorUNIXDatagram', 'listenUNIXDatagram', self.mktemp(),
            DatagramProtocol())


    def test_deprecatedConnectMode(self):
        """
        Passing any value for the C{mode} parameter of L{connectUNIXDatagram}
        causes a deprecation warning to be emitted.
        """
        path = self.mktemp()
        server = socket(AF_UNIX, SOCK_DGRAM)
        server.bind(path)
        self.addCleanup(server.close)

        self._deprecatedModeTest(
            'IReactorUNIXDatagram', 'connectUNIXDatagram',
            path, ConnectedDatagramProtocol())


globals().update(UNIXTestsBuilder.makeTestCaseClasses())
globals().update(UNIXDatagramTestsBuilder.makeTestCaseClasses())
