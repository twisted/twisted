"""UNIX Process management.
"""

# System Imports
import os, sys

if os.name == 'posix':
    # Inter-process communication and FCNTL fun isn't available on windows.
    import fcntl
    import FCNTL

from twisted.persisted import styles
from twisted.python import log, threadable

# Sibling Imports
import abstract, main
from main import CONNECTION_LOST

def reapProcess(*args):
    """Reap as many processes as possible (without blocking) via waitpid.

    This is called when sigchild is caught or a Process object loses its
    "connection" (stdout is closed) This ought to result in reaping all zombie
    processes, since it will be called twice as often as it needs to be.

    (Unfortunately, this is a slightly experimental approach, since UNIX
    has no way to be really sure that your process is going to go away w/o
    blocking.  I don't want to block.)
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
        self.proc = proc

    # Copy relevant parts of the protocol
    def writeSomeData(self, data):
        """Write some data to the open process.
        """
        try:
            return os.write(self.proc.stdin, self.unsent)
        except IOError, io:
            if io.args[0] == errno.EAGAIN:
                return 0
            return CONNECTION_LOST
        except OSError, ose:
            if ose.errno == errno.EPIPE:
                return CONNECTION_LOST
            raise

    def doRead(self):
        """This will raise an exception, as doRead should never be called.
        """
        raise "doRead is illegal on a processWriter"

    def connectionLost(self):
        """See abstract.FileDescriptor.connectionLost.
        """
        abstract.FileDescriptor.connectionLost(self)
        os.close(self.proc.stdin)

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
        self.proc = proc

    def fileno(self):
        """Return the fileno() of my process's stderr.
        """
        return self.proc.stderr.fileno()

    def doRead(self):
        """Call back to my process's doError.
        """
        return self.proc.doError()

    def connectionLost(self):
        """I close my process's stderr.
        """
        abstract.FileDescriptor.connectionLost(self)
        self.proc.stderr.close()
        del self.proc


class Process(abstract.FileDescriptor, styles.Ephemeral):
    """An operating-system Process.
    
    This represents an operating-system process with standard input,
    standard output, and standard error streams connected to it.

    On UNIX, this is implemented using fork(), exec(), pipe() and fcntl().
    These calls may not exist elsewhere so this code is not cross-platform.
    (also, windows can only select on sockets...)
    """
    def __init__(self, command, args, environment):
        """Initialize a Process object.

        Actual spawning of the process is deferred, to be sure that it happens
        in the main thread.
        """
        # I can't initialize immediately because I need to garuantee
        # that this happens in the main thread, so that process
        # reaping can happen there too.  This means that processes are
        # in an inconsistent state when they're initialized.
        threadable.dispatchOS(self, self.startProcess, command, args,
                              environment)

    def startProcess(self, command, args, environment):
        """Spawn an operating-system process.

        This is where the hard work of disconnecting all currently open files /
        forking / executing the new process happens.  (This is executed
        automatically when a Process is instantiated.)
        """
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
                for fd in range(3, 256):
                    try:    os.close(fd)
                    except: pass
                os.chdir(os.path.dirname(os.path.abspath(command)))
                os.execvpe(command, args, environment)
            except:
                # If there are errors, bail and try to write something
                # descriptive to stderr.
                stderr = os.fdopen(2,'w')
                traceback.print_exc(file=stderr)
                stderr.flush()
                for fd in range(3):
                    os.close(fd)
            os._exit(1)

        self.status = -1
        for fd in stdout_write, stderr_write, stdin_read:
            os.close(fd)
        for fd in (stdout_read, stderr_read):
            fcntl.fcntl(fd, FCNTL.F_SETFL, FCNTL.O_NONBLOCK)
        self.stdout = os.fdopen(stdout_read, 'r')
        self.stderr = os.fdopen(stderr_read, 'r')
        self.stdin = stdin_write
        # ok now I really have a fileno()
        self.writer = ProcessWriter(self)
        err = ProcessError(self)
        err.startReading()
        self.startReading()
        self.connected = 1

    def closeStdin(self):
        """Call this to close standard input on this process.
        """
        self.writer.loseConnection()

    def doError(self):
        """Called when my standard error stream is ready for reading.
        """
        try:
            output = self.stderr.read()
        except IOError, ioe:
            if ioe.args[0] == errno.EAGAIN:
                return
            return CONNECTION_LOST
        if not output:
            return CONNECTION_LOST
        self.handleError(output)

    def doRead(self):
        """Called when my standard output stream is ready for reading.
        """

        try:
            output = self.stdout.read()
        except IOError, ioe:
            if ioe.args[0] == errno.EAGAIN:
                return
            else:
                return CONNECTION_LOST
        if not output:
            return CONNECTION_LOST
        self.handleChunk(output)

    def doWrite(self):
        """Called when my standard output stream is ready for writing.

        This will only happen in the case where the pipe to write to is broken.
        """
        return CONNECTION_DONE

    def write(self,data):
        """Call this to write to standard input on this process.
        """
        self.writer.write(data)

    def fileno(self):
        """This returns the file number of standard output on this process.
        """
        return self.stdout.fileno()

    def connectionLost(self):
        """I call this to clean up when one or all of my connections has died.
        """
        abstract.FileDescriptor.connectionLost(self)
        self.stdout.close()
        self.closeStdin()
        del self.writer
        threadable.dispatchOS(self, reapProcess)


if os.name != 'posix':
    # Win32 l0sers unite
    class Process:
        """Non-implementation of Process, for win32.
        """
        def __init__(self, *args, **kw):
            raise "Processes unsupported on non-POSIX systems"
