# Copyright (C) 2003 Matthew W. Lefkowitz
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of version 2.1 of the GNU Lesser General Public
# License as published by the Free Software Foundation.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

from twisted.python import log
from twisted.application import app, service, internet
import sys, os

class ServerOptions(app.ServerOptions):
    synopsis = "Usage: twistw [options]"

    optFlags = [['nodaemon','n',  "(for backwards compatability)."],
                ]
    
    def opt_version(self):
        """Print version information and exit.
        """
        print 'twistw (the Twisted Windows runner) %s' % copyright.version
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
