# -*- test-case-name: twisted.test.test_process -*-

# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.


"""UNIX Process management.

Do NOT use this module directly - use reactor.spawnProcess() instead.

Maintainer: U{Itamar Shtull-Trauring<mailto:twisted@itamarst.org>}
"""

# System Imports
import os, sys, traceback, select, errno, struct, cStringIO, types, signal

try:
    import pty
except ImportError:
    pty = None

try:
    import fcntl, termios
except ImportError:
    fcntl = None

from twisted.persisted import styles
from twisted.python import log, failure
from twisted.python.util import switchUID
from twisted.internet import protocol
from twisted.internet.error import ProcessExitedAlready

# Sibling Imports
import abstract, fdesc, error
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
        log.msg('Failed to reap %d:' % pid)
        log.err()
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


def detectLinuxBrokenPipeBehavior():
    global brokenLinuxPipeBehavior
    r,w = os.pipe()
    os.write(w, 'a')
    reads, writes, exes = select.select([w], [], [], 0)
    if reads:
        # Linux < 2.6.11 says a write-only pipe is readable.
        brokenLinuxPipeBehavior = True
    else:
        brokenLinuxPipeBehavior = False
    os.close(r)
    os.close(w)
    
# Call at import time
detectLinuxBrokenPipeBehavior()

class ProcessWriter(abstract.FileDescriptor):
    """(Internal) Helper class to write into a Process's input pipe.

    I am a helper which describes a selectable asynchronous writer to a
    process's input pipe, including stdin.
    """
    connected = 1
    ic = 0
    enableReadHack = False
    
    def __init__(self, reactor, proc, name, fileno, forceReadHack=False):
        """Initialize, specifying a Process instance to connect to.
        """
        abstract.FileDescriptor.__init__(self, reactor)
        fdesc.setNonBlocking(fileno)
        self.proc = proc
        self.name = name
        self.fd = fileno
        
        if forceReadHack:
            self.enableReadHack = True
        else:
            # Detect if this fd is actually a write-only fd. If it's
            # valid to read, don't try to detect closing via read.
            # This really only means that we cannot detect a TTY's write
            # pipe being closed.
            try:
                os.read(self.fileno(), 0)
            except OSError:
                # It's a write-only pipe end, enable hack
                self.enableReadHack = True
            
        if self.enableReadHack:
            self.startReading()
            
    def fileno(self):
        """Return the fileno() of my process's stdin.
        """
        return self.fd

    # Copy relevant parts of the protocol
    def writeSomeData(self, data):
        """Write some data to the open process.
        """
        try:
            rv = os.write(self.fd, data)
            if rv == len(data) and self.enableReadHack:
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

    def write(self, data):
        self.stopReading()
        abstract.FileDescriptor.write(self, data)

    def doRead(self):
        """The only way a write pipe can become "readable" is at EOF, because the
        child has closed it, and we're using a reactor which doesn't distinguish
        between readable and closed (such as the select reactor).
        
        Except that's not true on linux < 2.6.11. It has the following characteristics:
        write pipe is completely empty => POLLOUT (writable in select)
        write pipe is not completely empty => POLLIN (readable in select)
        write pipe's reader closed => POLLIN|POLLERR (readable and writable in select)
        
        That's what this funky code is for. If linux was not broken, this function could
        be simply "return CONNECTION_LOST".
        
        BUG: We call select no matter what the reactor.
        If the reactor is pollreactor, and the fd is > 1024, this will fail.
        (only occurs on broken versions of linux, though).
        """
        if self.enableReadHack:
            if brokenLinuxPipeBehavior:
                fd = self.fd
                r, w, x = select.select([fd], [fd], [], 0)
                if r and w:
                    return CONNECTION_LOST
            else:
                return CONNECTION_LOST
        else:
            self.stopReading()
        
    def connectionLost(self, reason):
        """See abstract.FileDescriptor.connectionLost.
        """
        abstract.FileDescriptor.connectionLost(self, reason)
        self.proc.childConnectionLost(self.name, reason)


