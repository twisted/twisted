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

WARNING!  I'm BROKEN!
"""

# system imports
import os, threading, Queue

# dependent on pyserial ( http://pyserial.sf.net/ )
# only tested w/ 1.18 (5 Dec 2002)
import serial
from serial import PARITY_NONE, PARITY_EVEN, PARITY_ODD
from serial import STOPBITS_ONE, STOPBITS_TWO
from serial import FIVEBITS, SIXBITS, SEVENBITS, EIGHTBITS
from serialport import BaseSerialPort
import win32file, win32event

# twisted imports
from twisted.protocols import basic
from twisted.internet import abstract
from twisted.python import log

class SerialPort(BaseSerialPort, abstract.FileDescriptor):
    """A select()able serial device, acting as a transport."""
    connected = 1

    def __init__(self, protocol, deviceNameOrPortNumber, reactor, 
        baudrate = 9600, bytesize = EIGHTBITS, parity = PARITY_NONE,
        stopbits = STOPBITS_ONE, timeout = 0, xonxoff = 0, rtscts = 0):
        self._serial = serial.Serial(deviceNameOrPortNumber, baudrate = baudrate, bytesize = bytesize, parity = parity, stopbits = stopbits, timeout = timeout, xonxoff = xonxoff, rtscts = rtscts)
        self.flushInput()
        self.flushOutput()
        self.reactor = reactor
        self.protocol = protocol
        self.outQueue = Queue.Queue()
        self.closed = 0
        self.closedNotifies = 0
        log.msg('serial open')
        
        self.protocol = protocol
        self.protocol.makeConnection(self)
        self._overlapped = win32file.OVERLAPPED()
        self._overlapped.hEvent = win32event.CreateEvent(None, 0, 0, None)
        win32file.SetCommMask(self._serial.hComPort, win32file.EV_RXCHAR | win32file.EV_RXFLAG | win32file.EV_ERR | win32file.EV_TXEMPTY)
        rc, mask = win32file.WaitCommEvent(self._serial.hComPort, self._overlapped)
        log.msg('rc = %X mask = %X mymask = %X' % (rc, mask, win32file.EV_RXCHAR | win32file.EV_RXFLAG | win32file.EV_ERR | win32file.EV_TXEMPTY))
        if rc == 0:
            win32event.SetEvent(self._overlapped.hEvent)
        self.reactor.addEvent(self._overlapped.hEvent, self, self.serialEvent)
        log.msg('addEvent')

    def serialEvent(self):
        log.msg('serial event')
        mask = win32file.GetCommMask(self._serial.hComPort)
        log.msg('serial event %X' % mask)
        if mask & win32file.EV_RXCHAR:
            self.doRead()
        if mask & win32file.EV_TXEMPTY:
            self.doWrite()
        if mask & win32file.EV_ERR:
            log.msg('win32event.EV_ERR')
        if mask & win32file.EV_RXFLAG:
            log.msg('win32event.EV_RXFLAG')
        log.msg('serial event processed')
        win32file.WaitCommEvent(self._serial.hComPort, self._overlapped)
    
    def write(self, data):
        log.msg('adding to write queue')
        self.outQueue.put(data)

    def doWrite(self):
        return
        log.msg('doing a write')
        try:
            dataToWrite = self.outQueue.get_nowait()
        except:
            log.msg('outQueue empty?')
            return
        #flags, comstat = win32file.ClearCommError(self._serial.hComPort)
        win32file.WriteFile(self._serial.hComPort, dataToWrite, self._overlapped)
        
    
    def doRead(self):
        log.msg('doing a read')
        flags, comstat = win32file.ClearCommError(self._serial.hComPort)
        while 1:
            log.msg('read loop iteration')
            rc, data = win32file.ReadFile(self._serial.hComPort, comstat.cbInQue, self._overlapped)
            data = str(data)
            log.msg('read %r' % data)
            if not len(data):
                break
            self.protocol.dataReceived(data)
    
    def connectionLost(self, reason):
        self.reactor.removeEvent(self._overlapped.hEvent)
        abstract.FileDescriptor.connectionLost(self, reason)
        self._serial.close()
