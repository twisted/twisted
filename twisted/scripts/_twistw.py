# Copyright (c) 2001-2008 Twisted Matrix Laboratories.
# See LICENSE for details.

import warnings

from twisted.python import log, logfile
from twisted.application import app, service, internet
from twisted import copyright
import sys, os

class ServerOptions(app.ServerOptions):
    synopsis = "Usage: twistd [options]"

    optFlags = [['nodaemon','n',  "(for backwards compatability)."],
                ]

    def opt_version(self):
        """Print version information and exit.
        """
        print 'twistd (the Twisted Windows runner) %s' % copyright.version
        print copyright.copyright
        sys.exit()


def _getLogObserver(logfilename):
    """
    Create and return a suitable log observer for the given configuration.

    The observer will go to stdout if C{logfilename} is empty or equal to
    C{"-"}.  Otherwise, it will go to a file with that name.

    @type logfilename: C{str}
    @param logfilename: The name of the file to which to log, if other than the
    default.

    @return: An object suitable to be passed to C{log.addObserver}.
    """
    if logfilename == '-' or not logfilename:
        logFile = sys.stdout
    else:
        logFile = logfile.LogFile.fromFullPath(logfilename)
    return log.FileLogObserver(logFile).emit


def startLogging(*args, **kw):
    warnings.warn(
        """
        Use ApplicationRunner instead of startLogging."
        """,
        category=PendingDeprecationWarning,
        stacklevel=2)
    observer = _getLogObserver(*args, **kw)
    log.startLoggingWithObserver(observer)
    sys.stdout.flush()


class WindowsApplicationRunner(app.ApplicationRunner):
    """
    An ApplicationRunner which avoids unix-specific things. No
    forking, no PID files, no privileges.
    """
    def preApplication(self):
        """
        Do pre-application-creation setup.
        """
        self.oldstdout = sys.stdout
        self.oldstderr = sys.stderr
        os.chdir(self.config['rundir'])


    def getLogObserver(self):
        """
        Override to supply a log observer suitable for Windows based on the
        given arguments.
        """
        return _getLogObserver(self.config['logfile'])


    def postApplication(self):
        """
        Start the application and run the reactor.
        """
        service.IService(self.application).privilegedStartService()
        app.startApplication(self.application, not self.config['no_save'])
        app.startApplication(internet.TimerService(0.1, lambda:None), 0)
        app.runReactorWithLogging(self.config, self.oldstdout, self.oldstderr,
                                  self.profiler)
        log.msg("Server Shut Down.")