class ProcessReader(abstract.FileDescriptor):
    """ProcessReader

    I am a selectable representation of a process's output pipe, such as
    stdout and stderr.
    """
    connected = 1

    def __init__(self, reactor, proc, name, fileno):
        """Initialize, specifying a process to connect to.
        """
        abstract.FileDescriptor.__init__(self, reactor)
        fdesc.setNonBlocking(fileno)
        self.proc = proc
        self.name = name
        self.fd = fileno
        self.startReading()
        
    def fileno(self):
        """Return the fileno() of my process's stderr.
        """
        return self.fd

    def writeSomeData(self, data):
        # the only time this is actually called is after .loseConnection Any
        # actual write attempt would fail, so we must avoid that. This hack
        # allows us to use .loseConnection on both readers and writers.
        assert data == ""
        return CONNECTION_LOST

    def doRead(self):
        """This is called when the pipe becomes readable.
        """
        return fdesc.readFromFD(self.fd, self.dataReceived)

    def dataReceived(self, data):
        self.proc.childDataReceived(self.name, data)

    def loseConnection(self):
        if self.connected and not self.disconnecting:
            self.disconnecting = 1
            self.stopReading()
            self.reactor.callLater(0, self.connectionLost, failure.Failure(CONNECTION_DONE))
    
    def connectionLost(self, reason):
        """Close my end of the pipe, signal the Process (which signals the
        ProcessProtocol).
        """
        abstract.FileDescriptor.connectionLost(self, reason)
        self.proc.childConnectionLost(self.name, reason)


