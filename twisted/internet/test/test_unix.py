# Copyright (c) 2008-2010 Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for implementations of L{IReactorUNIX}.
"""

from stat import S_IMODE
from os import stat
try:
    from socket import AF_UNIX
except ImportError:
    AF_UNIX = None

from twisted.internet.protocol import ServerFactory, DatagramProtocol
from twisted.internet.test.reactormixins import ReactorBuilder


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



globals().update(UNIXTestsBuilder.makeTestCaseClasses())
globals().update(UNIXDatagramTestsBuilder.makeTestCaseClasses())
