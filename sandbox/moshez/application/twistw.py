
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
import sys, os, pdb, profile, getpass
from twistd import decrypt, createApplicationDecoder, loadApplication,\
                   installReactor, runReactor, runReactorWithLogging,
                   getPassphrase, getApplication, reportProfile
# runReactor will have to be made portable

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


class ServerOptions(usage.Options):
    synopsis = "Usage: twistw [options]"

    optFlags = [['savestats', None,
                 "save the Stats object rather than the text output of "
                 "the profiler."],
                ['debug', 'b',
                 "run the application in the Python Debugger "
                 "(implies nodaemon), sending SIGINT will drop into debugger"],
                ['quiet','q',     "be a little more quiet"],
                ['no_save','o',   "do not save state on shutdown"],
                ['encrypted', 'e',
                 "The specified tap/aos/xml file is encrypted."]]

    optParameters = [['logfile','l', None,
                      "log to a specified file, - for stdout"],
                     ['profile', 'p', None,
                      "Run in profile mode, dumping results to specified file"],
                     ['file','f','twistd.tap',
                      "read the given .tap file"],
                     ['python','y', None,
                      "read an application from within a Python file"],
                     ['xml', 'x', None,
                      "Read an application from a .tax file "
                      "(Marmalade format)."],
                     ['source', 's', None,
                      "Read an application from a .tas file (AOT format)."],
                     ['rundir','d','.',
                      'Change to a supplied directory before running'],
                     ['reactor', 'r', None,
                      'Which reactor to use out of: %s.' %
                      ', '.join(reactorTypes.keys())],
                     ['report-profile', None, None,
                      'E-mail address to use when reporting dynamic execution '
                      'profiler stats.  This should not be combined with '
                      'other profiling options.  This will only take effect '
                      'if the application to be run has an application '
                      'name.']]

    def opt_version(self):
        """Print version information and exit.
        """
        print 'twistw (the Twisted Windows runner) %s' % copyright.version
        print copyright.copyright
        sys.exit()

    def opt_spew(self):
        """Print an insanely verbose log of everything that happens.  Useful
        when debugging freezes or locks in complex code."""
        sys.settrace(util.spewer)


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
    passphrase = getPassphrase(config['encrypted'])
    installReactor(config['reactor'])
    oldstdout = sys.stdout
    oldstderr = sys.stderr
    startLogging(config['logfile'])
    from twisted.internet import reactor
    log.msg('reactor class: %s' % reactor.__class__)
    startApplication(config, getApplication(config, passphrase))
    runReactorWithLogging(config, oldstdout, oldstderr)
    if config['report-profile']:
        reportProfile(config['report-profile'], application.processName)
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