class Process(styles.Ephemeral):
    """An operating-system Process.

    This represents an operating-system process with arbitrary input/output
    pipes connected to it. Those pipes may represent standard input,
    standard output, and standard error, or any other file descriptor.

    On UNIX, this is implemented using fork(), exec(), pipe()
    and fcntl(). These calls may not exist elsewhere so this
    code is not cross-platform. (also, windows can only select
    on sockets...)
    """

    debug = False
    debug_child = False

    status = -1
    pid = None

    def __init__(self, reactor, command, args, environment, path, proto,
                 uid=None, gid=None, childFDs=None):
        """Spawn an operating-system process.

        This is where the hard work of disconnecting all currently open
        files / forking / executing the new process happens.  (This is
        executed automatically when a Process is instantiated.)

        This will also run the subprocess as a given user ID and group ID, if
        specified.  (Implementation Note: this doesn't support all the arcane
        nuances of setXXuid on UNIX: it will assume that either your effective
        or real UID is 0.)

        @param childFDs: a dictionary mapping fd_in_child to
                         current_fd_in_parent/'r'/'w'.

                         If the value is a number, it specifies one of the
                         parent's fds that will be remapped to the child's
                         fd. This is useful for things like inetd and
                         shell-like file redirection.

                         If it is the string 'r', a pipe will be created and
                         attached to the child at that fd number, and the
                         parent will be able to read from the pipe. This is
                         useful for the child's stdout and stderr.

                         If it is the string 'w', a pipe will be created and
                         attached, and the parent will be able to write into
                         that pipe. This is useful for the child's stdin.

                         If childFDs is not passed, the default behaviour is to
                         use a mapping that opens the usual stdin/stdout/stderr
                         pipes.
        """
        if not proto:
            assert 'r' not in childFDs.values()
            assert 'w' not in childFDs.values()
        if not signal.getsignal(signal.SIGCHLD):
            log.msg("spawnProcess called, but the SIGCHLD handler is not " +
                    "installed. This probably means you have not yet " +
                    "called reactor.run, or called " + 
                    "reactor.run(installSignalHandler=0). You will probably " +
                    "never see this process finish, and it may become a " +
                    "zombie process.")
            # if you see this message during a unit test, look in
            # test-standard.xhtml or twisted.test.test_process.SignalMixin
            # for a workaround

        self.lostProcess = False

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

        self.pipes = {}
        # keys are childFDs, we can sense them closing
        # values are ProcessReader/ProcessWriters

        helpers = {}
        # keys are childFDs
        # values are parentFDs

        if childFDs is None:
            childFDs = {0: "w", # we write to the child's stdin
                        1: "r", # we read from their stdout
                        2: "r", # and we read from their stderr
                        }

        debug = self.debug
        if debug: print "childFDs", childFDs

        # fdmap.keys() are filenos of pipes that are used by the child.
        fdmap = {} # maps childFD to parentFD
        for childFD, target in childFDs.items():
            if debug: print "[%d]" % childFD, target
            if target == "r":
                # we need a pipe that the parent can read from
                readFD, writeFD = os.pipe()
                if debug: print "readFD=%d, writeFD%d" % (readFD, writeFD)
                fdmap[childFD] = writeFD     # child writes to this
                helpers[childFD] = readFD    # parent reads from this
            elif target == "w":
                # we need a pipe that the parent can write to
                readFD, writeFD = os.pipe()
                if debug: print "readFD=%d, writeFD=%d" % (readFD, writeFD)
                fdmap[childFD] = readFD      # child reads from this
                helpers[childFD] = writeFD   # parent writes to this
            else:
                assert type(target) == int, '%r should be an int' % (target,)
                fdmap[childFD] = target      # parent ignores this
        if debug: print "fdmap", fdmap
        if debug: print "helpers", helpers
        # the child only cares about fdmap.values()

        self.pid = os.fork()
        if self.pid == 0: # pid is 0 in the child process

            # do not put *ANY* code outside the try block. The child process
            # must either exec or _exit. If it gets outside this block (due
            # to an exception that is not handled here, but which might be
            # handled higher up), there will be two copies of the parent
            # running in parallel, doing all kinds of damage.

            # After each change to this code, review it to make sure there
            # are no exit paths.

            try:
                # stop debugging, if I am!  I don't care anymore!
                sys.settrace(None)
                # close all parent-side pipes
                self._setupChild(fdmap)
                self._execChild(path, settingUID, uid, gid,
                                command, args, environment)
            except:
                # If there are errors, bail and try to write something
                # descriptive to stderr.
                # XXX: The parent's stderr isn't necessarily fd 2 anymore, or
                #      even still available
                # XXXX: however even libc assumes write(2,err) is a useful
                #       thing to attempt
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
            # Did you read the comment about not adding code here?
            os._exit(1)

        # we are the parent

        if settingUID:
            os.setregid(currgid, curegid)
            os.setreuid(curruid, cureuid)
        self.status = -1 # this records the exit status of the child

        self.proto = proto
        
        # arrange for the parent-side pipes to be read and written
        for childFD, parentFD in helpers.items():
            os.close(fdmap[childFD])

            if childFDs[childFD] == "r":
                reader = ProcessReader(reactor, self, childFD, parentFD)
                self.pipes[childFD] = reader

            if childFDs[childFD] == "w":
                writer = ProcessWriter(reactor, self, childFD, parentFD, forceReadHack=True)
                self.pipes[childFD] = writer

        try:
            # the 'transport' is used for some compatibility methods
            if self.proto is not None:
                self.proto.makeConnection(self)
        except:
            log.err()
        registerReapProcessHandler(self.pid, self)

    def _setupChild(self, fdmap):
        """
        fdmap[childFD] = parentFD

        The child wants to end up with 'childFD' attached to what used to be
        the parent's parentFD. As an example, a bash command run like
        'command 2>&1' would correspond to an fdmap of {0:0, 1:1, 2:1}.
        'command >foo.txt' would be {0:0, 1:os.open('foo.txt'), 2:2}.

        This is accomplished in two steps::

            1. close all file descriptors that aren't values of fdmap.  This means
               0 .. maxfds.

            2. for each childFD::

                 - if fdmap[childFD] == childFD, the descriptor is already in
                   place.  Make sure the CLOEXEC flag is not set, then delete the
                   entry from fdmap.

                 - if childFD is in fdmap.values(), then the target descriptor is
                   busy. Use os.dup() to move it elsewhere, update all
                   fdmap[childFD] items that point to it, then close the
                   original. Then fall through to the next case.

                 - now fdmap[childFD] is not in fdmap.values(), and is free. Use
                   os.dup2() to move it to the right place, then close the
                   original.
        """

        debug = self.debug_child
        if debug:
            #errfd = open("/tmp/p.err", "a", 0)
            errfd = sys.stderr
            print >>errfd, "starting _setupChild"

        destList = fdmap.values()
        try:
            import resource
            maxfds = resource.getrlimit(resource.RLIMIT_NOFILE)[1] + 1
            # OS-X reports 9223372036854775808. That's a lot of fds to close
            if maxfds > 1024:
                maxfds = 1024
        except:
            maxfds = 256

        for fd in range(maxfds):
            if fd in destList:
                continue
            if debug and fd == errfd.fileno():
                continue
            try:    os.close(fd)
            except: pass

        # at this point, the only fds still open are the ones that need to
        # be moved to their appropriate positions in the child (the targets
        # of fdmap, i.e. fdmap.values() )

        if debug: print >>errfd, "fdmap", fdmap
        childlist = fdmap.keys()
        childlist.sort()

        for child in childlist:
            target = fdmap[child]
            if target == child:
                # fd is already in place
                if debug: print >>errfd, "%d already in place" % target
                if fcntl and hasattr(fcntl, 'FD_CLOEXEC'):
                    old = fcntl.fcntl(child, fcntl.F_GETFD)
                    fcntl.fcntl(child,
                                fcntl.F_SETFD, old & ~fcntl.FD_CLOEXEC)
            else:
                if child in fdmap.values():
                    # we can't replace child-fd yet, as some other mapping
                    # still needs the fd it wants to target. We must preserve
                    # that old fd by duping it to a new home.
                    newtarget = os.dup(child) # give it a safe home
                    if debug: print >>errfd, "os.dup(%d) -> %d" % (child,
                                                                   newtarget)
                    os.close(child) # close the original
                    for c,p in fdmap.items():
                        if p == child:
                            fdmap[c] = newtarget # update all pointers
                # now it should be available
                if debug: print >>errfd, "os.dup2(%d,%d)" % (target, child)
                os.dup2(target, child)

        # At this point, the child has everything it needs. We want to close
        # everything that isn't going to be used by the child, i.e.
        # everything not in fdmap.keys(). The only remaining fds open are
        # those in fdmap.values().

        # Any given fd may appear in fdmap.values() multiple times, so we
        # need to remove duplicates first.

        old = []
        for fd in fdmap.values():
            if not fd in old:
                if not fd in fdmap.keys():
                    old.append(fd)
        if debug: print >>errfd, "old", old
        for fd in old:
            os.close(fd)

    def _execChild(self, path, settingUID, uid, gid,
                   command, args, environment):
        if path:
            os.chdir(path)
        # set the UID before I actually exec the process
        if settingUID:
            switchUID(uid, gid)
        os.execvpe(command, args, environment)

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
            log.msg('Failed to reap %d:' % self.pid)
            log.err()
            pid = None
        if pid:
            self.processEnded(status)
            unregisterReapProcessHandler(pid, self)

    def writeToChild(self, childFD, data):
        self.pipes[childFD].write(data)
    
    def closeChildFD(self, childFD):
        # for writer pipes, loseConnection tries to write the remaining data
        # out to the pipe before closing it
        # if childFD is not in the list of pipes, assume that it is already
        # closed
        if self.pipes.has_key(childFD):
            self.pipes[childFD].loseConnection()

    def pauseProducing(self):
        for p in self.pipes.itervalues():
            if isinstance(p, ProcessReader):
                p.stopReading()
 
    def resumeProducing(self):
        for p in self.pipes.itervalues():
            if isinstance(p, ProcessReader):
                p.startReading()

    # compatibility
    def closeStdin(self):
        """Call this to close standard input on this process.
        """
        self.closeChildFD(0)
    def closeStdout(self):
        self.closeChildFD(1)
    def closeStderr(self):
        self.closeChildFD(2)
    def loseConnection(self):
        self.closeStdin()
        self.closeStderr()
        self.closeStdout()

    def write(self,data):
        """Call this to write to standard input on this process.
        
        NOTE: This will silently lose data if there is no standard input.
        """
        if self.pipes.has_key(0):
            self.pipes[0].write(data)

    def registerProducer(self, producer, streaming):
        """Call this to register producer for standard input.

        If there is no standard input producer.stopProducing() will
        be called immediately.
        """
        if self.pipes.has_key(0):
            self.pipes[0].registerProducer(producer, streaming)
        else:
            producer.stopProducing()

    def unregisterProducer(self):
        """Call this to unregister producer for standard input."""
        if self.pipes.has_key(0):
            self.pipes[0].unregisterProducer()
    
    def writeSequence(self, seq):
        """Call this to write to standard input on this process.

        NOTE: This will silently lose data if there is no standard input.
        """
        if self.pipes.has_key(0):
            self.pipes[0].writeSequence(seq)

    def childDataReceived(self, name, data):
        self.proto.childDataReceived(name, data)
        
    def signalProcess(self, signalID):
        if signalID in ('HUP', 'STOP', 'INT', 'KILL', 'TERM'):
            signalID = getattr(signal, 'SIG'+signalID)
        if self.pid is None:
            raise ProcessExitedAlready
        os.kill(self.pid, signalID)

    def processEnded(self, status):
        # this is called when the child terminates (SIGCHLD)
        self.status = status
        self.lostProcess = True
        self.pid = None
        #for fd, helper in self.pipes.items():
        #    helper.connectionLost(None)
        ##self.closeStdin()
        self.maybeCallProcessEnded()

    def childConnectionLost(self, childFD, reason):
        # this is called when one of the helpers (ProcessReader or
        # ProcessWriter) notices their pipe has been closed
        os.close(self.pipes[childFD].fileno())
        del self.pipes[childFD]
        try:
            self.proto.childConnectionLost(childFD)
        except:
            log.err()
        self.maybeCallProcessEnded()

    def maybeCallProcessEnded(self):
        # we don't call ProcessProtocol.processEnded until:
        #  the child has terminated, AND
        #  all writers have indicated an error status, AND
        #  all readers have indicated EOF
        # This insures that we've gathered all output from the process.
        if self.pipes:
            #print "maybe, but pipes still", self.pipes.keys()
            return
        if not self.lostProcess:
            #print "maybe, but haven't .lostProcess yet"
            self.reapProcess()
            return
        try:
            exitCode = sig = None
            if self.status != -1:
                if os.WIFEXITED(self.status):
                    exitCode = os.WEXITSTATUS(self.status)
                else:
                    sig = os.WTERMSIG(self.status)
            else:
                pass # don't think this can happen
            if exitCode or sig:
                e = error.ProcessTerminated(exitCode, sig, self.status)
            else:
                e = error.ProcessDone(self.status)
            if self.proto is not None:
                self.proto.processEnded(failure.Failure(e))
                self.proto = None
        except:
            log.err()

    def __repr__(self):
        return "<%s pid=%s status=%s>" % (self.__class__.__name__,
                                          self.pid, self.status)

class PTYProcess(abstract.FileDescriptor, styles.Ephemeral):
    """An operating-system Process that uses PTY support."""
    status = -1
    pid = None
    
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
                if hasattr(termios, 'TIOCNOTTY'):
                    try:
                        fd = os.open("/dev/tty", os.O_RDWR | os.O_NOCTTY)
                    except OSError:
                        pass
                    else:
                        try:
                            fcntl.ioctl(fd, termios.TIOCNOTTY, '')
                        except:
                            pass
                        os.close(fd)
                    
                os.setsid()
                
                if hasattr(termios, 'TIOCSCTTY'):
                    fcntl.ioctl(slavefd, termios.TIOCSCTTY, '')
                
                for fd in range(3):
                    if fd != slavefd:
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
                    switchUID(uid, gid)
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
            log.err()
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
            if e.errno == errno.ECHILD: # no child process
                pid = None
            else:
                raise
        except:
            log.err()
            pid = None
        if pid:
            self.processEnded(status)
            unregisterReapProcessHandler(self.pid, self)

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
                self.proto = None
            except:
                log.err()

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

    def __repr__(self):
        return "<%s pid=%s status=%s>" % (self.__class__.__name__,
                                          self.pid, self.status)
