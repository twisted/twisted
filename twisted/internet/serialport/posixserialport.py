# Twisted, the Framework of Your Internet
# Copyright (C) 2001-2002 Matthew W. Lefkowitz
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of version 2.1 of the GNU Lesser General Public
# License as published by the Free Software Foundation.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

"""
Serial Port Protocol
"""

# system imports
import os

# dependent on pyserial ( http://pyserial.sf.net/ )
# only tested w/ 1.18 (5 Dec 2002)
import serial
from serial import PARITY_NONE, PARITY_EVEN, PARITY_ODD
from serial import STOPBITS_ONE, STOPBITS_TWO
from serial import FIVEBITS, SIXBITS, SEVENBITS, EIGHTBITS

from serialport import BaseSerialPort

# twisted imports
from twisted.internet import abstract, fdesc, main

class SerialPort(BaseSerialPort, abstract.FileDescriptor):
    """A select()able serial device, acting as a transport."""
    connected = 1

    def __init__(self, protocol, deviceNameOrPortNumber, reactor, 
        baudrate = 9600, bytesize = EIGHTBITS, parity = PARITY_NONE,
        stopbits = STOPBITS_ONE, timeout = 0, xonxoff = 0, rtscts = 0):
        abstract.FileDescriptor.__init__(self, reactor)
        self._serial = serial.Serial(deviceNameOrPortNumber, baudrate = baudrate, bytesize = bytesize, parity = parity, stopbits = stopbits, timeout = timeout, xonxoff = xonxoff, rtscts = rtscts)
        self.reactor = reactor
        self.flushInput()
        self.flushOutput()
        self.protocol = protocol
        self.protocol.makeConnection(self)
        self.startReading()

    def fileno(self):
        return self._serial.fd

    def writeSomeData(self, data):
        """Write some data to the serial device.
        """
        try:
            return os.write(self.fileno(), data)
        except IOError, io:
            if io.args[0] == errno.EAGAIN:
                return 0
            return main.CONNECTION_LOST

    def doRead(self):
        """Some data's readable from serial device.
        """
        return fdesc.readFromFD(self.fileno(), self.protocol.dataReceived)

    def connectionLost(self, reason):
        abstract.FileDescriptor.connectionLost(self, reason)
        self._serial.close()
