# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.


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
from twisted.internet import abstract, javareactor, main
from twisted.python import log

class SerialPort(BaseSerialPort, javareactor.JConnection):
    """A select()able serial device, acting as a transport."""
    connected = 1

    def __init__(self, protocol, deviceNameOrPortNumber, reactor, 
        baudrate = 9600, bytesize = EIGHTBITS, parity = PARITY_NONE,
        stopbits = STOPBITS_ONE, timeout = 3, xonxoff = 0, rtscts = 0):
        # do NOT use timeout = 0 !!
        self._serial = serial.Serial(deviceNameOrPortNumber, baudrate = baudrate, bytesize = bytesize, parity = parity, stopbits = stopbits, timeout = timeout, xonxoff = xonxoff, rtscts = rtscts)
        javareactor.JConnection.__init__(self, self._serial.sPort, protocol, None)
        self.flushInput()
        self.flushOutput()
        
        self.reactor = reactor
        self.protocol = protocol
        self.protocol.makeConnection(self)
        wb = javareactor.WriteBlocker(self, reactor.q)
        wb.start()
        self.writeBlocker = wb
        javareactor.ReadBlocker(self, reactor.q).start()
          
    def writeSomeData(self, data):
        try:
          self._serial.write(data)
          return len(data)
        # should have something better here
        except Exception, e:
          return main.CONNECTION_LOST

    def doRead(self):
        readBytes = ''
        try:
          readBytes = self._serial.read(min(8192, self.inWaiting()))
        except Exception, e:
          return main.CONNECTION_LOST
        if not readBytes:
          return main.CONNECTION_LOST
        self.protocol.dataReceived(readBytes)
        
    def connectionLost(self, reason):
        self._serial.close()
        self.protocol.connectionLost(reason)
        abstract.FileDescriptor.connectionLost(self, reason)

    def getHost(self):
        raise NotImplementedError

    def getPeer(self):
        raise NotImplementedError

    def getTcpNoDelay(self):
        raise NotImplementedError

    def setTcpNoDelay(self, enabled):
        raise NotImplementedError
