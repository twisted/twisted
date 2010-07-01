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


import errno
import pywintypes
import win32api
import win32console



_ENABLE_NORMAL_MODE = win32console.ENABLE_ECHO_INPUT | win32console.ENABLE_LINE_INPUT
_ENABLE_WINDOW_INPUT = win32console.ENABLE_WINDOW_INPUT


class ConIn(object):
    """
    I implement a file like object that supports asyncronous reading
    from a console.

    This class should be considered a singleton, don't instantiate new
    objects and instead use the global stdin object.
    """
    
    def __init__(self, handle):
        # handle should be std handle for STD_INPUT_HANDLE
        self.handle = handle

        # The code page in use
        # I assume that this does not change
        self.cp = "cp%d" % win32console.GetConsoleCP()

        # The temporary (accumulation) buffer used to store the data as
        # it arrives from the console
        self._buf = []
        
        # The buffer used to store data ready to be read
        self.buffer = ''

        # Enable the receiving of input records when the console
        # window (buffer) is changed
        defaultMode = handle.GetConsoleMode()
        handle.SetConsoleMode(defaultMode | _ENABLE_WINDOW_INPUT)

        # The callback to be called upon the receiving of a windows
        # change record
        self._windowChangeCallback = None
        
        # To optimize the code we use different functions for normal
        # and raw mode
        self.read = self._read
        self.readline = self._readline

    #
    # termios interface
    #
    def enableRawMode(self, enabled=True):
        """
        Enable raw mode.

        XXX check me
        """

        # Flush buffer
        self._buf = []
        self.buffer = ''

        # Flush the console buffer, too
        self.handle.FlushConsoleInputBuffer()

        mode = self.handle.GetConsoleMode()

        if enabled:
            self.read = self._read_raw
            self.readline = self._readline_raw

            # Set mode on the console, too
            # XXX check me (this seems not to work)
            self.handle.SetConsoleMode(mode & ~_ENABLE_NORMAL_MODE)
        else:
            self.read = self._read
            self.readline = self._readline

            # Set mode on the console, too
            self.handle.SetConsoleMode(mode | _ENABLE_NORMAL_MODE)

    def setWindowChangeCallback(self, callback):
        """
        callback is called when the console window buffer is
        changed.

        Note: WINDOW_BUFFER_SIZE_EVENT is only raised when changing
        the window *buffer* size from the console menu
        """

        self._windowChangeCallback = callback


    #
    # File object interface
    #
    def close(self):
        win32api.CloseHandle(self.handle)

    def flush(self):
        # Flush both internal buffer and system console buffer
        self.buffer = ''
        self._buf = []

        self.handle.FlushConsoleInputBuffer() 

    def fileno(self):
        return self.handle

    def isatty(self): 
        return True

    def next(self):
        raise NotImplementedError("Not yet implemented")

    def _read(self, size=None):
        """
        Read size bytes from the console.
        An exception is raised when the operation would block.

        XXX Just return the empty string instead of raising an exception?
        """

        # This can fail if stdout has been closed
        info = stdout.handle.GetConsoleScreenBufferInfo()
        rowSize = info["MaximumWindowSize"].X 

        # Initialize the current cursor position
        if not self._buf:
            self.pos = info["CursorPosition"]

        while 1:
            n = self.handle.GetNumberOfConsoleInputEvents()
            if n == 0:
                break

            records = self.handle.ReadConsoleInput(n)

            # Process input
            for record in records:
                if record.EventType == win32console.WINDOW_BUFFER_SIZE_EVENT:
                    rowSize = record.Size.X
                    if self._windowChangeCallback:
                        self._windowChangeCallback()
                if record.EventType != win32console.KEY_EVENT \
                        or not record.KeyDown:
                    continue

                char = record.Char
                n = record.RepeatCount
                if char == '\b':
                    pos = stdout.handle.GetConsoleScreenBufferInfo()["CursorPosition"]

                    # Move the cursor
                    x = pos.X - n
                    if x >= 0:
                        pos.X = x
                    # XXX assuming |x| < rowSize (I'm lazy)
                    elif pos.Y > self.pos.Y:
                        pos.X = rowSize - 1
                        pos.Y -= 1

                    stdout.handle.SetConsoleCursorPosition(pos)
                    stdout.handle.WriteConsoleOutputCharacter(' ' * n, pos)

                    # Delete the characters from accumulation buffer
                    self._buf = self._buf[:-n]
                    continue
                elif char == '\0':
                    vCode = record.VirtualKeyCode
                    # XXX TODO handle keyboard navigation
                    continue
                elif char == '\r':
                    char = '\n' * n

                    self._buf.append(char)
                    stdout.handle.WriteConsole(char) # do echo

                    # We have some data ready to be read
                    self.buffer = ''.join(self._buf)
                    self._buf = []
                    self.pos = info["CursorPosition"]

                    if size is None:
                        size = len(self.buffer)

                    data = self.buffer[:size]
                    self.buffer = self.buffer[size:]
                    return data

                char = char * n
                data = char.encode(self.cp)
                stdout.handle.WriteConsole(data) # do echo

                self._buf.append(data)

        if self.buffer:
            data = self.buffer[:size]
            self.buffer = self.buffer[size:]
            return data
        else:
            raise IOError(errno.EAGAIN)

    def _read_raw(self, size=None):
        """
        Read size bytes from the console, in raw mode.

        XXX check me.
        """

        while 1: # XXX is this loop really needed?
            n = self.handle.GetNumberOfConsoleInputEvents()
            if n == 0:
                break

            records = self.handle.ReadConsoleInput(n)

            # Process input
            for record in records:
                if record.EventType == win32console.WINDOW_BUFFER_SIZE_EVENT:
                    if self._windowChangeCallback:
                        self._windowChangeCallback()
                if record.EventType != win32console.KEY_EVENT \
                        or not record.KeyDown:
                    continue

                char = record.Char
                n = record.RepeatCount
                if char == '\0':
                    vCode = record.VirtualKeyCode
                    # XXX TODO handle keyboard navigation
                    continue
                elif char == '\r':
                    char = '\n' * n

                char = char * n
                data = char.encode(self.cp)

                self._buf.append(data)


        buffer = ''.join(self._buf)
        if buffer:
            if size is None:
                size = len(buffer)

            data = buffer[:size]
            # Keep the remaining data in the accumulation buffer
            self._buf = [buffer[size:]]
            return data
        else:
            return ''

    def _readline(self, size=None):
        # XXX check me
        return self._read(size)

    def _readline_raw(self, size=None):
        raise NotImplementedError("Not yet implemented")



