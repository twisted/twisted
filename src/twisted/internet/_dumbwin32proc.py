# -*- test-case-name: twisted.test.test_process -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Windows Process Management, used with reactor.spawnProcess
"""


import os
import sys

from zope.interface import implementer

import pywintypes

# Win32 imports
import win32api
import win32con
import win32event
import win32file
import win32pipe
import win32process
import win32security

from twisted.internet import _pollingfile, error
from twisted.internet._baseprocess import BaseProcess
from twisted.internet.interfaces import IConsumer, IProcessTransport, IProducer
from twisted.python.win32 import quoteArguments

# Security attributes for pipes
PIPE_ATTRS_INHERITABLE = win32security.SECURITY_ATTRIBUTES()
PIPE_ATTRS_INHERITABLE.bInheritHandle = 1


def debug(msg):
    print(msg)
    sys.stdout.flush()


class _Reaper(_pollingfile._PollableResource):
    def __init__(self, proc):
        self.proc = proc

    def checkWork(self):
        try:
            if (
                win32event.WaitForSingleObject(self.proc.hProcess, 0)
                != win32event.WAIT_OBJECT_0
            ):
                return 0

            exitCode = win32process.GetExitCodeProcess(self.proc.hProcess)

        except pywintypes.error as error:
            if error.args[0] != 6:
                raise
            # I don't know why the process is already closed,
            # since in theory we wait for all the streams to be closed,
            # before closing the process.
            exitCode = 0

        self.proc.processEnded(exitCode)
        self.deactivate()
        return 0


def _findShebang(filename):
    """
    Look for a #! line, and return the value following the #! if one exists, or
    None if this file is not a script.

    I don't know if there are any conventions for quoting in Windows shebang
    lines, so this doesn't support any; therefore, you may not pass any
    arguments to scripts invoked as filters.  That's probably wrong, so if
    somebody knows more about the cultural expectations on Windows, please feel
    free to fix.

    This shebang line support was added in support of the CGI tests;
    appropriately enough, I determined that shebang lines are culturally
    accepted in the Windows world through this page::

        http://www.cgi101.com/learn/connect/winxp.html

    @param filename: str representing a filename

    @return: a str representing another filename.
    """
    with open(filename) as f:
        if f.read(2) == "#!":
            exe = f.readline(1024).strip("\n")
            return exe


def _invalidWin32App(pywinerr):
    """
    Determine if a pywintypes.error is telling us that the given process is
    'not a valid win32 application', i.e. not a PE format executable.

    @param pywinerr: a pywintypes.error instance raised by CreateProcess

    @return: a boolean
    """

    # Let's do this better in the future, but I have no idea what this error
    # is; MSDN doesn't mention it, and there is no symbolic constant in
    # win32process module that represents 193.

    return pywinerr.args[0] == 193


@implementer(IProcessTransport, IConsumer, IProducer)
class Process(_pollingfile._PollingTimer, BaseProcess):
    """
    A process that integrates with the Twisted event loop.

    If your subprocess is a python program, you need to:

     - Run python.exe with the '-u' command line option - this turns on
       unbuffered I/O. Buffering stdout/err/in can cause problems, see e.g.
       http://support.microsoft.com/default.aspx?scid=kb;EN-US;q1903

     - If you don't want Windows messing with data passed over
       stdin/out/err, set the pipes to be in binary mode::

        import os, sys, mscvrt
        msvcrt.setmode(sys.stdin.fileno(), os.O_BINARY)
        msvcrt.setmode(sys.stdout.fileno(), os.O_BINARY)
        msvcrt.setmode(sys.stderr.fileno(), os.O_BINARY)

    @ivar _childPipes: A mapping of file descriptor numbers to
        L{_pollingfile._PollableResource} instances which are used to
        communicate with the subprocess.
        They include the standard file descriptors.
    """

    _childPipes: dict[int, _pollingfile._PollableResource]

    closedNotifies = 0

    def __init__(
        self, reactor, protocol, command, args, environment, path, childFDs=None
    ):
        """
        Create a new child process.
        """
        _pollingfile._PollingTimer.__init__(self, reactor)
        BaseProcess.__init__(self, protocol)

        parentHandles = []
        childPipes = {}

        # security attributes for pipes
        sAttrs = win32security.SECURITY_ATTRIBUTES()
        sAttrs.bInheritHandle = 1

        # create the pipes which will connect to the secondary process
        self.hStdoutR, hStdoutW = win32pipe.CreatePipe(sAttrs, 0)
        self.hStderrR, hStderrW = win32pipe.CreatePipe(sAttrs, 0)
        parentHandles.append(hStdoutW)
        parentHandles.append(hStderrW)
        hStdinR, self.hStdinW = win32pipe.CreatePipe(sAttrs, 0)
        parentHandles.append(hStdinR)

        win32pipe.SetNamedPipeHandleState(
            self.hStdinW, win32pipe.PIPE_NOWAIT, None, None
        )

        # set the info structure for the new process.
        StartupInfo = win32process.STARTUPINFO()
        StartupInfo.hStdOutput = hStdoutW
        StartupInfo.hStdError = hStderrW
        StartupInfo.hStdInput = hStdinR
        StartupInfo.dwFlags = win32process.STARTF_USESTDHANDLES

        # Create new handles whose inheritance property is false
        currentPid = win32api.GetCurrentProcess()

        tmp = win32api.DuplicateHandle(
            currentPid, self.hStdoutR, currentPid, 0, 0, win32con.DUPLICATE_SAME_ACCESS
        )
        win32file.CloseHandle(self.hStdoutR)
        self.hStdoutR = tmp

        tmp = win32api.DuplicateHandle(
            currentPid, self.hStderrR, currentPid, 0, 0, win32con.DUPLICATE_SAME_ACCESS
        )
        win32file.CloseHandle(self.hStderrR)
        self.hStderrR = tmp

        tmp = win32api.DuplicateHandle(
            currentPid, self.hStdinW, currentPid, 0, 0, win32con.DUPLICATE_SAME_ACCESS
        )
        win32file.CloseHandle(self.hStdinW)
        self.hStdinW = tmp

        # Add the specified environment to the current environment - this is
        # necessary because certain operations are only supported on Windows
        # if certain environment variables are present.

        env = os.environ.copy()
        env.update(environment or {})
        env = {os.fsdecode(key): os.fsdecode(value) for key, value in env.items()}

        # Set inherited handles for child process and pass them via the
        # environment.
        if not childFDs:
            childFDs = {}
        for fd, parentMode in childFDs.items():
            if fd in (0, 1, 2):
                # Standard pipes are always setup via the STARTUPINFO.
                continue

            if parentMode not in ("r", "w"):
                raise ValueError(f"Invalid mode {parentMode!r} for childFDs[{fd}]")

            if parentMode == "r":
                # Child writes, parent reads.
                childMode = "w"
                # Create a native Windows anonymous pipe
                hParentR, hChildW = win32pipe.CreatePipe(sAttrs, 0)
                # Prepare for passing via env.
                winHandle = int(hChildW)
                # Make sure the parent side is NOT inheritable.
                win32api.SetHandleInformation(hParentR, win32con.HANDLE_FLAG_INHERIT, 0)

                # _PollableReadPipe is calling the callbaks without arguments.
                # We use lambda with default argument to work around.
                childPipe = _pollingfile._PollableReadPipe(
                    hParentR,
                    lambda data, boundFD=fd: self.proto.childDataReceived(
                        boundFD, data
                    ),
                    lambda boundFD=fd: self._pipeConnectionLost(boundFD),
                )
            elif parentMode == "w":
                # Master writes, Child reads.
                childMode = "r"
                hChildR, hParentW = win32pipe.CreatePipe(sAttrs, 0)
                win32api.SetHandleInformation(hParentW, win32con.HANDLE_FLAG_INHERIT, 0)
                winHandle = int(hChildR)

                childPipe = _pollingfile._PollableWritePipe(
                    hParentW, lambda boundFD=fd: self._pipeConnectionLost(boundFD)
                )

            parentHandles.append(winHandle)
            childPipes[fd] = childPipe
            env[f"_TWISTED_CHILD_FD_{fd}"] = f"{childMode},{winHandle}"

        # Make sure all the arguments are Unicode.
        args = [os.fsdecode(x) for x in args]

        cmdline = quoteArguments(args)

        # The command, too, needs to be Unicode, if it is a value.
        command = os.fsdecode(command) if command else command
        path = os.fsdecode(path) if path else path

        # TODO: error detection here.  See #2787 and #4184.
        def doCreate():
            flags = win32con.CREATE_NO_WINDOW
            self.hProcess, self.hThread, self.pid, dwTid = win32process.CreateProcess(
                command, cmdline, None, None, 1, flags, env, path, StartupInfo
            )

        try:
            doCreate()
        except pywintypes.error as pwte:
            if not _invalidWin32App(pwte):
                # This behavior isn't _really_ documented, but let's make it
                # consistent with the behavior that is documented.
                raise OSError(pwte)
            else:
                # look for a shebang line.  Insert the original 'command'
                # (actually a script) into the new arguments list.
                sheb = _findShebang(command)
                if sheb is None:
                    raise OSError(
                        "%r is neither a Windows executable, "
                        "nor a script with a shebang line" % command
                    )
                else:
                    args = list(args)
                    args.insert(0, command)
                    cmdline = quoteArguments(args)
                    origcmd = command
                    command = sheb
                    try:
                        # Let's try again.
                        doCreate()
                    except pywintypes.error as pwte2:
                        # d'oh, failed again!
                        if _invalidWin32App(pwte2):
                            raise OSError(
                                "%r has an invalid shebang line: "
                                "%r is not a valid executable" % (origcmd, sheb)
                            )
                        raise OSError(pwte2)

        # close handles which only the child will use
        for h in parentHandles:
            win32api.CloseHandle(h)

        # set up everything
        self.stdout = _pollingfile._PollableReadPipe(
            self.hStdoutR,
            lambda data: self.proto.childDataReceived(1, data),
            self.outConnectionLost,
        )
        childPipes[1] = self.stdout

        self.stderr = _pollingfile._PollableReadPipe(
            self.hStderrR,
            lambda data: self.proto.childDataReceived(2, data),
            self.errConnectionLost,
        )
        childPipes[2] = self.stderr

        self.stdin = _pollingfile._PollableWritePipe(
            self.hStdinW, self.inConnectionLost
        )
        childPipes[0] = self.stdin

        self._childPipes = childPipes
        for pipewatcher in childPipes.values():
            self._addPollableResource(pipewatcher)

        # notify protocol
        self.proto.makeConnection(self)

        self._addPollableResource(_Reaper(self))

    def signalProcess(self, signalID):
        if self.pid is None:
            raise error.ProcessExitedAlready()
        if signalID in ("INT", "TERM", "KILL"):
            win32process.TerminateProcess(self.hProcess, 1)

    def _getReason(self, status):
        if status == 0:
            return error.ProcessDone(status)
        return error.ProcessTerminated(status)

    def write(self, data):
        """
        Write data to the process' stdin.

        @type data: C{bytes}
        """
        self.stdin.write(data)

    def writeSequence(self, seq):
        """
        Write data to the process' stdin.

        @type seq: C{list} of C{bytes}
        """
        self._childPipes[0].writeSequence(seq)

    def writeToChild(self, fd, data):
        """
        Similar to L{ITransport.write} but also allows the file descriptor in
        the child process which will receive the bytes to be specified.

        This implementation is limited to writing to the child's standard input.

        @param fd: The file descriptor to which to write.  Only stdin (C{0}) is
            supported.
        @type fd: C{int}

        @param data: The bytes to write.
        @type data: C{bytes}

        @return: L{None}

        @raise KeyError: If C{fd} is anything other than the stdin file
            descriptor (C{0}).
        """
        self._childPipes[fd].write(data)

    def closeChildFD(self, fd):
        self._childPipes[fd].close()

    def closeStdin(self) -> None:
        """
        Close the process' stdin.
        """
        self.stdin.close()

    def closeStderr(self) -> None:
        """
        Close the process' stderr.
        """
        self.stderr.close()

    def closeStdout(self) -> None:
        """
        Close the process' stdout.
        """
        self.stdout.close()

    def loseConnection(self) -> None:
        """
        Close all the process pipes.
        """
        for pipe in self._childPipes.values():
            pipe.close()

    def outConnectionLost(self):
        self.proto.childConnectionLost(1)
        self.connectionLostNotify()

    def errConnectionLost(self):
        self.proto.childConnectionLost(2)
        self.connectionLostNotify()

    def inConnectionLost(self):
        self.proto.childConnectionLost(0)
        self.connectionLostNotify()

    def _pipeConnectionLost(self, fd):
        self.proto.childConnectionLost(fd)
        self.connectionLostNotify()

    def connectionLostNotify(self):
        """
        Will be called 3 times, by stdout/err threads and process handle.
        """
        self.closedNotifies += 1
        self.maybeCallProcessEnded()

    def maybeCallProcessEnded(self) -> None:
        """
        Wait for all pipes to be closed and then close the process.
        """
        if self.closedNotifies != len(self._childPipes) or not self.lostProcess:
            return

        try:
            win32file.CloseHandle(self.hProcess)
        except pywintypes.error as error:
            # We get pywintypes.error:
            #  (6, 'WaitForSingleObject', 'The handle is invalid.')
            # With error 6 the handle is already closed.
            if error.args[0] != 6:
                raise

        try:
            win32file.CloseHandle(self.hThread)
        except pywintypes.error as error:
            if error.args[0] != 6:
                raise

        self.hProcess = None
        self.hThread = None
        BaseProcess.maybeCallProcessEnded(self)

    # IConsumer
    def registerProducer(self, producer, streaming):
        self.stdin.registerProducer(producer, streaming)

    def unregisterProducer(self):
        self.stdin.unregisterProducer()

    # IProducer
    def pauseProducing(self):
        self._pause()

    def resumeProducing(self):
        self._unpause()

    def stopProducing(self):
        self.loseConnection()

    def getHost(self):
        # ITransport.getHost
        raise NotImplementedError("Unimplemented: Process.getHost")

    def getPeer(self):
        # ITransport.getPeer
        raise NotImplementedError("Unimplemented: Process.getPeer")

    def __repr__(self) -> str:
        """
        Return a string representation of the process.
        """
        return f"<{self.__class__.__name__} pid={self.pid}>"


def _getWindowsInheritedHandle(fd: int, _fdopen=os.fdopen):
    """
    Get a handle from an inherited file descriptor.

    @param fd: The parent file descriptor.

    @return: The file descriptor that can be used on the current child process.
    """
    import msvcrt

    varName = f"_TWISTED_CHILD_FD_{fd}"
    envValue = os.environ.get(varName, "")
    if not envValue:
        raise ValueError(
            f"Env {varName} not found. Was this child process spawned by Twisted?"
        )

    parts = envValue.split(",", 1)
    if len(parts) != 2:
        raise ValueError(f"Env {varName} is malformed: {envValue}")
    mode, winHandle = parts

    if mode != "r" and mode != "w":
        raise ValueError(f"Env {varName} has invalid mode: {mode}")

    if mode == "r":
        openedFD = msvcrt.open_osfhandle(int(winHandle), os.O_RDONLY | os.O_BINARY)
        if openedFD != fd:
            os.dup2(openedFD, fd)
            os.close(openedFD)

        result = _fdopen(fd, "rb", buffering=0)
        return result
    elif mode == "w":
        openedFD = msvcrt.open_osfhandle(int(winHandle), os.O_WRONLY | os.O_BINARY)
        if openedFD != fd:
            os.dup2(openedFD, fd)
            os.close(openedFD)
        return _fdopen(fd, "wb", buffering=0)
