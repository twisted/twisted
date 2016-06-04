# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Twisted application runner.
"""

__all__ = [
    "Runner",
    "RunnerOptions",
]

from sys import stderr
from signal import SIGTERM
from os import getpid, kill

from twisted.python.constants import Names, NamedConstant
# from twisted.python.constants import Values, ValueConstant
# from twisted.python.usage import Options, UsageError
# from twisted.python.filepath import FilePath
from twisted.logger import (
    globalLogBeginner, textFileLogObserver,  # jsonFileLogObserver,
    FilteringLogObserver, LogLevelFilterPredicate,
    LogLevel,  # InvalidLogLevelError,
    Logger,
)
from ._exit import exit, ExitStatus



class Runner(object):
    """
    Twisted application runner.
    """

    log = Logger()


    def __init__(self, options):
        """
        @param options: Configuration options for this runner.
        @type options: mapping
        """
        self.options = options


    def execute(self):
        """
        Execute this command.
        Equivalent to:
            self.killIfRequested()
            self.writePIDFile()
            self.startLogging()
            self.startReactor()
            self.reactorExited()
            self.removePIDFile()
        """
        self.killIfRequested()
        self.writePIDFile()
        self.startLogging()
        self.startReactor()
        self.reactorExited()
        self.removePIDFile()


    def killIfRequested(self):
        """
        Kill a running instance of this application if L{RunnerOptions.kill} is
        specified and L{True} in L{self.options}.
        This requires that L{RunnerOptions.pidFilePath} also be specified;
        exit with L{ExitStatus.EX_USAGE} if kill is requested with no PID file.
        """
        pidFilePath = self.options.get(RunnerOptions.pidFilePath)

        if self.options.get(RunnerOptions.kill, False):
            if pidFilePath is None:
                exit(ExitStatus.EX_USAGE, "No PID file specified")
                return  # When testing, patched exit doesn't exit
            else:
                pid = ""
                try:
                    for pid in pidFilePath.open():
                        break
                except (IOError, OSError):
                    exit(ExitStatus.EX_DATAERR, "Unable to read pid file.")
                    return  # When testing, patched exit doesn't exit
                try:
                    pid = int(pid)
                except ValueError:
                    exit(ExitStatus.EX_DATAERR, "Invalid pid file.")
                    return  # When testing, patched exit doesn't exit

            self.startLogging()
            self.log.info("Terminating process: {pid}", pid=pid)

            kill(pid, SIGTERM)

            exit(ExitStatus.EX_OK)
            return  # When testing, patched exit doesn't exit


    def writePIDFile(self):
        """
        Write a PID file for this application if L{RunnerOptions.pidFilePath}
        is specified in L{self.options}.
        """
        pidFilePath = self.options.get(RunnerOptions.pidFilePath)
        if pidFilePath is not None:
            pid = getpid()
            pidFilePath.setContent(u"{}\n".format(pid).encode("utf-8"))


    def removePIDFile(self):
        """
        Remove the PID file for this application if L{RunnerOptions.pidFilePath}
        is specified in L{self.options}.
        """
        pidFilePath = self.options.get(RunnerOptions.pidFilePath)
        if pidFilePath is not None:
            pidFilePath.remove()


    def startLogging(self):
        """
        Start the L{twisted.logging} system.
        """
        logFile = self.options.get(RunnerOptions.logFile, stderr)

        fileLogObserverFactory = self.options.get(
            RunnerOptions.fileLogObserverFactory, textFileLogObserver
        )

        fileLogObserver = fileLogObserverFactory(logFile)

        logLevelPredicate = LogLevelFilterPredicate(
            defaultLogLevel=self.options.get(
                RunnerOptions.defaultLogLevel, LogLevel.info
            )
        )

        filteringObserver = FilteringLogObserver(
            fileLogObserver, [logLevelPredicate]
        )

        globalLogBeginner.beginLoggingTo([filteringObserver])


    def startReactor(self):
        """
        Register L{self.whenRunning} with the reactor so that it is called once
        the reactor is running and start the reactor.
        If L{RunnerOptions.reactor} is specified in L{self.options}, use that
        reactor; otherwise use the default reactor.
        """
        reactor = self.options.get(RunnerOptions.reactor)
        if reactor is None:
            from twisted.internet import reactor
            self.options[RunnerOptions.reactor] = reactor

        reactor.callWhenRunning(self.whenRunning)

        self.log.info("Starting reactor...")
        reactor.run()


    def whenRunning(self):
        """
        If L{RunnerOptions.whenRunning} is specified in L{self.options}, call
        it.

        @note: This method is called when the reactor is running.
        """
        whenRunning = self.options.get(RunnerOptions.whenRunning)
        if whenRunning is not None:
            whenRunning(self.options)


    def reactorExited(self):
        """
        If L{RunnerOptions.reactorExited} is specified in L{self.options}, call
        it.

        @note: This method is called after the reactor has exited.
        """
        reactorExited = self.options.get(RunnerOptions.reactorExited)
        if reactorExited is not None:
            reactorExited(self.options)



class RunnerOptions(Names):
    """
    Names for options recognized by L{Runner}.
    """

    reactor                = NamedConstant()
    pidFilePath            = NamedConstant()
    kill                   = NamedConstant()
    logFile                = NamedConstant()
    logFileFormat          = NamedConstant()
    defaultLogLevel        = NamedConstant()
    fileLogObserverFactory = NamedConstant()
    whenRunning            = NamedConstant()
    reactorExited          = NamedConstant()
