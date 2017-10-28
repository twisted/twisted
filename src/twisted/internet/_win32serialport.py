# -*- test-case-name: twisted.internet.test.test_win32serialport -*-

# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Serial port support for Windows.

Requires PySerial and pywin32.
"""

from __future__ import division, absolute_import

# system imports
from serial import PARITY_NONE
from serial import STOPBITS_ONE
from serial import EIGHTBITS
from serial.serialutil import to_bytes
import win32file
from pywincffi.kernel32 import (
    CreateEvent, ClearCommError, GetOverlappedResult, ReadFile, ResetEvent,
    WriteFile
)
from pywincffi.wintypes import OVERLAPPED


# twisted imports
from twisted.internet import abstract

# sibling imports
from twisted.internet.serialport import BaseSerialPort


class SerialPort(BaseSerialPort, abstract.FileDescriptor):
    """A serial device, acting as a transport, that uses a win32 event."""

    connected = 1

    def __init__(self, protocol, deviceNameOrPortNumber, reactor,
        baudrate = 9600, bytesize = EIGHTBITS, parity = PARITY_NONE,
        stopbits = STOPBITS_ONE, xonxoff = 0, rtscts = 0):
        self._serial = self._serialFactory(
            deviceNameOrPortNumber, baudrate=baudrate, bytesize=bytesize,
            parity=parity, stopbits=stopbits, timeout=None,
            xonxoff=xonxoff, rtscts=rtscts)
        self.flushInput()
        self.flushOutput()
        self.reactor = reactor
        self.protocol = protocol
        self.outQueue = []
        self.closed = 0
        self.closedNotifies = 0
        self.writeInProgress = 0

        self.protocol = protocol
        self._overlappedRead = OVERLAPPED()
        self._overlappedRead.hEvent = CreateEvent(None, True, False, None)
        self._overlappedWrite = OVERLAPPED()
        self._overlappedWrite.hEvent = CreateEvent(None, False, False, None)

        self.reactor.addEvent(self._overlappedRead.hEvent, self, 'serialReadEvent')
        self.reactor.addEvent(self._overlappedWrite.hEvent, self, 'serialWriteEvent')

        self.protocol.makeConnection(self)
        self._finishPortSetup()


    def _finishPortSetup(self):
        """
        Finish setting up the serial port.

        This is a separate method to facilitate testing.
        """
        flags, comstat = self._clearCommError()
        rc, self.read_buf = ReadFile(self._serial._port_handle,
                                               win32file.AllocateReadBuffer(1),
                                               self._overlappedRead)


    def _clearCommError(self):
        return ClearCommError(self._serial._port_handle)


    def serialReadEvent(self):
        #get that character we set up
        n = GetOverlappedResult(self._serial._port_handle,
                                self._overlappedRead, 0)
        first = to_bytes(self.read_buf[:n])
        #now we should get everything that is already in the buffer
        flags, comstat = self._clearCommError()
        if comstat.cbInQue:
            ResetEvent(self._overlappedRead.hEvent)
            rc, buf = ReadFile(self._serial._port_handle,
                               win32file.AllocateReadBuffer(comstat.cbInQue),
                               self._overlappedRead)
            n = GetOverlappedResult(self._serial._port_handle,
                                    self._overlappedRead, 1)
            #handle all the received data:
            self.protocol.dataReceived(first + to_bytes(buf[:n]))
        else:
            #handle all the received data:
            self.protocol.dataReceived(first)

        #set up next one
        ResetEvent(self._overlappedRead.hEvent)
        rc, self.read_buf = ReadFile(self._serial._port_handle,
                                     win32file.AllocateReadBuffer(1),
                                     self._overlappedRead)


    def write(self, data):
        if data:
            if self.writeInProgress:
                self.outQueue.append(data)
            else:
                self.writeInProgress = 1
                WriteFile(self._serial._port_handle, data,
                          self._overlappedWrite)


    def serialWriteEvent(self):
        try:
            dataToWrite = self.outQueue.pop(0)
        except IndexError:
            self.writeInProgress = 0
            return
        else:
            WriteFile(self._serial._port_handle, dataToWrite,
                      self._overlappedWrite)


    def connectionLost(self, reason):
        """
        Called when the serial port disconnects.

        Will call C{connectionLost} on the protocol that is handling the
        serial data.
        """
        self.reactor.removeEvent(self._overlappedRead.hEvent)
        self.reactor.removeEvent(self._overlappedWrite.hEvent)
        abstract.FileDescriptor.connectionLost(self, reason)
        self._serial.close()
        self.protocol.connectionLost(reason)
