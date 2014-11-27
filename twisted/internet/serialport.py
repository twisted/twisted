# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.


"""
Serial Port Protocol
"""

# http://twistedmatrix.com/trac/ticket/3725#comment:24
# Apparently applications use these names even though they should
# be imported from pyserial
__all__ = ["serial", "PARITY_ODD", "PARITY_EVEN", "PARITY_NONE",
           "STOPBITS_TWO", "STOPBITS_ONE", "FIVEBITS",
           "EIGHTBITS", "SEVENBITS", "SIXBITS",
# Name this module is actually trying to export
           "SerialPort"]

# All of them require pyserial at the moment, so check that first
import serial
from serial import PARITY_NONE, PARITY_EVEN, PARITY_ODD
from serial import STOPBITS_ONE, STOPBITS_TWO
from serial import FIVEBITS, SIXBITS, SEVENBITS, EIGHTBITS

from twisted.python.runtime import platform



class BaseSerialPort:
    """
    Base class for Windows and POSIX serial ports.

    @ivar _serialFactory: a pyserial C{serial.Serial} factory, used to create
        the instance stored in C{self._serial}. Overrideable to enable easier
        testing.

    @ivar _serial: a pyserial C{serial.Serial} instance used to manage the
        options on the serial port.
    """

    _serialFactory = serial.Serial


    def setBaudRate(self, baudrate):
        """
        Set baud rate on underlying serial device

        @type baudrate: number
        @param baudrate: Serial port baudrate
        @return: None
        """
        if hasattr(self._serial, "setBaudrate"):
            self._serial.setBaudrate(baudrate)
        else:
            self._serial.setBaudRate(baudrate)


    def inWaiting(self):
        """

        @return: number of characters currently in the input buffer.
        """
        return self._serial.inWaiting()


    def flushInput(self):
        """
        Clear input buffer, discarding all that is in the buffer.

        @return: None
        """
        self._serial.flushInput()


    def flushOutput(self):
        """
        Clear output buffer, aborting the current output and
        discarding all that is in the buffer.

        @return: None
        """
        self._serial.flushOutput()


    def sendBreak(self, duration=0.25):
        """
        Send break condition. Timed, returns to idle state
        after given duration.

        @type duration: number
        @param duration: Seconds to send break
        @return: None
        """
        self._serial.sendBreak(duration)


    def getDSR(self):
        """
        Read terminal status line: Data Set Ready

        @return: State of DSR
        """
        return self._serial.getDSR()


    def getCD(self):
        """
        Read terminal status line: Carrier Detect

        @return: State of DCD
        """
        return self._serial.getCD()


    def getRI(self):
        """
        Read terminal status line: Ring Indicator

        @return: State of RI
        """
        return self._serial.getRI()


    def getCTS(self):
        """
        Read terminal status line: Clear To Send

        @return: State of CTS
        """
        return self._serial.getCTS()


    def setDTR(self, on = 1):
        """
        Set terminal status line: Data Terminal Ready

        @type on: number
        @param on: Value to set DTR to
        @return: None
        """
        self._serial.setDTR(on)


    def setRTS(self, on = 1):
        """
        Set terminal status line: Request To Send

        @type on: number
        @param on: Value to set RTS to
        @return: None
        """
        self._serial.setRTS(on)



# Expert appropriate implementation of SerialPort.
if platform.isWindows():
    from twisted.internet._win32serialport import SerialPort
else:
    from twisted.internet._posixserialport import SerialPort
