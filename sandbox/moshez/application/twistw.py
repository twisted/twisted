
# Copyright (C) 2001 Matthew W. Lefkowitz
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
from twisted.python import util, log, logfile
from twisted.application import apprun
import sys, os

util.addPluginDir()

class ServerOptions(apprun.ServerOptions):
    synopsis = "Usage: twistw [options]"

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
        logPath = os.path.abspath(logfilename or 'twistd.log')
        logFile = logfile.LogFile(os.path.basename(logPath),
                                  os.path.dirname(logPath))
    log.startLogging(logFile)
    sys.stdout.flush()

def runApp(config):
    passphrase = apprun.getPassphrase(config['encrypted'])
    apprun.installReactor(config['reactor'])
    oldstdout = sys.stdout
    oldstderr = sys.stderr
    startLogging(config['logfile'])
    apprun.initialLog()
    os.chdir(config['rundir'])
    application = apprun.getApplication(config, passphrase)
    application.privilegedStartService()
    application.startService()
    if not config['no_save']:
        apprun.scheduleSave(application)
    apprun.runReactorWithLogging(config, oldstdout, oldstderr)
    if config['report-profile']:
        apprun.reportProfile(config['report-profile'], application.processName)
    log.msg("Server Shut Down.")


def run():
    apprun.run(runApp, ServerOptions)
