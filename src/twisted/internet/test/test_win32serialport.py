# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.internet.serialport}.
"""

import os
import shutil
import tempfile

from twisted.trial import unittest
from twisted.internet.protocol import Protocol
from twisted.python.runtime import platform
from twisted.internet.test.test_serialport import DoNothing

try:
    from twisted.internet import serialport
    import serial
except ImportError as e:
    serialport = None
    serial = None


if serialport is not None:
    class Serial(serial.Serial):
        def _reconfigurePort(self):
            pass


    class TestableSerialPortBase(serialport.SerialPort):
        _serialFactory = Serial

        def __init__(self, cbInQue, *args, **kwargs):
            self.comstat = serial.win32.COMSTAT
            self.comstat.cbInQue = cbInQue

            super(TestableSerialPortBase, self).__init__(*args, **kwargs)

        def _clearCommError(self):
            return True, self.comstat


class CollectReceivedProtocol(Protocol):
    def __init__(self):
        self.received_data = []

    def dataReceived(self, data):
        self.received_data.append(data)


class Win32SerialPortTests(unittest.TestCase):
    if not platform.isWindows():
        skip = "This test must run on Windows."

    elif not serialport:
        skip = "Windows serial port support is not available."

    def setUp(self):
        # Re-usable protocol and reactor
        self.protocol = CollectReceivedProtocol()
        self.reactor = DoNothing()


        self.directory = tempfile.mkdtemp()
        self.path = os.path.join(self.directory, 'fake_serial')

        data = b'1234'
        with open(self.path, 'wb') as f:
            f.write(data)

    def tearDown(self):
        shutil.rmtree(self.directory)

    def common_serialPortReturnsBytes(self, cbInQue):
        port = TestableSerialPortBase(cbInQue, self.protocol, self.path, self.reactor)
        port.serialReadEvent()
        self.assertTrue(all(
            isinstance(d, bytes) for d in self.protocol.received_data
        ))
        port.connectionLost(reason='just cleanup')

    def test_serialPortReturnsBytes_1(self):
        self.common_serialPortReturnsBytes(cbInQue=False)

    def test_serialPortReturnsBytes_2(self):
        self.common_serialPortReturnsBytes(cbInQue=True)
