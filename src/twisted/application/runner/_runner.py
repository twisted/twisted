# -*- test-case-name: twisted.application.runner.test.test_runner -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Twisted application runner.
"""

from sys import stderr
from signal import SIGTERM
from os import kill

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
        self,
        reactor=None,
        pidFile=nonePIDFile, kill=False,
        defaultLogLevel=LogLevel.info,
        logFile=stderr, fileLogObserverFactory=textFileLogObserver,
        whenRunning=lambda **_: None, whenRunningArguments={},
        reactorExited=lambda **_: None, reactorExitedArguments={},
    ):
        """
        @param reactor: The reactor to start and run the application in.
        @type reactor: L{IReactorCore}

        @param pidFile: The file to store the running process ID in.
        @type pidFile: L{IPIDFile}

        @param kill: Whether this runner should kill an existing running
            instance of the application.
        @type kill: L{bool}

        @param defaultLogLevel: The default log level to start the logging
            system with.
        @type defaultLogLevel: L{constantly.NamedConstant} from L{LogLevel}

        @param logFile: A file stream to write logging output to.
        @type logFile: writable file-like object

        @param fileLogObserverFactory: A factory for the file log observer to
            use when starting the logging system.
        @type pidFile: callable that takes a single writable file-like object
            argument and returns a L{twisted.logger.FileLogObserver}

        @param whenRunning: Hook to call after the reactor is running;
            this is where the application code that relies on the reactor gets
            called.
        @type whenRunning: callable that takes the keyword arguments specified
            by C{whenRunningArguments}

        @param whenRunningArguments: Keyword arguments to pass to
            C{whenRunning} when it is called.
        @type whenRunningArguments: L{dict}

        @param reactorExited: Hook to call after the reactor exits.
        @type reactorExited: callable that takes the keyword arguments
            specified by C{reactorExitedArguments}

        @param reactorExitedArguments: Keyword arguments to pass to
            C{reactorExited} when it is called.
        @type reactorExitedArguments: L{dict}
        """
        self.reactor                = reactor
        self.pidFile                = pidFile
        self.kill                   = kill
        self.defaultLogLevel        = defaultLogLevel
        self.logFile                = logFile
        self.fileLogObserverFactory = fileLogObserverFactory
        self.whenRunningHook        = whenRunning
        self.whenRunningArguments   = whenRunningArguments
        self.reactorExitedHook      = reactorExited
        self.reactorExitedArguments = reactorExitedArguments


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
        logFile = self.logFile

        fileLogObserverFactory = self.fileLogObserverFactory

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
        If C{self.reactor} is L{None}, install the default reactor and set
        C{self.reactor} to the default reactor.

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
        Call C{self.whenRunning}.

        @note: This method is called after the reactor starts running.
        """
        self.whenRunningHook(**self.whenRunningArguments)


    def reactorExited(self):
        """
        Call C{self.reactorExited}.

        @note: This method is called after the reactor exits.
        """
        self.reactorExitedHook(**self.reactorExitedArguments)
