# Copyright (c) 2001-2010 Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Serial Port Protocol
"""

# dependent on pyserial ( http://pyserial.sf.net/ )
# only tested w/ 1.18 (5 Dec 2002)
from serial import PARITY_NONE
from serial import STOPBITS_ONE
from serial import EIGHTBITS

from serialport import BaseSerialPort

# twisted imports
from twisted.internet import abstract, fdesc

class SerialPort(BaseSerialPort, abstract.FileDescriptor):
    """
    A select()able serial device, acting as a transport.
    """

    connected = 1

    def __init__(self, protocol, deviceNameOrPortNumber, reactor, 
        baudrate=9600, bytesize=EIGHTBITS, parity=PARITY_NONE,
        stopbits=STOPBITS_ONE, timeout=None, xonxoff=0, rtscts=0):
        abstract.FileDescriptor.__init__(self, reactor)
        BaseSerialPort.__init__(
                self, deviceNameOrPortNumber,
                baudrate=baudrate, bytesize=bytesize,
                parity=parity, stopbits=stopbits,
                xonxoff=xonxoff, rtscts=rtscts)
        self.reactor = reactor
        self.flushInput()
        self.flushOutput()
        self.protocol = protocol
        self.protocol.makeConnection(self)
        self.startReading()

    def fileno(self):
        return self._serial.fd

    def writeSomeData(self, data):
        """
        Write some data to the serial device.
        """
        return fdesc.writeToFD(self.fileno(), data)

    def doRead(self):
        """
        Some data's readable from serial device.
        """
        return fdesc.readFromFD(self.fileno(), self.protocol.dataReceived)

    def connectionLost(self, reason):
        abstract.FileDescriptor.connectionLost(self, reason)
        self._serial.close()
