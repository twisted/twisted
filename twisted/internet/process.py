# -*- test-case-name: twisted.test.test_process -*-

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

"""UNIX Process management.

Do NOT use this module directly - use reactor.spawnProcess() instead. 
"""

# System Imports
import os, sys, traceback, select, errno

from twisted.persisted import styles
from twisted.python import log, failure

# Sibling Imports
import abstract, main, fdesc
from main import CONNECTION_LOST, CONNECTION_DONE

def reapProcess(*args):
    """Reap as many processes as possible (without blocking) via waitpid.

    This is called when sigchild is caught or a Process object loses its
    "connection" (stdout is closed) This ought to result in reaping all
    zombie processes, since it will be called twice as often as it needs
    to be.

    (Unfortunately, this is a slightly experimental approach, since
    UNIX has no way to be really sure that your process is going to
    go away w/o blocking.  I don't want to block.)
    """
    try:
        os.waitpid(0,os.WNOHANG)
    except:
        pass

class ProcessWriter(abstract.FileDescriptor, styles.Ephemeral):
    """(Internal) Helper class to write to Process's stdin.

    I am a helper which describes a selectable asynchronous writer to a
    process's stdin.
    """
    connected = 1
    ic = 0

    def __init__(self, proc):
        """Initialize, specifying a Process instance to connect to.
        """
        abstract.FileDescriptor.__init__(self)
        self.proc = proc

    # Copy relevant parts of the protocol
    def writeSomeData(self, data):
        """Write some data to the open process.
        """
        try:
            rv = os.write(self.proc.stdin, self.unsent)
            if rv == len(self.unsent):
                self.startReading()
            return rv
        except IOError, io:
            if io.args[0] == errno.EAGAIN:
                return 0
            return CONNECTION_LOST
        except OSError, ose:
            if ose.errno == errno.EPIPE:
                return CONNECTION_LOST
            raise

    def write(self, data):
        self.stopReading()
        abstract.FileDescriptor.write(self, data)

    def doRead(self):
        """This does nothing.
        """
        fd = self.fileno()
        r, w, x = select.select([fd], [fd], [], 0)
        if r and w:
            return CONNECTION_LOST

    def connectionLost(self, reason):
        """See abstract.FileDescriptor.connectionLost.
        """
        abstract.FileDescriptor.connectionLost(self, reason)
        os.close(self.proc.stdin)
        self.proc.inConnectionLost()

    def fileno(self):
        """Return the fileno() of my process's stdin.
        """
        return self.proc.stdin

class ProcessError(abstract.FileDescriptor):
    """ProcessError

    I am a selectable representation of a process's stderr.
    """
    def __init__(self, proc):
        """Initialize, specifying a process to connect to.
        """
        abstract.FileDescriptor.__init__(self)
        self.proc = proc

    def fileno(self):
        """Return the fileno() of my process's stderr.
        """
        return self.proc.stderr

    def doRead(self):
        """Call back to my process's doError.
        """
        return self.proc.doError()

    def connectionLost(self, reason):
        """I close my process's stderr.
        """
        abstract.FileDescriptor.connectionLost(self, reason)
        os.close(self.proc.stderr)
        self.proc.errConnectionLost()
        del self.proc


