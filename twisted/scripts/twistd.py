# Twisted, the Framework of Your Internet
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
from twisted.python import usage, util, runtime, register, plugin
from twisted.python import logfile
util.addPluginDir()

# System Imports
from cPickle import load, loads
from cStringIO import StringIO
import traceback
import imp
import sys, os

reactorTypes = {
    'gtk': 'twisted.internet.gtkreactor',
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
                ['profile','p',   "run profiler"],
                ['debug', 'b',    "run the application in the Python Debugger (implies nodaemon)"],
                ['quiet','q',     "be a little more quiet"],
                ['no_save','o',   "do not save state on shutdown"],
                ['euid', '',     "Set only effective user-id rather than real user-id. "
                                  "(This option has no effect unless the server is running as root, "
                                  "in which case it means not to shed all privileges after binding "
                                  "ports, retaining the option to regain privileges in cases such as "
                                  "spawning processes.  Use with caution.)"],
                ['encrypted', 'e', "The specified tap/aos/xml file is encrypted."]]

    optParameters = [['logfile','l', None,
                   "log to a specified file, - for stdout"],
                  ['file','f','twistd.tap',
                   "read the given .tap file"],
                  ['python','y', None,
                   "read an application from within a Python file"],
                  ['xml', 'x', None,
                   "Read an application from a .tax file (Marmalade format)."],
                  ['source', 's', None,
                   "Read an application from a .tas file (AOT format)."],
                  ['pidfile','','twistd.pid',
                   "Name of the pidfile"],
                  ['rundir','d','.',
                   'Change to a supplied directory before running'],
                  ['reactor', 'r', 'default',
                   'Which reactor to use out of: %s.' % ', '.join(reactorTypes.keys())]]

    def opt_plugin(self, pkgname):
        """read config.tac from a plugin package, as with -y
        """
        try:
            fname = imp.find_module(pkgname)[1]
        except ImportError:
            print "Error: Package %s not found. Is it in your ~/TwistedPlugins directory?" % pkgname
            sys.exit()
        self.opts['python'] = os.path.join(fname, 'config.tac')

    def opt_version(self):
        """Print version information and exit.
        """
        print 'twistd (the Twisted daemon) %s' % copyright.version
        print copyright.copyright
        sys.exit()

    opt_g = opt_plugin


