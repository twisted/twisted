
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

from __future__ import nested_scopes

from twisted import copyright
from twisted.python import usage, util, runtime
from twisted.python import log, logfile

from twisted.persisted import styles
util.addPluginDir()

# System Imports
try:
    import cPickle as pickle
except ImportError:
    import pickle

try:
    import cStringIO as StringIO
except ImportError:
    import StringIO

import traceback, imp, sys, os, errno

reactorTypes = {
    'gtk': 'twisted.internet.gtkreactor',
    'gtk2': 'twisted.internet.gtk2reactor',
    'glade': 'twisted.internet.gladereactor',
    'default': 'twisted.internet.default',
    'win32': 'twisted.internet.win32eventreactor',
    'win': 'twisted.internet.win32eventreactor',
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

    def opt_plugin(self, pkgname):
        """read config.tac from a plugin package, as with -y
        """
        try:
            fname = imp.find_module(pkgname)[1]
        except ImportError:
            raise UsageError("Error: Package %s not found. Is it in your "
                             "~/TwistedPlugins directory?" % pkgname)
        self.opts['python'] = os.path.join(fname, 'config.tac')

    def opt_version(self):
        """Print version information and exit.
        """
        print 'twistd (the Twisted daemon) %s' % copyright.version
        print copyright.copyright
        sys.exit()

    def opt_spew(self):
        """Print an insanely verbose log of everything that happens.  Useful
        when debugging freezes or locks in complex code."""
        from twisted.python.util import spewer
        sys.settrace(spewer)

    opt_g = opt_plugin


def decrypt(passphrase, data):
    import md5
    from Crypto.Cipher import AES
    return AES.new(md5.new(passphrase).digest()[:16]).decrypt(data)


def createApplicationDecoder(config):
    mainMod = sys.modules['__main__']

    # Twisted Imports
    class EverythingEphemeral(styles.Ephemeral):
        def __getattr__(self, key):
            try:
                return getattr(mainMod, key)
            except AttributeError:
                if initRun:
                    raise
                else:
                    log.msg("Warning!  Loading from __main__: %s" % key)
                    return styles.Ephemeral()

    # Application creation/unserializing
    if config['python']:
        def decode(filename, data):
            log.msg('Loading %s...' % (filename,))
            d = {'__file__': filename}
            exec data in d, d
            try:
                return d['application']
            except KeyError:
                log.msg("Error - python file %r must set a variable named "
                        "'application', an instance of "
                        "twisted.internet.app.Application. No such variable "
                        "was found!" % filename)
                sys.exit()
        filename = os.path.abspath(config['python'])
        mode = 'r'
    elif config['xml']:
        def decode(filename, data):
            from twisted.persisted.marmalade import unjellyFromXML
            log.msg('<Loading file="%s" />' % (filename,))
            sys.modules['__main__'] = EverythingEphemeral()
            application = unjellyFromXML(StringIO.StringIO(data))
            sys.modules['__main__'] = mainMod
            styles.doUpgrade()
            return application
        filename = config['xml']
        mode = 'r'
    elif config['source']:
        def decode(filename, data):
            from twisted.persisted.aot import unjellyFromSource
            log.msg("Loading %s..." % (filename,))
            sys.modules['__main__'] = EverythingEphemeral()
            application = unjellyFromSource(StringIO.StringIO(data))
            sys.modules['__main__'] = mainMod
            styles.doUpgrade()
            return application
        filename = config['source']
        mode = 'r'
    else:
        def decode(filename, data):
            log.msg("Loading %s..." % (filename,))
            sys.modules['__main__'] = EverythingEphemeral()
            application = pickle.loads(data)
            sys.modules['__main__'] = mainMod
            styles.doUpgrade()
            return application
        filename = config['file']
        mode = 'rb'
    return filename, decode, mode


def loadApplication(config, passphrase):
    filename, decode, mode = createApplicationDecoder(config)
    if config['encrypted']:
        data = open(filename, 'rb').read()
        data = decrypt(passphrase, data)
        try:
            return decode(filename, data)
        except:
            # Too bad about this.
            log.msg("Error loading Application - "
                    "perhaps you used the wrong passphrase?")
            raise
    else:
        data = open(filename, mode).read()
        return decode(filename, data)


def debugSignalHandler(*args):
    """Break into debugger."""
    import pdb
    pdb.set_trace()


def installReactor(reactor)
    if reactor:
        if runtime.platformType == 'java':
            from twisted.internet import javareactor
            javareactor.install()
        else:
            from twisted.python.reflect import namedModule
            namedModule(reactorTypes[reactor]).install()

def checkPID(pidfile, quiet)
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
        except AttributeError:
            pass # welcome to windows
        else:
            sys.exit("""\
Another twistd server is running, PID %s\n
This could either be a previously started instance of your application or a
different application entirely. To start a new one, either run it in some other
directory, or use my --pidfile and --logfile parameters to avoid clashes.
""" %  pid)

def removePID(pidfile)
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

def startLogging(logfile, syslog, prefix, nodaemon):
    if logfile == '-':
        if not nodaemon:
            print 'daemons cannot log to stdout'
            os._exit(1)
        logFile = sys.stdout
    elif nodaemon and not logfile:
        logFile = sys.stdout
    elif syslog:
        from twisted.python import syslog
        syslog.startLogging(prefix)
    else:
        logPath = os.path.abspath(logfile or 'twistd.log')
        logFile = logfile.LogFile(os.path.basename(logPath),
                                  os.path.dirname(logPath))
        # rotate logs on SIGUSR1
        if os.name == "posix":
            import signal
            def rotateLog(signal, frame, logFile=logFile):
                from twisted.internet import reactor
                reactor.callLater(0, logFile.rotate)
            signal.signal(signal.SIGUSR1, rotateLog)


    oldstdin = sys.stdin
    oldstdout = sys.stdout
    oldstderr = sys.stderr
    if not syslog:
        log.startLogging(logFile)
    sys.stdout.flush()
    log.msg("twistd %s (%s %s) starting up" % (copyright.version,
                                               sys.executable,
                                               runtime.shortPythonVersion()))



def runReactor(config):
    from twisted.internet import reactor
    if config['profile']:
        import profile
        p = profile.Profile()
        p.runctx("reactor.run()", globals(), locals())
        if config['savestats']:
            p.dump_stats(config['profile'])
        else:
            # XXX - omfg python sucks
            tmp, sys.stdout = sys.stdout, open(config['profile'], 'a')
            p.print_stats()
            sys.stdout, tmp = tmp, sys.stdout
            tmp.close()
    elif config['debug']:
        import pdb
        from twisted.python import failure
        failure.startDebugMode()
        sys.stdout = oldstdout
        sys.stderr = oldstderr
        if os.name == "posix":
            import signal
            signal.signal(signal.SIGINT, debugSignalHandler)
            pdb.run("reactor.run()", globals(), locals())
    else:
        reactor.run()


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
    if euid:
        try:
            os.setegid(gid)
            os.seteuid(uid)
        except (AttributeError, OSError):
            pass
        else:
            log.msg('set euid/egid %s/%s' % (uid, gid))
    else:
        try:
            os.setgid(gid)
            os.setuid(uid)
        except (AttributeError, OSError):
            pass
        else:
            log.msg('set uid/gid %s/%s' % (uid, gid))

def getPassphrase(needed):
    if needed:
        import getpass
        return getpass.getpass('Passphrase: ')
    else:
        return None

def getApplication(config, passphrase)
    global initRun
    initRun = 0
    try:
        application = loadApplication(config, passphrase)
    except Exception, e:
        s = "Failed to load application: %s" % (e,)
        traceback.print_exc(file=log.logfile)
        log.msg(s)
        log.deferr()
        sys.exit('\n' + s + '\n')
    log.msg("Loaded.")
    initRun = 1

def launchWithName(name):
    if name and name != sys.argv[0]:
        exe = os.path.realpath(sys.executable)
        log.msg('Changing process name to ' + name)
        os.execv(exe, [name, sys.argv[0], '--originalname']+sys.argv[1:])
    
def usepid():
    # java doesn't have getpid, and Windows' getpid is near-useless
    return ((os.name != 'java') and (os.name != 'nt'))

def setupEnvironment(config):
    if config['chroot'] is not None:
        os.chroot(config['chroot'])
        if config['rundir'] == '.':
            config['rundir'] = '/'
    if platformType != 'java':
        # java can't chdir
        os.chdir(config['rundir'])
    if not config['nodaemon']:
        daemonize()
    if usepid():
        open(config['pidfile'],'wb').write(str(os.getpid()))
    if os.name == 'nt':
        # C-c can't interrupt select.select in win32.
        def callAgain(f):
            reactor.callLater(0.1, f, f)
        reactor.callLater(0.1, callAgain, callAgain)

# Install a reactor immediately.  The application will not load properly
# unless this is done FIRST; otherwise the first 'reactor' import would
# trigger an automatic installation of the default reactor.

# To make this callable from within a running Twisted app, allow as the
# reactor None to bypass this and use whatever reactor is currently in use.
def runApp(config):
    passphrase = getPassphrase(config['encrypted'])
    installReactor(config['reactor'])
    if runtime.platformType != 'posix' or config['debug']:
        # only posix can fork, and debugging requires nodaemon
        config['nodaemon'] = 1
    startLogging(config['logfile'], config['syslog'], config['prefix'],
                 config['nodaemon'])
    checkPID(config['pidfile'], config['quiet'])
    from twisted.internet import reactor
    log.msg('reactor class: %s' % reactor.__class__)
    application = getApplication(config, passphrase)
    if not config['originalname']:
        launchWithName(application.processName)
    setupEnvironment(config)
    application.privilegedStartService()
    shedPrivileges(config['euid'], application.uid, application.gid)
    application.startService()
    if not config['no_save']:
        application.scheduleSave()
    try:
        runReactor(config)
    except:
        if config['nodaemon']:
            file = oldstdout
        else:
            file = open("TWISTD-CRASH.log",'a')
        traceback.print_exc(file=file)
        file.flush()
    if usepid():
        removePID(config['pidfile'])
    if config['report-profile']:
        if application.processName:
            from twisted.python.dxprofile import report
            log.msg("Sending DXP stats...")
            report(config['report-profile'], application.processName)
            log.msg("DXP stats sent.")
        else:
            log.err("--report-profile specified but application has no "
                    "name (--appname unspecified)")
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
