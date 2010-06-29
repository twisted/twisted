# Copyright (c) 2001-2010 Twisted Matrix Laboratories.
# See LICENSE for details.


"""
Serial Port Protocol

pySerial is required for all platforms: http://pyserial.sourceforge.net/

Windows requires the use of a reactor that supports
L{twisted.internet.interfaces.IReactorWin32Events}
e.g. L{twisted.internet.win32eventreactor}

pywin32 (previously win32all) is also required for Windows:
http://sourceforge.net/projects/pywin32/
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
    Initialize the SerialPort
    Serial parameters are passed through to the underlying 
    pyserial Serial constructor
    
    @param protocol: Protocol to use with the serial transport
    @type protocol: type which implements L{IProtocol}
    
    @param deviceNameOrPortNumber: OS-specific device name or number. e.g.
                                   device number, starting at zero
                                   '/dev/ttyUSB0' on GNU/Linux
                                   'COM3' on Windows
    @type deviceNameOrPortNumber: C{str} or C{int}
    
    @param reactor: The reactor to use. On Windows, must implement 
                   L{twisted.internet.interfaces.IReactorWin32Events}
                   e.g. L{twisted.internet.win32eventreactor}
    @type reactor: type which implements L{IReactor}.

    @param baudrate: baudrate
    @type baudrate: C{int}
    
    @param bytesize: number of databits
    @type bytesize: C{int}
    
    @param parity: enable parity checking
    @type parity: C{str}
    
    @param stopbits: number of stopbits
    @type stopbits: C{int}
    
    @param timeout: set a read timeout value (not implemented on win32)
    @type timeout: C{int} or C{float}
    
    @param xonxoff: enable software flow control (0/1)
    @type xonxoff: C{int}
    
    @param rtscts: enable RTS/CTS flow control (0/1)
    @type rtscts: C{int}
    
    @raise ValueError: On Windows, if the reactor does not support 
                       L{twisted.internet.interfaces.IReactorWin32Events}
                       e.g. L{twisted.internet.win32eventreactor}

    @raise ValueError: Will be raised when serial parameters are out of range,
                       e.g baudrate, bytesize, etc.

    @raise SerialException: In case the device can not be found or 
                            can not be configured
    """


# replace SerialPort with appropriate serial port
if os.name == 'posix':
    from twisted.internet._posixserialport import SerialPort
elif sys.platform == 'win32':
    from twisted.internet._win32serialport import SerialPort
