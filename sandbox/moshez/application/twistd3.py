
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
from twisted.python import usage, util, runtime, reflect, log, logfile, syslog
from twisted.python import failure
from twisted.persisted import styles
from twisted.application import apprun
import cPickle as pickle
import cStringIO as StringIO
import traceback, imp, sys, os, errno, signal, pdb, profile, getpass

util.addPluginDir()

reactorTypes = {
    'gtk': 'twisted.internet.gtkreactor',
    'gtk2': 'twisted.internet.gtk2reactor',
    'glade': 'twisted.internet.gladereactor',
    'default': 'twisted.internet.default',
    'poll': 'twisted.internet.pollreactor',
    'qt': 'twisted.internet.qtreactor',
    'c' : 'twisted.internet.cReactor',
    'kqueue': 'twisted.internet.kqreactor'
    }


class ServerOptions(usage.Options):
    synopsis = "Usage: twistd [options]"

    optFlags = [['nodaemon','n',  "don't daemonize"],
                ['savestats', None,
                 "save the Stats object rather than the text output of "
                 "the profiler."],
                ['debug', 'b',
                 "run the application in the Python Debugger "
                 "(implies nodaemon), sending SIGINT will drop into debugger"],
                ['quiet','q',     "be a little more quiet"],
                ['no_save','o',   "do not save state on shutdown"],
                ['originalname', None, "Don't try to change the process name"],
                ['syslog', None,   "Log to syslog, not to file"],
                ['euid', '',
                 "Set only effective user-id rather than real user-id. "
                 "(This option has no effect unless the server is running as "
                 "root, in which case it means not to shed all privileges "
                 "after binding ports, retaining the option to regain "
                 "privileges in cases such as spawning processes. "
                 "Use with caution.)"],
                ['encrypted', 'e',
                 "The specified tap/aos/xml file is encrypted."]]

    optParameters = [['logfile','l', None,
                      "log to a specified file, - for stdout"],
                     ['profile', 'p', None,
                      "Run in profile mode, dumping results to specified file"],
                     ['file','f','twistd.tap',
                      "read the given .tap file"],
                     ['prefix', None,'twisted',
                      "use the given prefix when syslogging"],
                     ['python','y', None,
                      "read an application from within a Python file"],
                     ['xml', 'x', None,
                      "Read an application from a .tax file "
                      "(Marmalade format)."],
                     ['source', 's', None,
                      "Read an application from a .tas file (AOT format)."],
                     ['pidfile','','twistd.pid',
                      "Name of the pidfile"],
                     ['rundir','d','.',
                      'Change to a supplied directory before running'],
                     ['chroot', None, None,
                      'Chroot to a supplied directory before running'],
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
        print 'twistd (the Twisted daemon) %s' % copyright.version
        print copyright.copyright
        sys.exit()

    def opt_spew(self):
        """Print an insanely verbose log of everything that happens.  Useful
        when debugging freezes or locks in complex code."""
        sys.settrace(util.spewer)


def checkPID(pidfile, quiet):
    if os.path.exists(pidfile):
        try:
            pid = int(open(pidfile).read())
        except ValueError:
            sys.exit('Pidfile %s contains non numeric value' % pidfile)

        try:
            os.kill(pid, 0)
        except OSError, why:
            if why[0] == errno.ESRCH:
                # The pid doesnt exists.
                if not quiet:
                    print 'Removing stale pidfile %s' % config['pidfile']
                    os.remove(pidfile)
            else:
                sys.exit("Can't check status of PID %s from pidfile %s: %s" %
                         (pid, pidfile, why[1]))
        else:
            sys.exit("""\
Another twistd server is running, PID %s\n
This could either be a previously started instance of your application or a
different application entirely. To start a new one, either run it in some other
directory, or use my --pidfile and --logfile parameters to avoid clashes.
""" %  pid)

def removePID(pidfile):
    try:
        os.unlink(pidfile)
    except OSError, e:
        if e.errno == errno.EACCES or e.errno == errno.EPERM:
            log.msg("Warning: No permission to delete pid file")
        else:
            log.msg("Failed to unlink PID file:")
            log.deferr()
    except:
        log.msg("Failed to unlink PID file:")
        log.deferr()

def startLogging(logfilename, syslog, prefix, nodaemon):
    if logfilename == '-':
        if not nodaemon:
            print 'daemons cannot log to stdout'
            os._exit(1)
        logFile = sys.stdout
    elif nodaemon and not logfile:
        logFile = sys.stdout
    elif syslog:
        syslog.startLogging(prefix)
    else:
        logPath = os.path.abspath(logfilename or 'twistd.log')
        logFile = logfile.LogFile(os.path.basename(logPath),
                                  os.path.dirname(logPath))
        def rotateLog(signal, frame, logFile=logFile):
            from twisted.internet import reactor
            reactor.callLater(0, logFile.rotate)
        signal.signal(signal.SIGUSR1, rotateLog)
    if not syslog:
        log.startLogging(logFile)
    sys.stdout.flush()
    log.msg("twistd %s (%s %s) starting up" % (copyright.version,
                                               sys.executable,
                                               runtime.shortPythonVersion()))


def daemonize():
    if os.fork():   # launch child and...
        os._exit(0) # kill off parent
    os.setsid()
    os.umask(077)
    for i in range(3):
        try:
            os.close(i)
        except OSError, e:
            if e.errno != errno.EBADF:
                raise

def shedPrivileges(euid, uid, gid):
    extra = (euid and 'e') or ''
    try:
        for (method, value) in zip(['uid', 'gid'], [uid, gid]):
            getattr(os, 'set'+extra+method)(value)
    except OSError:
        pass
    else:
        log.msg('set %suid/%sgid %s/%s' % (extra, extra, uid, gid))

def launchWithName(name):
    if name and name != sys.argv[0]:
        exe = os.path.realpath(sys.executable)
        log.msg('Changing process name to ' + name)
        os.execv(exe, [name, sys.argv[0], '--originalname']+sys.argv[1:])
    
def setupEnvironment(config):
    if config['chroot'] is not None:
        os.chroot(config['chroot'])
        if config['rundir'] == '.':
            config['rundir'] = '/'
    os.chdir(config['rundir'])
    if not config['nodaemon']:
        daemonize()
    open(config['pidfile'],'wb').write(str(os.getpid()))

def startApplication(config, application):
    if not config['originalname']:
        launchWithName(application.processName)
    setupEnvironment(config)
    application.privilegedStartService()
    shedPrivileges(config['euid'], application.uid, application.gid)
    application.startService()
    if not config['no_save']:
        application.scheduleSave()

def runApp(config):
    passphrase = apprun.getPassphrase(config['encrypted'])
    apprun.installReactor(config['reactor'])
    config['nodaemon'] = config['nodaemon'] and not config['debug']
    oldstdout = sys.stdout
    oldstderr = sys.stderr
    startLogging(config['logfile'], config['syslog'], config['prefix'],
                 config['nodaemon'])
    checkPID(config['pidfile'], config['quiet'])
    from twisted.internet import reactor
    log.msg('reactor class: %s' % reactor.__class__)
    startApplication(config, apprun.getApplication(config, passphrase))
    apprun.runReactorWithLogging(config, oldstdout, oldstderr)
    removePID(config['pidfile'])
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
