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

Maintainer: U{Itamar Shtull-Trauring<mailto:twisted@itamarst.org>}
"""

# System Imports
import os, sys, traceback, select, errno, struct, cStringIO, types, signal

try:
    import pty
    import fcntl, termios
except:
    pty = None

try:
    import pwd, grp
    from os import setgroups
    def initgroups(uid, primaryGid):
        username = pwd.getpwuid(uid)[0]
        l=[primaryGid]
        for groupname, password, gid, userlist in grp.getgrall():
            if username in userlist:
                l.append(gid)
        setgroups(l)
except:
    def initgroups(uid, primaryGid):
        pass

def switch_uid(uid, gid):
    os.setgid(gid)
    initgroups(uid, gid)
    os.setuid(uid)

from twisted.persisted import styles
from twisted.python import log, failure
from twisted.internet import protocol

# Sibling Imports
import abstract, main, fdesc, error
from main import CONNECTION_LOST, CONNECTION_DONE


reapProcessHandlers = {}

def reapAllProcesses():
    """Reap all registered processes.
    """
    for process in reapProcessHandlers.values():
        process.reapProcess()

def registerReapProcessHandler(pid, process):
    if reapProcessHandlers.has_key(pid):
        raise RuntimeError
    try:
        aux_pid, status = os.waitpid(pid, os.WNOHANG)
    except:
        log.deferr()
        aux_pid = None
    if aux_pid:
        process.processEnded(status)
    else:
        reapProcessHandlers[pid] = process


def unregisterReapProcessHandler(pid, process):
    if not (reapProcessHandlers.has_key(pid)
            and reapProcessHandlers[pid] == process):
        raise RuntimeError
    del reapProcessHandlers[pid]

from twisted.internet.abstract import _BufferBufferMixin
class ProcessWriter(_BufferBufferMixin, abstract.FileDescriptor, styles.Ephemeral):
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

    def write(self, data):
        self.stopReading()
        abstract.FileDescriptor.write(self, data)

    def writeSomeData(self, data):
        """Write some data to the open process.
        """
        try:
            rv = os.write(self.proc.stdin, data)
            if rv == len(data):
                self.startReading()
            return rv
        except IOError, io:
            if io.args[0] == errno.EAGAIN:
                return 0
            return CONNECTION_LOST
        except OSError, ose:
            if ose.errno == errno.EPIPE:
                return CONNECTION_LOST
            if ose.errno == errno.EAGAIN: # MacOS-X does this
                return 0
            raise

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

class ProcessExitedAlready(Exception):
    """The process has already excited, and the operation requested can no longer be performed."""
    pass

class Process(abstract.FileDescriptor, styles.Ephemeral):
    """An operating-system Process.

    This represents an operating-system process with standard input,
    standard output, and standard error streams connected to it.

    On UNIX, this is implemented using fork(), exec(), pipe()
    and fcntl(). These calls may not exist elsewhere so this
    code is not cross-platform. (also, windows can only select
    on sockets...)
    """

    def __init__(self, reactor, command, args, environment, path, proto,
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
        abstract.FileDescriptor.__init__(self, reactor)
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
        self.pid = os.fork()
        if self.pid == 0: # pid is 0 in the child process
            # stop debugging, if I am!  I don't care anymore!
            sys.settrace(None)
            # Destroy my stdin / stdout / stderr (in that order)
            try:
                os.dup2(stdin_read, 0)
                os.dup2(stdout_write, 1)
                os.dup2(stderr_write, 2)
                # XXX TODO FIXME: 256 is a magic number here; really we need a
                # way of saying "close all open FDs except 0, 1, 2".  This will
                # fail in a surprising and subtle way if the current process
                # has more than 256 FDs open.  On linux this would be
                # "[os.close(int(fd)) for fd in os.listdir('/proc/self/fd')]"
                # but I seriously doubt that's portable.
                for fd in range(3, 256):
                    try:    os.close(fd)
                    except: pass
                if path:
                    os.chdir(path)
                # set the UID before I actually exec the process
                if settingUID:
                    switch_uid(uid, gid)
                os.execvpe(command, args, environment)
            except:
                # If there are errors, bail and try to write something
                # descriptive to stderr.
                try:
                    stderr = os.fdopen(2,'w')
                    stderr.write("Upon execvpe %s %s in environment %s\n:" %
                                 (command, str(args),
                                  "id %s" % id(environment)))
                    traceback.print_exc(file=stderr)
                    stderr.flush()
                    for fd in range(3):
                        os.close(fd)
                except:
                    pass # make *sure* the child terminates
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
        registerReapProcessHandler(self.pid, self)

    def reapProcess(self):
        """Try to reap a process (without blocking) via waitpid.

        This is called when sigchild is caught or a Process object loses its
        "connection" (stdout is closed) This ought to result in reaping all
        zombie processes, since it will be called twice as often as it needs
        to be.

        (Unfortunately, this is a slightly experimental approach, since
        UNIX has no way to be really sure that your process is going to
        go away w/o blocking.  I don't want to block.)
        """
        try:
            pid, status = os.waitpid(self.pid, os.WNOHANG)
        except:
            log.deferr()
            pid = None
        if pid:
            self.processEnded(status)
            del reapProcessHandlers[pid]

    def closeStdin(self):
        """Call this to close standard input on this process.
        """
        if hasattr(self, "writer"):
            self.writer.loseConnection()

    def closeStderr(self):
        """Close stderr."""
        if hasattr(self, "err"):
             self.err.stopReading()
             self.err.connectionLost(None)

    def closeStdout(self):
        """Close stdout."""
        if not self.lostOutConnection:
            self.stopReading()
            self.connectionLost(None)

    def loseConnection(self):
        self.closeStdin()
        self.closeStderr()
        self.closeStdout()

    def signalProcess(self, signalID):
        if signalID in ('HUP', 'STOP', 'INT', 'KILL'):
            signalID = getattr(signal, 'SIG'+signalID)
        if self.pid is None:
            raise ProcessExitedAlready
        os.kill(self.pid, signalID)

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
    lostProcess = 0

    def maybeCallProcessEnded(self):
        if (self.lostErrorConnection and
            self.lostOutConnection and
            self.lostInConnection):
            if self.lostProcess:
                try:
                    exitCode = sig = None
                    if self.status != -1:
                        if os.WIFEXITED(self.status):
                            exitCode = os.WEXITSTATUS(self.status)
                        else:
                            sig = os.WTERMSIG(self.status)
                    else:
                        pass # wonder when this happens
                    if exitCode or sig:
                        e = error.ProcessTerminated(exitCode, sig, self.status)
                    else:
                        e = error.ProcessDone(self.status)
                    self.proto.processEnded(failure.Failure(e))
                except:
                    log.deferr()
            else:
                self.reapProcess()

    def processEnded(self, status):
        self.status = status
        self.lostProcess = 1
        self.pid = None
        self.closeStdin()
        self.maybeCallProcessEnded()

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


class PTYProcess(abstract.FileDescriptor, styles.Ephemeral):
    """An operating-system Process that uses PTY support."""

    def __init__(self, reactor, command, args, environment, path, proto,
                 uid=None, gid=None, usePTY=None):
        """Spawn an operating-system process.

        This is where the hard work of disconnecting all currently open
        files / forking / executing the new process happens.  (This is
        executed automatically when a Process is instantiated.)

        This will also run the subprocess as a given user ID and group ID, if
        specified.  (Implementation Note: this doesn't support all the arcane
        nuances of setXXuid on UNIX: it will assume that either your effective
        or real UID is 0.)
        """
        if not pty and type(usePTY) not in (types.ListType, types.TupleType):
            # no pty module and we didn't get a pty to use
            raise NotImplementedError, "cannot use PTYProcess on platforms without the pty module."
        abstract.FileDescriptor.__init__(self, reactor)
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
        if type(usePTY) in (types.TupleType, types.ListType):
            masterfd, slavefd, ttyname = usePTY
        else:
            masterfd, slavefd = pty.openpty()
            ttyname = os.ttyname(slavefd)
        pid = os.fork()
        self.pid = pid
        if pid == 0: # pid is 0 in the child process
            try:
                sys.settrace(None)
                os.close(masterfd)
                os.setsid()
                if hasattr(termios, 'TIOCSCTTY'):
                    fcntl.ioctl(slavefd, termios.TIOCSCTTY, '')
                else:
                    for fd in range(3):
                        if fd != slavefd:
                            os.close(fd)
                    fd = os.open(ttyname, os.O_RDWR)
                    os.close(fd)

                os.dup2(slavefd, 0) # stdin
                os.dup2(slavefd, 1) # stdout
                os.dup2(slavefd, 2) # stderr

                if path:
                    os.chdir(path)
                for fd in range(3, 256):
                    try:    os.close(fd)
                    except: pass

                # set the UID before I actually exec the process
                if settingUID:
                    switch_uid(uid, gid)
                os.execvpe(command, args, environment)
            except:
                stderr = os.fdopen(1, 'w')
                stderr.write("Upon execvpe %s %s in environment %s:\n" %
                             (command, str(args),
                              "id %s" % id(environment)))
                traceback.print_exc(file=stderr)
                stderr.flush()
            os._exit(1)
        assert pid!=0
        os.close(slavefd)
        fdesc.setNonBlocking(masterfd)
        self.fd=masterfd
        self.startReading()
        self.connected = 1
        self.proto = proto
        self.lostProcess = 0
        self.status = -1
        try:
            self.proto.makeConnection(self)
        except:
            log.deferr()
        registerReapProcessHandler(self.pid, self)

    def reapProcess(self):
        """Try to reap a process (without blocking) via waitpid.

        This is called when sigchild is caught or a Process object loses its
        "connection" (stdout is closed) This ought to result in reaping all
        zombie processes, since it will be called twice as often as it needs
        to be.

        (Unfortunately, this is a slightly experimental approach, since
        UNIX has no way to be really sure that your process is going to
        go away w/o blocking.  I don't want to block.)
        """
        try:
            pid, status = os.waitpid(self.pid, os.WNOHANG)
        except OSError, e:
            if e.errno == 10: # no child process
                pid = None
            else:
                raise
        except:
            log.deferr()
            pid = None
        if pid:
            self.processEnded(status)
            del reapProcessHandlers[pid]

    # PTYs do not have stdin/stdout/stderr. They only have in and out, just
    # like sockets. You cannot close one without closing off the entire PTY.
    def closeStdin(self):
        pass

    def closeStdout(self):
        pass

    def closeStderr(self):
        pass

    def signalProcess(self, signalID):
        if signalID in ('HUP', 'STOP', 'INT', 'KILL'):
            signalID = getattr(signal, 'SIG'+signalID)
        os.kill(self.pid, signalID)

    def processEnded(self, status):
        self.status = status
        self.lostProcess += 1
        self.maybeCallProcessEnded()

    def doRead(self):
        """Called when my standard output stream is ready for reading.
        """
        try:
            return fdesc.readFromFD(self.fd, self.proto.outReceived)
        except OSError:
            return CONNECTION_LOST

    def fileno(self):
        """This returns the file number of standard output on this process.
        """
        return self.fd

    def maybeCallProcessEnded(self):
        # two things must happen before we call the ProcessProtocol's
        # processEnded method. 1: the child process must die and be reaped
        # (which calls our own processEnded method). 2: the child must close
        # their stdin/stdout/stderr fds, causing the pty to close, causing
        # our connectionLost method to be called. #2 can also be triggered
        # by calling .loseConnection().
        if self.lostProcess == 2:
            try:
                exitCode = sig = None
                if self.status != -1:
                    if os.WIFEXITED(self.status):
                        exitCode = os.WEXITSTATUS(self.status)
                    else:
                        sig = os.WTERMSIG(self.status)
                else:
                    pass # wonder when this happens
                if exitCode or sig:
                    e = error.ProcessTerminated(exitCode, sig, self.status)
                else:
                    e = error.ProcessDone(self.status)
                self.proto.processEnded(failure.Failure(e))
            except:
                log.deferr()

    def connectionLost(self, reason):
        """I call this to clean up when one or all of my connections has died.
        """
        abstract.FileDescriptor.connectionLost(self, reason)
        os.close(self.fd)
        self.lostProcess +=1
        self.maybeCallProcessEnded()

    def writeSomeData(self, data):
        """Write some data to the open process.
        """
        try:
            return os.write(self.fd, data)
        except IOError,io:
            if io.args[0] == errno.EAGAIN:
                return 0
            return CONNECTION_LOST
