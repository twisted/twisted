
# Twisted, the Framework of Your Internet
# Copyright (C) 2001 Matthew W. Lefkowitz
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
twisted.log: Logfile and multi-threaded file support.
"""


import sys
import os
import string
import cStringIO
import time
import threadable
import failure


StringIO = cStringIO
del cStringIO

def _no_log_output(func, *args, **kw):
    io = StringIO.StringIO()
    old = sys.stdout
    sys.stdout = io
    try:
        result = apply(func, args, kw)
        return result, io.getvalue()
    finally:
        sys.stdout = old


def _log_output(func, *args, **kw):
    io = Output()
    logOwner.own(io)
    try:
        result = apply(func, args, kw)
        return result, io.getvalue()
    finally:
        logOwner.disown(io)


def output(func, *args, **kw):
    return apply([_no_log_output, _log_output]
                 [isinstance(sys.stdout, Log)],
                 (func,)+args,kw)


file_protocol = ['close', 'closed', 'fileno', 'flush', 'mode', 'name', 'read',
                 'readline', 'readlines', 'seek', 'softspace', 'tell',
                 'write', 'writelines']

# Prevent logfile from being erased on reload.  This only works in cpython.
try:
    logfile
except NameError:
    logfile = sys.stdout

def write(stuff):
    """Write some data to the log."""
    logfile.write(str(stuff))
    logfile.flush()

def msg(stuff):
    """Write some data to the log (a linebreak will be appended)."""
    logfile.write(str(stuff) + os.linesep)
    logfile.flush()

def err(stuff):
    """Write a failure to the log.
    """
    if isinstance(stuff, failure.Failure):
        stuff.printTraceback(file=logfile)
    else:
        msg(stuff)
def deferr():
    """Write the default failure (the current exception) to the log.
    """
    err(failure.Failure())

class Logger:
    """
    This represents a class which may 'own' a log. Used by subclassing.
    """
    written = 1
    def log(self,bytes):
        if not bytes: return
        written = self.written
        if bytes[-1]=='\n':
            self.written = self.written+1
            bytes = string.replace(bytes[:-1],'\n','\n'+self.__prefix())+'\n'
        else:
            bytes = string.replace(bytes,'\n','\n'+self.__prefix())
        if written:
            bytes = self.__prefix()+bytes
            self.written = self.written-1
        # TODO: make this cache everything after the last newline so
        # that multiple threads using "print x, y" style logging get x
        # and y on the same line.
        return bytes

    def __prefix(self):
        y,mon,d,h,min, i,g,no,re = time.localtime(time.time())
        return ("%0.2d/%0.2d/%0.4d %0.2d:%0.2d [%s] " %
                 (d,mon,y,h,min , self.logPrefix()))

    def logPrefix(self):
        """
        Override this method to insert custom logging behavior.  Its
        return value will be inserted in front of every line.  It may
        be called more times than the number of output lines.
        """
        return '-'


class Output:
    """
    This represents a class which traps output.
    """
    def __init__(self):
        self.io = StringIO.StringIO()


    def log(self, bytes):
        self.io.write(bytes)


    def getvalue(self):
        return self.io.getvalue()


class LogOwner:
    """Allow object to register themselves as owners of the log."""

    def __init__(self):
        self.owners = []
        self.defaultOwner = Logger()

    def own(self, owner):
        """Set an object as owner of the log."""
        if owner is not None:
            self.owners.append(owner)

    def disown(self, owner):
        """Remove an object as owner of the log."""
        if owner is not None:
            x = self.owners.pop()
            assert x is owner, "Bad disown"

    def owner(self):
        """Return the owner of the log."""
        try:
            return self.owners[-1]
        except:
            return self.defaultOwner


class ThreadedLogOwner:
    """Allow object to register themselves as owners of the log, per thread."""

    def __init__(self):
        import thread
        self.threadId = thread.get_ident
        self.ownersPerThread = {}
        self.defaultOwner = Logger()

    def own(self, owner):
        """Set an object as owner of the log."""
        if owner is not None:
            i = self.threadId()
            owners = self.ownersPerThread.get(i,[])
            owners.append(owner)
            self.ownersPerThread[i] = owners

    def disown(self, owner):
        """Remove an object as owner of the log."""
        if owner is not None:
            i = self.threadId()
            owners = self.ownersPerThread[i]
            x = owners.pop()
            assert x is owner, "Bad disown: %s != %s" % (x, owner)
            if not owners: del self.ownersPerThread[i]

    def owner(self):
        """Return the owner of the log."""
        i = self.threadId()
        try:
            return self.ownersPerThread[i][-1]
        except (KeyError, IndexError):
            return self.defaultOwner


class Log:
    """
    This will create a Log file (intended to be written to with
    'print', but usable from anywhere that a file is) from a file.
    """

    synchronized = ['write', 'writelines']

    def __init__(self, file, ownable):
        self.file = file

    def __getattr__(self, attr):
        if attr in file_protocol:
            return getattr(self.file, attr)
        else:
            raise AttributeError, attr
    
    def __setattr__(self, attr, value):
        if attr in file_protocol:
            setattr(self.file, attr, value)
        else:
            self.__dict__[attr] = value
    
    def write(self,bytes):
        if not bytes:
            return
        logger = logOwner.owner()
        if logger:
            bytes = logger.log(bytes)
        if not bytes:
            return
        self.file.write(bytes)
        self.file.flush()

    def writelines(self, lines):
        for line in lines:
            self.write(line)


# Make sure we have some basic logging setup.  This only works in cpython.
try:
    logOwner
except NameError:
    logOwner = LogOwner()

    
def _threaded_msg(stuff):
    loglock.acquire()
    real_msg(stuff)
    loglock.release()

def initThreads():
    import thread
    global logOwner, real_msg, msg, loglock
    oldLogOwner = logOwner
    logOwner = ThreadedLogOwner()
    logOwner.ownersPerThread[logOwner.threadId()] = oldLogOwner.owners
    real_msg = msg
    msg = _threaded_msg
    loglock = thread.allocate_lock()

threadable.whenThreaded(initThreads)

def startLogging(file):
    """Initialize logging to a specified file."""
    global logfile
    logfile = sys.stdout = sys.stderr = Log(file, logOwner)
    msg("Log opened.")



__all__ = ["logOwner", "Log", "Logger", "startLogging", "msg", "write"]
