
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
from twisted import copyright
from twisted.python import usage, util, runtime, log, logfile
from twisted.application import apprun
import sys, os, pdb, profile, getpass

util.addPluginDir()

reactorTypes = {
    'gtk': 'twisted.internet.gtkreactor',
    'gtk2': 'twisted.internet.gtk2reactor',
    'glade': 'twisted.internet.gladereactor',
    'default': 'twisted.internet.default',
    'poll': 'twisted.internet.pollreactor',
    'qt': 'twisted.internet.qtreactor',
    'c' : 'twisted.internet.cReactor',
    }


class ServerOptions(apprun.ServerOptions):
    synopsis = "Usage: twistw [options]"

    def opt_version(self):
        """Print version information and exit.
        """
        print 'twistw (the Twisted Windows runner) %s' % copyright.version
        print copyright.copyright
        sys.exit()


def startLogging(logfilename):
    if logfilename == '-':
        if not nodaemon:
            print 'daemons cannot log to stdout'
            os._exit(1)
        logFile = sys.stdout
    elif not logfile:
        logFile = sys.stdout
    else:
        logPath = os.path.abspath(logfilename or 'twistd.log')
        logFile = logfile.LogFile(os.path.basename(logPath),
                                  os.path.dirname(logPath))
    sys.stdout.flush()
    log.msg("twistd %s (%s %s) starting up" % (copyright.version,
                                               sys.executable,
                                               runtime.shortPythonVersion()))

def setupEnvironment(config):
    os.chdir(config['rundir'])

def startApplication(config, application):
    application.privilegedStartService()
    application.startService()
    if not config['no_save']:
        application.scheduleSave()

def runApp(config):
    passphrase = apprun.getPassphrase(config['encrypted'])
    apprun.installReactor(config['reactor'])
    oldstdout = sys.stdout
    oldstderr = sys.stderr
    startLogging(config['logfile'])
    from twisted.internet import reactor
    log.msg('reactor class: %s' % reactor.__class__)
    startApplication(config, apprun.getApplication(config, passphrase))
    apprun.runReactorWithLogging(config, oldstdout, oldstderr)
    if config['report-profile']:
        apprun.reportProfile(config['report-profile'], application.processName)
    log.msg("Server Shut Down.")


def run():
    # make default be "--help"
    if len(sys.argv) == 1:
        sys.argv.append("--help")

    config = ServerOptions()
    try:
        config.parseOptions()
    except usage.error, ue:
        config.opt_help()
        print "%s: %s" % (sys.argv[0], ue)
        os._exit(1)

    runApp(config)

if __name__ == '__main__':
    run()