class ConOut(object):
    """
    I implement a file like object that supports asyncronous writing
    to a console.

    This class should be considered private, don't instantiate new
    objects and instead use the global stdout and stderr objects.

    Note that there is no option to make WriteConsole non blocking,
    but is seems that this function does not block at all.
    When a blocking operation like text selection is in action, the
    process is halted.
    """

    def __init__(self, handle):
        # handle should be std handle for STD_OUTPUT_HANDLE or STD_ERROR_HANDLE
        self.handle = handle


    #
    # File object interface
    #
    def close(self):
        win32api.CloseHandle(self.handle)

    def flush(self):
        # There is no buffering
        pass

    def fileno(self):
        return self.handle

    def isatty(self): 
        return True

    def write(self, s):
        """
        Write a string to the console.
        """

        return self.handle.WriteConsole(s)

    def writelines(self, seq):
        """
        Write a sequence of strings to the console.
        """

        s = ''.join(seq)
        return self.handle.WriteConsole(s)



# The public interface of this module
# XXX TODO replace sys.stdin, sys.stdout and sys.stderr?
stdin = ConIn(win32console.GetStdHandle(win32console.STD_INPUT_HANDLE))
stdout = ConOut(win32console.GetStdHandle(win32console.STD_OUTPUT_HANDLE))
stderr = ConOut(win32console.GetStdHandle(win32console.STD_ERROR_HANDLE))


__all__ = [stdin, stdout, stderr]
