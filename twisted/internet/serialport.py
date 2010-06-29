# Copyright (c) 2001-2010 Twisted Matrix Laboratories.
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

# system imports
import os, sys

# all of them require pyserial at the moment, so check that first
import serial
from serial import PARITY_NONE, PARITY_EVEN, PARITY_ODD
from serial import STOPBITS_ONE, STOPBITS_TWO
from serial import FIVEBITS, SIXBITS, SEVENBITS, EIGHTBITS

# common code for serial ports
class BaseSerialPort:
    def __init__(
        self, protocol, deviceNameOrPortNumber, reactor, 
        baudrate=9600, bytesize=EIGHTBITS, parity=PARITY_NONE,
        stopbits=STOPBITS_ONE, timeout=0, xonxoff=0, rtscts=0):
        """
        Initialize this serial transport.

        Serial parameters are passed through to the underlying pyserial
        C{Serial} constructor
        
        @param protocol: Protocol to use with the serial transport
        @type protocol: L{IProtocol} provider

        @param deviceNameOrPortNumber: OS-specific device name or number.
            e.g.  device number, starting at zero or C{'/dev/ttyUSB0'} on
            GNU/Linux or C{'COM3'} on Windows
        @type deviceNameOrPortNumber: C{str} or C{int}
        
        @param reactor: The reactor to use. On Windows, must implement
            L{twisted.internet.interfaces.IReactorWin32Events} e.g. 
            L{twisted.internet.win32eventreactor}

        @param baudrate: The baud rate to use to communicate with the serial
            device.
        @type baudrate: C{int}
        
        @param bytesize: number of databits
        @type bytesize: C{int}
        
        @param parity: The parity mode to use for error checking.  Must be
            either C{'N'} for none, C{'O'} for odd, C{'E'} for even, C{'M'}
            for mark, or C{'S'} for space.
        @type parity: C{str}
        
        @param stopbits: number of stopbits
        @type stopbits: C{int}
        
        @param timeout: ignored; do not pass a value for this parameter.
        
        @param xonxoff: enable software flow control (0/1)
        @type xonxoff: C{int}
        
        @param rtscts: enable RTS/CTS flow control (0/1)
        @type rtscts: C{int}
        
        @raise ValueError: Will be raised when serial parameters are out of range,
            e.g baudrate, bytesize, etc.

        @raise SerialException: In case the device can not be found or can
            not be configured.
        """
        # Only initialize the underlying Serial instance.  Error checking
        # and other initialization is done in the subclasses.
        self._serial = serial.Serial(
            deviceNameOrPortNumber, baudrate=baudrate,
            bytesize=bytesize, parity=parity,
            stopbits=stopbits, timeout=None,
            xonxoff=xonxoff, rtscts=rtscts)


    def setBaudRate(self, baudrate):
        if hasattr(self._serial, "setBaudrate"):
            self._serial.setBaudrate(baudrate)
        else:
            self._serial.setBaudRate(baudrate)

    def inWaiting(self):
        return self._serial.inWaiting()

    def flushInput(self):
        self._serial.flushInput()

    def flushOutput(self):
        self._serial.flushOutput()

    def sendBreak(self):
        self._serial.sendBreak()

    def getDSR(self):
        return self._serial.getDSR()

    def getCD(self):
        return self._serial.getCD()

    def getRI(self):
        return self._serial.getRI()

    def getCTS(self):
        return self._serial.getCTS()

    def setDTR(self, on = 1):
        self._serial.setDTR(on)

    def setRTS(self, on = 1):
        self._serial.setRTS(on)



class SerialPort(BaseSerialPort):
    """
    Non-implementation of the serial port transport, only actually used when
    running on a platform for which Twisted lacks serial port support
    (currently POSIX and Windows on CPython are supported).
    """

# replace SerialPort with appropriate serial port
if os.name == 'posix':
    from twisted.internet._posixserialport import SerialPort
elif sys.platform == 'win32':
    from twisted.internet._win32serialport import SerialPort