class Process(abstract.FileDescriptor, styles.Ephemeral):
    """An operating-system Process.

    This represents an operating-system process with standard input,
    standard output, and standard error streams connected to it.

    On UNIX, this is implemented using fork(), exec(), pipe()
    and fcntl(). These calls may not exist elsewhere so this
    code is not cross-platform. (also, windows can only select
    on sockets...)
    """

    def __init__(self, command, args, environment, path, proto,
                 uid=None, gid=None):
        """Spawn an operating-system process.

        This is where the hard work of disconnecting all currently open
        files / forking / executing the new process happens.  (This is
        executed automatically when a Process is instantiated.)

        This will also run the subprocess as a given user ID and group ID, if
        specified.  (Implementation Note: this doesn't support all the arcane
        nuances of setXXuid on UNIX: it will assume that either your effective
        or real UID is 0.)
        """
        abstract.FileDescriptor.__init__(self)
        settingUID = (uid is not None) or (gid is not None)
        if settingUID:
            curegid = os.getegid()
            currgid = os.getgid()
            cureuid = os.geteuid()
            curruid = os.getuid()
            if uid is None:
                uid = cureuid
            if gid is None:
                gid = curegid
            # prepare to change UID in subprocess
            os.setuid(0)
            os.setgid(0)
        stdout_read, stdout_write = os.pipe()
        stderr_read, stderr_write = os.pipe()
        stdin_read,  stdin_write  = os.pipe()
        pid = os.fork()
        if pid == 0: # pid is 0 in the child process
            # stop debugging, if I am!  I don't care anymore!
            sys.settrace(None)
            # Destroy my stdin / stdout / stderr (in that order)
            try:
                for fd in range(3):
                    os.close(fd)
                os.dup(stdin_read)   # should be 0
                os.dup(stdout_write) # 1
                os.dup(stderr_write) # 2
                os.close(stdin_read)
                os.close(stdin_write)
                os.close(stderr_read)
                os.close(stderr_write)
                os.close(stdout_read)
                os.close(stdout_write)
                for fd in range(3, 256):
                    try:    os.close(fd)
                    except: pass
                if path:
                    os.chdir(path)
                # set the UID before I actually exec the process
                if settingUID:
                    os.setuid(uid)
                    os.setgid(gid)
                os.execvpe(command, args, environment)
            except:
                # If there are errors, bail and try to write something
                # descriptive to stderr.
                stderr = os.fdopen(2,'w')
                stderr.write("Upon execvpe %s %s in environment %s\n:" %
                             (command, str(args),
                              "id %s" % id(environment)))
                traceback.print_exc(file=stderr)
                stderr.flush()
                for fd in range(3):
                    os.close(fd)
            os._exit(1)
        if settingUID:
            os.setregid(currgid, curegid)
            os.setreuid(curruid, cureuid)
        self.status = -1
        for fd in stdout_write, stderr_write, stdin_read:
            os.close(fd)
        for fd in (stdout_read, stderr_read, stdin_write):
            fdesc.setNonBlocking(fd)
        self.stdout = stdout_read # os.fdopen(stdout_read, 'r')
        self.stderr = stderr_read # os.fdopen(stderr_read, 'r')
        self.stdin = stdin_write
        # ok now I really have a fileno()
        self.writer = ProcessWriter(self)
        self.writer.startReading()
        self.err = ProcessError(self)
        self.err.startReading()
        self.startReading()
        self.connected = 1
        self.proto = proto
        try:
            self.proto.makeConnection(self)
        except:
            log.deferr()

    def closeStdin(self):
        """Call this to close standard input on this process.
        """
        self.writer.loseConnection()

    def closeStderr(self):
        """Close stderr."""
        self.err.stopReading()
        self.err.connectionLost(None)

    def closeStdout(self):
        """Close stdout."""
        abstract.FileDescriptor.loseConnection(self)

    def loseConnection(self):
        self.closeStdin()
        self.closeStderr()
        self.closeStdout()
    
    def doError(self):
        """Called when my standard error stream is ready for reading.
        """
        return fdesc.readFromFD(self.stderr, self.proto.errReceived)

    def doRead(self):
        """Called when my standard output stream is ready for reading.
        """
        return fdesc.readFromFD(self.stdout, self.proto.outReceived)

    def doWrite(self):
        """Called when my standard output stream is ready for writing.

        This will only happen in the case where the pipe to write to is
        broken.
        """
        return CONNECTION_DONE

    def write(self,data):
        """Call this to write to standard input on this process.
        """
        self.writer.write(data)

    def fileno(self):
        """This returns the file number of standard output on this process.
        """
        return self.stdout

    lostErrorConnection = 0
    lostOutConnection = 0
    lostInConnection = 0

    def maybeCallProcessEnded(self):
        if (self.lostErrorConnection and
            self.lostOutConnection and
            self.lostInConnection):
            try:
                self.proto.processEnded(failure.Failure(CONNECTION_DONE))
            except:
                log.deferr()
            reapProcess()
    
    def inConnectionLost(self):
        try:
            self.proto.inConnectionLost()
        except:
            log.deferr()
        del self.writer
        self.lostInConnection = 1
        self.maybeCallProcessEnded()

    def errConnectionLost(self):
        self.lostErrorConnection = 1
        del self.err
        try:
            self.proto.errConnectionLost()
        except:
            log.deferr()
        self.maybeCallProcessEnded()

    def connectionLost(self, reason):
        """stdout closed.
        """
        self.lostOutConnection = 1
        abstract.FileDescriptor.connectionLost(self, reason)
        os.close(self.stdout)
        try:
            self.proto.outConnectionLost()
        except:
            log.deferr()
        self.maybeCallProcessEnded()


