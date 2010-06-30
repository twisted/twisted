# Copyright (c) 2001-2010 Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Serial port support for Windows.

Requires:
pySerial - http://pyserial.sourceforge.net/
pywin32 (previously win32all) - http://pywin32.sourceforge.net/

Also, needs to be used with a reactor that implements
L{twisted.internet.interfaces.IReactorWin32Events}
e.g. L{twisted.internet.win32eventreactor} win32eventreactor.
"""

# system imports
from serial import PARITY_NONE, STOPBITS_ONE, EIGHTBITS
import win32file, win32event

# twisted imports
from twisted.internet import abstract
from twisted.internet.serialport import BaseSerialPort



class SerialPort(BaseSerialPort, abstract.FileDescriptor):
    """
    A select()able serial device, acting as a transport.
    """

    connected = 1

    def __init__(self, protocol, deviceNameOrPortNumber, reactor,
        baudrate=9600, bytesize=EIGHTBITS, parity=PARITY_NONE,
        stopbits=STOPBITS_ONE, xonxoff=0, rtscts=0):

        abstract.FileDescriptor.__init__(self, reactor)
        BaseSerialPort.__init__(
            self, protocol, deviceNameOrPortNumber, reactor,
            baudrate=baudrate, bytesize=bytesize,
            parity=parity, stopbits=stopbits,
            xonxoff=xonxoff, rtscts=rtscts)

        self.outQueue = []
        self.closed = 0
        self.closedNotifies = 0
        self.writeInProgress = 0

        self._overlappedRead = win32file.OVERLAPPED()
        self._overlappedRead.hEvent = win32event.CreateEvent(None, 1, 0, None)
        self._overlappedWrite = win32file.OVERLAPPED()
        self._overlappedWrite.hEvent = win32event.CreateEvent(None, 0, 0, None)

        self.reactor.addEvent(self._overlappedRead.hEvent, self, 'serialReadEvent')
        self.reactor.addEvent(self._overlappedWrite.hEvent, self, 'serialWriteEvent')

        self.protocol.makeConnection(self)

        flags, comstat = win32file.ClearCommError(self._serial.hComPort)
        rc, self.read_buf = win32file.ReadFile(self._serial.hComPort,
                                               win32file.AllocateReadBuffer(1),
                                               self._overlappedRead)

    def serialReadEvent(self):
        #get that character we set up
        n = win32file.GetOverlappedResult(self._serial.hComPort, self._overlappedRead, 0)
        if n:
            first = str(self.read_buf[:n])
            #now we should get everything that is already in the buffer
            flags, comstat = win32file.ClearCommError(self._serial.hComPort)
            if comstat.cbInQue:
                win32event.ResetEvent(self._overlappedRead.hEvent)
                rc, buf = win32file.ReadFile(self._serial.hComPort,
                                             win32file.AllocateReadBuffer(comstat.cbInQue),
                                             self._overlappedRead)
                n = win32file.GetOverlappedResult(self._serial.hComPort, self._overlappedRead, 1)
                #handle all the received data:
                self.protocol.dataReceived(first + str(buf[:n]))
            else:
                #handle all the received data:
                self.protocol.dataReceived(first)

        #set up next one
        win32event.ResetEvent(self._overlappedRead.hEvent)
        rc, self.read_buf = win32file.ReadFile(self._serial.hComPort,
                                               win32file.AllocateReadBuffer(1),
                                               self._overlappedRead)

    def write(self, data):
        if data:
            if self.writeInProgress:
                self.outQueue.append(data)
            else:
                self.writeInProgress = 1
                win32file.WriteFile(self._serial.hComPort, data, self._overlappedWrite)

    def serialWriteEvent(self):
        try:
            dataToWrite = self.outQueue.pop(0)
        except IndexError:
            self.writeInProgress = 0
            return
        else:
            win32file.WriteFile(self._serial.hComPort, dataToWrite, self._overlappedWrite)

    def connectionLost(self, reason):
        self.reactor.removeEvent(self._overlappedRead.hEvent)
        self.reactor.removeEvent(self._overlappedWrite.hEvent)
        abstract.FileDescriptor.connectionLost(self, reason)
        self._serial.close()
