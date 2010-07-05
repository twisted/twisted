# Copyright (c) 2010 Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.internet.serialport}.
"""


try:
    from serial import SerialException
except ImportError, e:
    skip = "serial support unavailable (%s)" % (e,)
else:
    from twisted.internet.serialport import SerialPort

from twisted.internet.error import ConnectionDone
from twisted.internet.defer import Deferred
from twisted.internet.test.reactormixins import ReactorBuilder
from twisted.trial.unittest import SkipTest
from twisted.test.test_tcp import ConnectionLostNotifyingProtocol


class SerialPortTestsBuilder(ReactorBuilder):
    """
    Builder defining tests for L{twisted.internet.serialport}.
    """
    portName = 0

    def test_loseConnection(self):
        """
        The serial port transport implementation of C{loseConnection}
        causes the serial port to be closed and the protocol's
        C{connectionLost} method to be called with a L{Failure}
        wrapping L{ConnectionDone}.
        """
        reactor = self.buildReactor()
        onConnectionLost = Deferred()
        protocol = ConnectionLostNotifyingProtocol(onConnectionLost)

        try:
            port = SerialPort(protocol, self.portName, reactor)
        except SerialException, e:
            raise SkipTest("Cannot open serial port: %s" % (e,))

        def cbConnLost(ignored):
            reactor.stop()
        onConnectionLost.addCallback(cbConnLost)

        port.loseConnection()

        self.runReactor(reactor)

        protocol.lostConnectionReason.trap(ConnectionDone)


globals().update(SerialPortTestsBuilder.makeTestCaseClasses())
