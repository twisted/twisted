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
from twisted.python import log, logfile
from twisted.persisted import styles
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
                ['debug', 'b',    "run the application in the Python Debugger (implies nodaemon), sending SIGINT will drop into debugger"],
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
                  ['chroot', None, None,
                   'Chroot to a supplied directory before running'],
                  ['reactor', 'r', None,
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

    def opt_spew(self):
        """Print an insanely verbose log of everything that happens.

        Useful when debugging freezes or locks in complex code.
        """
        def spewer(frame, s, ignored):
            from twisted.python import reflect
            if frame.f_locals.has_key('self'):
                se = frame.f_locals['self']
                print 'method %s of %s at %s' % (
                    frame.f_code.co_name, reflect.qual(se.__class__), id(se)
                    )
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
                log.msg("Error - python file %s must set a variable named 'application', an instance of twisted.internet.app.Application. No such variable was found!" % (repr(filename),))
                sys.exit()
        filename = os.path.abspath(config['python'])
        mode = 'r'
    elif config['xml']:
        def decode(filename, data):
            from twisted.persisted.marmalade import unjellyFromXML
            log.msg('<Loading file="%s" />' % (filename,))
            sys.modules['__main__'] = EverythingEphemeral()
            application = unjellyFromXML(StringIO(data))
            application.persistStyle = 'xml'
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
            application = unjellyFromSource(StringIO(data))
            application.persistStyle = 'aot'
            sys.modules['__main__'] = mainMod
            styles.doUpgrade()
            return application
        filename = config['source']
        mode = 'r'
    else:
        def decode(filename, data):
            log.msg("Loading %s..." % (filename,))
            sys.modules['__main__'] = EverythingEphemeral()
            application = loads(data)
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
            log.msg("Error loading Application - perhaps you used the wrong passphrase?")
            raise
    else:
        data = open(filename, mode).read()
        return decode(filename, data)


def debugSignalHandler(*args):
    """Break into debugger."""
    import pdb
    pdb.set_trace()


def runApp(config):
    global initRun
    platformType = runtime.platform.getType()

    register.checkLicenseFile()
    sys.path.append(config['rundir'])

    # Install a reactor immediately.  The application will not load properly
    # unless this is done FIRST; otherwise the first 'reactor' import would
    # trigger an automatic installation of the default reactor.
    
    # To make this callable from within a running Twisted app, allow as the
    # reactor None to bypass this and use whatever reactor is currently in use.

    if config['reactor']:
        if platformType == 'java':
            from twisted.internet import javareactor
            javareactor.install()
        else:
            from twisted.python.reflect import namedModule
            namedModule(reactorTypes[config['reactor']]).install()

    if platformType != 'posix' or config['debug']:
        # only posix can fork, and debugging requires nodaemon
        config['nodaemon'] = 1

    if config['encrypted']:
        import getpass
        passphrase = getpass.getpass('Passphrase: ')
    else:
        passphrase = None
    
    # Load the servers.
    # This will fix up accidental function definitions in evaluation spaces
    # and the like.
    initRun = 0
    if os.path.exists(config['pidfile']):
        try:
            pid = int(open(config['pidfile']).read())
        except ValueError:
            sys.exit('Pidfile %s contains non numeric value' % config['pidfile'])

        try:
            os.kill(pid, 0)
        except OSError, why:
            import errno
            if why[0] == errno.ESRCH:
                # The pid doesnt exists.
                if not config['quiet']:
                    print 'Removing stale pidfile %s' % config['pidfile']
                    os.remove(config['pidfile'])
            else:
                sys.exit('Can\'t check status of PID %s from pidfile %s: %s' % (pid, config['pidfile'], why[1]))
        else:
            sys.exit('A server is already running, PID %s' %  pid)

    if config['logfile'] == '-':
        if not config['nodaemon']:
            print 'daemons cannot log to stdout'
            os._exit(1)
        logFile = sys.stdout
    elif config['nodaemon'] and not config['logfile']:
        logFile = sys.stdout
    else:
        logPath = os.path.abspath(config['logfile'] or 'twistd.log')
        logFile = logfile.LogFile(os.path.basename(logPath), os.path.dirname(logPath))

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

    from twisted.internet import reactor
    log.msg('reactor class: %s' % reactor.__class__)

    try:
        application = loadApplication(config, passphrase)
    except Exception, e:
        s = "Failed to load application: %s" % (e,)
        traceback.print_exc(file=log.logfile)
        log.msg(s)
        log.deferr()
        sys.exit('\n' + s + '\n')

    # If we're asked to chroot and os.chroot does not exist,
    # just fail.
    if config['chroot'] is not None:
        os.chroot(config['chroot']) 

    if platformType != 'java':
        # java can't chdir
        os.chdir(config['rundir'])


    if not config['nodaemon']:
        # Turn into a daemon.
        if os.fork():   # launch child and...
            os._exit(0) # kill off parent
        os.setsid()
        os.umask(077)
        for i in range(3):
            try:
                os.close(i)
            except OSError, e:
                import errno
                if e.errno != errno.EBADF:
                    raise

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
        open(config['pidfile'],'wb').write(str(os.getpid()))

    if os.name == 'nt':
        # C-c can't interrupt select.select in win32.
        class Win32KillTimeout:
            """I time out every 1/10 second in order to allow C-c to kill the server.
            """
            def callMeAgain(self):
                reactor.callLater(0.1, self.callMeAgain)
        reactor.callLater(0.1, Win32KillTimeout().callMeAgain)


    application.bindPorts()
    if config['euid']:
        application.setEUID()
    else:
        application.setUID()

    try:
        if config['profile']:
            import profile
            profile.run("application.run(%d)" % (not config['no_save']))
        elif config['debug']:
            import pdb
            sys.stdout = oldstdout
            sys.stderr = oldstderr
            if os.name == "posix":
                import signal
                signal.signal(signal.SIGINT, debugSignalHandler)
            pdb.run("application.run(%d)" % (not config['no_save']),
                    globals(), locals())
        else:
            application.run(not config['no_save'])
    except:
        if config['nodaemon']:
            file = oldstdout
        else:
            file = open("TWISTD-CRASH.log",'a')
        traceback.print_exc(file=file)
        file.flush()
    if usepid:
        os.unlink(config['pidfile'])
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
