# -*- test-case-name: twisted.test.test_conio -*-

# Copyright (c) 2009 Twisted Matrix Laboratories.
# See LICENSE for details.

"""
This module implements POSIX replacements for stdin/stdout/stderr
that support asyncronous read/write to a Windows console.

Some details about Windows console:
 - a process can have attached only one console
 - there can be only one input buffer
 - there can be more then one output buffer

Moreover this module tries to offer an higher level and convenient
interface for termios commands.
"""

import os
import errno
import pywintypes
import win32api
import win32file
import win32console


_ENABLE_NORMAL_MODE = win32console.ENABLE_ECHO_INPUT | win32console.ENABLE_LINE_INPUT
_ENABLE_WINDOW_INPUT = win32console.ENABLE_WINDOW_INPUT

_share_mode = win32file.FILE_SHARE_READ | win32file.FILE_SHARE_WRITE
_access_mode = win32file.GENERIC_READ | win32file.GENERIC_WRITE

def GetStdHandle(name):
    """
    Get console handles even if they are redirected
    (usually pipes to/from a parent process)
    """
    handle = win32file.CreateFile(name, _access_mode, _share_mode, None, win32file.OPEN_EXISTING, 0, None)
    return win32console.PyConsoleScreenBufferType(handle)


def getWindowSize():
    size = GetStdHandle("CONOUT$").GetConsoleScreenBufferInfo()["Size"]
    return (size.X, size.Y)


class ConsoleImpl(object):
    """
    """
    def __init__(self):
        self.in_handle  = GetStdHandle("CONIN$")
        self.out_handle = GetStdHandle("CONOUT$")

        # The code page in use
        # I assume that this does not change
        self.cp = "cp%d" % win32console.GetConsoleCP()

        self.init()

    def init(self):
        self.in_closed = False
        self.out_closed = False
        self._inbuf = ""
        self.inbuffer = []
        self.echo = True
        defaultMode = self.in_handle.GetConsoleMode()
        self.in_handle.SetConsoleMode(defaultMode | _ENABLE_WINDOW_INPUT)
        self._windowChangeCallback = None
        self.read = self._read
        self.readline = self._readline
        return self

    #
    # termios interface
    #
    def isatty(self): 
        return True

    def flushIn(self):
        # Flush both internal buffer and system console buffer
        self._inbuf = ""
        self.inbuffer = []
        self.in_handle.FlushConsoleInputBuffer() 

    def setEcho(self, enabled):
        self.echo = enabled

    def enableRawMode(self, enabled=True):
        """
        Enable raw mode.
        """
        self.flushIn()
        mode = self.in_handle.GetConsoleMode()

        if enabled:
            self.read = self._read_raw
            self.readline = self._readline_raw

            # Set mode on the console, too
            # XXX check me (this seems not to work)
            self.in_handle.SetConsoleMode(mode & ~_ENABLE_NORMAL_MODE)
        else:
            self.read = self._read
            self.readline = self._readline

            # Set mode on the console, too
            self.in_handle.SetConsoleMode(mode | _ENABLE_NORMAL_MODE)

    def setWindowChangeCallback(self, callback):
        """
        callback is called when the console window buffer is
        changed.

        Note: WINDOW_BUFFER_SIZE_EVENT is only raised when changing
        the window *buffer* size from the console menu
        """
        self._windowChangeCallback = callback


    #
    # Channel interface
    #
    def closeRead(self):
        self.flushIn()
        self.in_closed = True

    def closeWrite(self):
        self.out_closed = True

    def isWriteClosed(self):
        return self.out_closed

    def write(self, s):
        """
        Write a string to the console.
        """
        return self.out_handle.WriteConsole(s)

    def writelines(self, seq):
        """
        Write a sequence of strings to the console.
        """
        s = ''.join(seq)
        return self.out_handle.WriteConsole(s)

    def _read(self):
        """
        """
        if self.out_closed:
            raise pywintypes.error(6, "The handle is invalid.") 
        info = self.out_handle.GetConsoleScreenBufferInfo()
        self.rowSize = info["MaximumWindowSize"].X 

        # Initialize the current cursor position
        if not self._inbuf:
            self.pos = info["CursorPosition"]

        while 1:
            n = self.in_handle.GetNumberOfConsoleInputEvents()
            if n == 0:
                break

            # Process input
            for record in self.in_handle.ReadConsoleInput(n):
                if record.EventType == win32console.WINDOW_BUFFER_SIZE_EVENT:
                    self.rowSize = record.Size.X
                    if self._windowChangeCallback:
                        self._windowChangeCallback()
                if record.EventType != win32console.KEY_EVENT or \
                        not record.KeyDown:
                    continue
                for i in range(record.RepeatCount):
                    self._handleReadChar(record.Char)

        if self.inbuffer:
            return self.inbuffer.pop(0)
        else:
            return ''

    def _handleReadChar(self, char):
        info = self.out_handle.GetConsoleScreenBufferInfo()
        if char == '\b':
            if self.echo:
                pos = info["CursorPosition"]
                # Move the cursor, handle line wrapping 
                if pos.X > self.pos.X or (pos.X > 0 and \
                        len(self._inbuf)+self.pos.X > self.rowSize):
                    pos.X -= 1
                elif len(self._inbuf)+self.pos.X >= self.rowSize:
                    pos.X = self.rowSize - 1
                    pos.Y -= 1

                self.out_handle.SetConsoleCursorPosition(pos)
                self.out_handle.WriteConsoleOutputCharacter(' ', pos)

            # Delete the characters from accumulation buffer
            self._inbuf = self._inbuf[:-1]
            return
        if char == '\0':
            # XXX TODO handle keyboard navigation
            return
        if char == '\r':
            self._inbuf += os.linesep
            if self.echo:
                self.out_handle.WriteConsole(os.linesep) # do echo

            # We have some data ready to be read
            self.inbuffer.append(self._inbuf)
            self._inbuf = ""
            self.pos = info["CursorPosition"]
            return

        data = char.encode(self.cp)
        if self.echo:
            self.out_handle.WriteConsole(data) # do echo
        self._inbuf += data

    def _read_raw(self):
        """
        """
        n = self.in_handle.GetNumberOfConsoleInputEvents()
        if n == 0:
            return ''
        # Process input
        for record in self.in_handle.ReadConsoleInput(n):
            if record.EventType == win32console.WINDOW_BUFFER_SIZE_EVENT:
                if self._windowChangeCallback:
                    self._windowChangeCallback()
            if record.EventType != win32console.KEY_EVENT or not record.KeyDown:
                continue

            char = record.Char
            for i in range(record.RepeatCount):
                if char == '\0':
                    vCode = record.VirtualKeyCode
                    # XXX TODO handle keyboard navigation
                    continue

                data = char.encode(self.cp)
                self._inbuf += data
        return self._inbuf

    def _readline(self):
        raise NotImplementedError("Not yet implemented")

    def _readline_raw(self):
        raise NotImplementedError("Not yet implemented")


console = ConsoleImpl()
Console  = console.init

__all__ = [Console]

