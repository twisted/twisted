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

def runApp(config):
    passphrase = app.getPassphrase(config['encrypted'])
    app.installReactor(config['reactor'])
    application = app.getApplication(config, passphrase)
    oldstdout = sys.stdout
    oldstderr = sys.stderr
    startLogging(config['logfile'])
    app.initialLog()
    os.chdir(config['rundir'])
    service.IService(application).privilegedStartService()
    app.startApplication(application, not config['no_save'])
    app.startApplication(internet.TimerService(0.1, lambda:None), 0)
    app.runReactorWithLogging(config, oldstdout, oldstderr)
    app.reportProfile(config['report-profile'],
                      service.IProcess(application).processName)
    log.msg("Server Shut Down.")


def run():
    app.run(runApp, ServerOptions)
