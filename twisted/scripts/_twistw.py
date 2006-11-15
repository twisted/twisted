# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.


from twisted.python import log
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


def startLogging(logfilename):
    if logfilename == '-' or not logfilename:
        logFile = sys.stdout
    else:
        logFile = app.getLogFile(logfilename)
    log.startLogging(logFile)
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
        startLogging(self.config['logfile'])
        app.initialLog()
        os.chdir(self.config['rundir'])


    def postApplication(self):
        """
        Start the application and run the reactor.
        """
        service.IService(self.application).privilegedStartService()
        app.startApplication(self.application, not self.config['no_save'])
        app.startApplication(internet.TimerService(0.1, lambda:None), 0)
        app.runReactorWithLogging(self.config, self.oldstdout, self.oldstderr)
        app.reportProfile(self.config['report-profile'],
                          service.IProcess(self.application).processName)
        log.msg("Server Shut Down.")

