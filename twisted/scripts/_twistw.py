# Copyright (c) 2001-2007 Twisted Matrix Laboratories.
# See LICENSE for details.


from twisted.python import log, logfile
from twisted.application import app, service, internet
from twisted import copyright

import sys, os


class ServerOptions(app.ServerOptions):
    synopsis = "Usage: twistd [options]"

    optFlags = [['nodaemon','n',  "(for backwards compatability)."],
                ]

    def opt_version(self):
        """
        Print version information and exit.
        """
        print 'twistd (the Twisted Windows runner) %s' % copyright.version
        print copyright.copyright
        sys.exit()


class AppLogger(app.AppLogger):
    """
    Logger specific to windows.
    """

    def getLogObserver(self):
        """
        Create and return a suitable log observer for the given configuration.

        The observer will go to stdout if C{logfilename} is empty or equal to
        C{"-"}.  Otherwise, it will go to a file with that name.

        @return: An object suitable to be passed to C{log.addObserver}.
        """
        logfilename = self.config['logfile']
        if logfilename == '-' or not logfilename:
            logFile = sys.stdout
        else:
            logFile = logfile.LogFile.fromFullPath(logfilename)
        return log.FileLogObserver(logFile).emit


class AppRunner(app.AppRunner):
    """
    Runner specific to windows.
    """

    def setupEnvironment(self):
        """
        Manage environment, only rundir for now.
        """
        os.chdir(self.options['rundir'])

    def startApplication(self, application):
        """
        Start the application: prepare the environment, call normal start.
        """
        self.setupEnvironment()
        service.IService(self.application).privilegedStartService()
        app.AppRunner.startApplication(self, application)
        app.AppRunner.startApplication(self, internet.TimerService(0.1, lambda:None), 0)


class ApplicationConfig(app.ApplicationConfig):
    """
    Configuration specific to windows.
    """
    runnerFactory = AppRunner
    loggerFactory = AppLogger


class WindowsApplicationRunner(app.ApplicationRunner):
    """
    An ApplicationRunner which avoids unix-specific things. No
    forking, no PID files, no privileges.
    """
    def preApplication(self):
        """
        Do pre-application-creation setup.
        """

    def postApplication(self):
        """
        Start the application and run the reactor.
        """
        self.config.runner.start(self.application)
        # Here the application has stopped
        self.config.profiling.reportProfile(self.config.process.processName)
        self.config.logger.finalLog()

