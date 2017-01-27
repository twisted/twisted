# -*- test-case-name: twisted.application.runner.test.test_runner -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Twisted application runner.
"""

from sys import stderr
from signal import SIGTERM
from os import kill

from constantly import Names, NamedConstant

from twisted.logger import (
    globalLogBeginner, textFileLogObserver,
    FilteringLogObserver, LogLevelFilterPredicate,
    LogLevel, Logger,
)
from twisted.internet import default as defaultReactor
from ._exit import exit, ExitStatus
from ._pidfile import nonePIDFile, AlreadyRunningError, InvalidPIDFileError



class Runner(object):
    """
    Twisted application runner.
    """

    log = Logger()


    def __init__(
        self, options={},
        reactor=None,
        pidFile=nonePIDFile, kill=False,
        defaultLogLevel=LogLevel.info,
    ):
        """
        @param options: Configuration options for this runner.
        @type options: mapping of L{RunnerOptions} to values

        @param reactor: The reactor to start and run the application in.
        @type reactor: L{IReactorCore}

        @param pidFile: The file to store the running process ID in.
        @type pidFile: L{IPIDFile}

        @param kill: Whether this runner should kill an existing running
            instance of the application.
        @type kill: L{bool}

        @param defaultLogLevel: The default log level to start the logging
            system with.
        @type defaultLogLevel: L{NamedConstant} from L{LogLevel}
        """
        self.options         = options
        self.reactor         = reactor
        self.pidFile         = pidFile
        self.kill            = kill
        self.defaultLogLevel = defaultLogLevel


    def run(self):
        """
        Run this command.
        """
        pidFile = self.pidFile

        self.killIfRequested()

        try:
            with pidFile:
                self.startLogging()
                self.startReactor()
                self.reactorExited()

        except AlreadyRunningError:
            exit(ExitStatus.EX_CONFIG, "Already running.")
            return  # When testing, patched exit doesn't exit


    def killIfRequested(self):
        """
        If C{self.kill} is true, attempt to kill a running instance of the
        application.
        """
        pidFile = self.pidFile

        if self.kill:
            if pidFile is nonePIDFile:
                exit(ExitStatus.EX_USAGE, "No PID file specified.")
                return  # When testing, patched exit doesn't exit

            try:
                pid = pidFile.read()
            except EnvironmentError:
                exit(ExitStatus.EX_IOERR, "Unable to read PID file.")
                return  # When testing, patched exit doesn't exit
            except InvalidPIDFileError:
                exit(ExitStatus.EX_DATAERR, "Invalid PID file.")
                return  # When testing, patched exit doesn't exit

            self.startLogging()
            self.log.info("Terminating process: {pid}", pid=pid)

            kill(pid, SIGTERM)

            exit(ExitStatus.EX_OK)
            return  # When testing, patched exit doesn't exit


    def startLogging(self):
        """
        Start the L{twisted.logger} logging system.
        """
        logFile = self.options.get(RunnerOptions.logFile, stderr)

        fileLogObserverFactory = self.options.get(
            RunnerOptions.fileLogObserverFactory, textFileLogObserver
        )

        fileLogObserver = fileLogObserverFactory(logFile)

        logLevelPredicate = LogLevelFilterPredicate(
            defaultLogLevel=self.defaultLogLevel
        )

        filteringObserver = FilteringLogObserver(
            fileLogObserver, [logLevelPredicate]
        )

        globalLogBeginner.beginLoggingTo([filteringObserver])


    def startReactor(self):
        """
        Register C{self.whenRunning} with the reactor so that it is called once
        the reactor is running, then start the reactor.
        """
        if self.reactor is None:
            defaultReactor.install()
            from twisted.internet import reactor
            self.reactor = reactor
        else:
            reactor = self.reactor

        reactor.callWhenRunning(self.whenRunning)

        self.log.info("Starting reactor...")
        reactor.run()


    def whenRunning(self):
        """
        If L{RunnerOptions.whenRunning} is specified in C{self.options}, call
        it.

        @note: This method is called when the reactor is running.
        """
        whenRunning = self.options.get(RunnerOptions.whenRunning)
        if whenRunning is not None:
            whenRunning(self.options)


    def reactorExited(self):
        """
        If L{RunnerOptions.reactorExited} is specified in C{self.options}, call
        it.

        @note: This method is called after the reactor has exited.
        """
        reactorExited = self.options.get(RunnerOptions.reactorExited)
        if reactorExited is not None:
            reactorExited(self.options)



class RunnerOptions(Names):
    """
    Names for options recognized by L{Runner}.
    These are meant to be used as keys in the options given to L{Runner}, with
    corresponding values as noted below.

    @cvar logFile: A file stream to write logging output to.
        Corresponding value: writable file like object.
    @type logFile: L{NamedConstant}

    @cvar fileLogObserverFactory: What file log observer to use when starting
        the logging system.
        Corresponding value: callable that returns a
        L{twisted.logger.FileLogObserver}
    @type fileLogObserverFactory: L{NamedConstant}

    @cvar whenRunning: Hook to call when the reactor is running.
        This can be considered the Twisted equivalent to C{main()}.
        Corresponding value: callable that takes the options mapping given to
        the runner as an argument.
    @type whenRunning: L{NamedConstant}

    @cvar reactorExited: Hook to call when the reactor has exited.
        Corresponding value: callable that takes an empty arguments list
    @type reactorExited: L{NamedConstant}
    """

    logFile                = NamedConstant()
    fileLogObserverFactory = NamedConstant()
    whenRunning            = NamedConstant()
    reactorExited          = NamedConstant()