def decrypt(passphrase, data):
    from Crypto.Cipher import RC5
    return RC5.new(passphrase).decrypt(data)


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

    platformType = runtime.platform.getType()
    if platformType != 'java':
        # java can't chdir
        os.chdir(config.opts['rundir'])

    register.checkLicenseFile()
    sys.path.append(config.opts['rundir'])

    if platformType != 'posix' or config.opts['debug']:
        # only posix can fork, and debugging requires nodaemon
        config.opts['nodaemon'] = 1

    if config.opts['encrypted']:
        import getpass
        passphrase = getpass.getpass('Passphrase: ')

    # Twisted Imports
    from twisted.python import log
    from twisted.persisted import styles
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


    # Load the servers.
    # This will fix up accidental function definitions in evaluation spaces
    # and the like.
    initRun = 0
    mainMod = sys.modules['__main__']


    if os.path.exists(config.opts['pidfile']):
        try:
            pid = int(open(config.opts['pidfile']).read())
        except ValueError:
            sys.exit('Pidfile %s contains non numeric value' % config.opts['pidfile'])

        try:
            os.kill(pid, 0)
        except OSError, why:
            import errno
            if why[0] == errno.ESRCH:
                # The pid doesnt exists.
                if not config.opts['quiet']:
                    print 'Removing stale pidfile %s' % config.opts['pidfile']
                    os.remove(config.opts['pidfile'])
            else:
                sys.exit('Can\'t check status of PID %s from pidfile %s: %s' % (pid, config.opts['pidfile'], why[1]))
        else:
            sys.exit('A server is already running, PID %s' %  pid)

    if config.opts['logfile'] == '-':
        if not config.opts['nodaemon']:
            print 'daemons cannot log to stdout'
            os._exit(1)
        logFile = sys.stdout
    elif config.opts['nodaemon'] and not config.opts['logfile']:
        logFile = sys.stdout
    else:
        logPath = os.path.abspath(config.opts['logfile'] or 'twistd.log')
        logFile = logfile.LogFile(os.path.basename(logPath), os.path.dirname(logPath))

        # rotate logs on SIGUSR1
        if os.name == "posix":
            import signal
            def rotateLog(signal, frame, logFile=logFile):
                logFile.rotate()
            signal.signal(signal.SIGUSR1, rotateLog)


    oldstdin = sys.stdin
    oldstdout = sys.stdout
    oldstderr = sys.stderr
    log.startLogging(logFile)
    sys.stdout.flush()
    log.msg("twistd %s (%s %s) starting up" % (copyright.version,
                                               sys.executable,
                                               runtime.shortPythonVersion()))

    if register.LICENSE_USER:
        log.msg("license user: %s <%s>" % (register.LICENSE_USER, register.LICENSE_EMAIL))
    if register.LICENSE_KEY:
        log.msg("license code: %s" % (register.LICENSE_KEY))
    if register.LICENSE_ORG:
        log.msg("organization: %s" % register.LICENSE_ORG)

    if not config.opts['nodaemon']:
        # Turn into a daemon.
        if os.fork():   # launch child and...
            os._exit(0) # kill off parent
        os.setsid()
        os.umask(077)
        oldstdin.close()
        oldstdout.close()
        oldstderr.close()

    if platformType == 'java':
        from twisted.internet import javareactor
        javareactor.install()
    else:
        from twisted.python.reflect import namedModule
        namedModule(reactorTypes[config['reactor']]).install()

    from twisted.internet import reactor
    log.msg('reactor class: %s' % reactor.__class__)

    #Application creation/unserializing
    if config.opts['python']:
        def decode(file, data):
            log.msg('Loading %s...' % (file,))
            d = {'__file__': pyfile}
            exec data in d, d
            try:
                return d['application']
            except KeyError:
                log.msg("Error - python file %s must set a variable named 'application', an instance of twisted.internet.app.Application. No such variable was found!" % (repr(file),))
                sys.exit()
        file = os.path.abspath(config.opts['python'])
        mode = 'r'
    elif config.opts['xml']:
        def decode(file, data):
            from twisted.persisted.marmalade import unjellyFromXML
            log.msg('<Loading file="%s" />' % (file,))
            sys.modules['__main__'] = EverythingEphemeral()
            application = unjellyFromXML(StringIO(data))
            application.persistStyle = 'xml'
            sys.modules['__main__'] = mainMod
            styles.doUpgrade()
            return application
        file = config.opts['xml']
        mode = 'r'
    elif config.opts['source']:
        def decode(file, data):
            from twisted.persisted.aot import unjellyFromSource
            log.msg("Loading %s..." % (file,))
            sys.modules['__main__'] = EverythingEphemeral()
            application = unjellyFromSource(StringIO(data))
            application.persistStyle = 'aot'
            sys.modules['__main__'] = mainMod
            styles.doUpgrade()
            return application
        file = config.opts['source']
        mode = 'r'
    else:
        def decode(file, data):
            log.msg("Loading %s..." % (file,))
            sys.modules['__main__'] = EverythingEphemeral()
            application = loads(data)
            sys.modules['__main__'] = mainMod
            styles.doUpgrade()
            return application
        file = config.opts['file']
        mode = 'rb'

    if config.opts['encrypted']:
        data = open(file, 'rb').read()
        data = decrypt(passphrase, data)
        try:
            application = decode(file, data)
        except:
            # Too bad about this.
            log.msg("Error loading Application - perhaps you used the wrong passphrase?")
            raise
    else:
        data = open(file, mode).read()
        application = decode(file, data)


    # Load any view plugins which have been registered in plugins.tml file
    # This needs to be moved to an event which occurs on web server startup
    # Once glyph is done with the Reactors

    # (Note: 'view' is probably a bad name for a plugin, since this is really a
    # 'twisted.web.view'.  I suppose 'tap' was a bad precedent for plugin system
    # naming. --glyph)

    plugins = plugin.getPlugIns('view')
    for plug in plugins:
        try:
            plug.load()
        except Exception, e:
            log.msg("Loading view %s failed. %s" % (plug, e))

    log.msg("Loaded.")
    initRun = 1

    # java doesn't have getpid, and Windows' getpid is near-useless
    usepid = ((os.name != 'java') and (os.name != 'nt'))
    if usepid:
        open(config.opts['pidfile'],'wb').write(str(os.getpid()))

    if os.name == 'nt':
        # C-c can't interrupt select.select in win32.
        class Win32KillTimeout:
            """I time out every 1/10 second in order to allow C-c to kill the server.
            """
            def callMeAgain(self):
                reactor.callLater(0.1, self.callMeAgain)
        reactor.callLater(0.1, Win32KillTimeout().callMeAgain)


    application.bindPorts()
    if config.opts['euid']:
        application.setEUID()
    else:
        application.setUID()

    try:
        if config.opts['profile']:
            import profile
            profile.run("application.run(%d)" % (not config.opts['no_save']))
        elif config.opts['debug']:
            import pdb
            pdb.run("application.run(%d)" % (not config.opts['no_save']))
        else:
            application.run(not config.opts['no_save'])
    except:
        if config.opts['nodaemon']:
            file = oldstdout
        else:
            file = open("TWISTD-CRASH.log",'a')
        traceback.print_exc(file=file)
        file.flush()
    if usepid:
        os.unlink(config.opts['pidfile'])
    log.msg("Server Shut Down.")
