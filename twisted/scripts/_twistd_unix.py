# -*- test-case-name: twisted.test.test_twistd -*-
# Copyright (c) 2001-2007 Twisted Matrix Laboratories.
# See LICENSE for details.


from twisted.python import log, syslog, logfile
from twisted.python.util import switchUID
from twisted.application import app, service
from twisted.scripts import mktap
from twisted import copyright

import os, errno, sys


class ServerOptions(app.ServerOptions):
    synopsis = "Usage: twistd [options]"

    optFlags = [['nodaemon','n',  "don't daemonize"],
                ['quiet', 'q', "No-op for backwards compatability."],
                ['originalname', None, "Don't try to change the process name"],
                ['syslog', None,   "Log to syslog, not to file"],
                ['euid', '',
                 "Set only effective user-id rather than real user-id. "
                 "(This option has no effect unless the server is running as "
                 "root, in which case it means not to shed all privileges "
                 "after binding ports, retaining the option to regain "
                 "privileges in cases such as spawning processes. "
                 "Use with caution.)"],
               ]

    optParameters = [
                     ['prefix', None,'twisted',
                      "use the given prefix when syslogging"],
                     ['pidfile','','twistd.pid',
                      "Name of the pidfile"],
                     ['chroot', None, None,
                      'Chroot to a supplied directory before running'],
                     ['uid', 'u', None, "The uid to run as."],
                     ['gid', 'g', None, "The gid to run as."],
                    ]
    zsh_altArgDescr = {"prefix":"Use the given prefix when syslogging (default: twisted)",
                       "pidfile":"Name of the pidfile (default: twistd.pid)",}
    zsh_actions = {"pidfile":'_files -g "*.pid"', "chroot":'_dirs'}
    zsh_actionDescr = {"chroot":"chroot directory"}

    def opt_version(self):
        """
        Print version information and exit.
        """
        print 'twistd (the Twisted daemon) %s' % copyright.version
        print copyright.copyright
        sys.exit()

    def postOptions(self):
        app.ServerOptions.postOptions(self)
        if self['pidfile']:
            self['pidfile'] = os.path.abspath(self['pidfile'])


class Daemonizer(app.ApplicationConfigItem):
    """
    Manage daemonization and PID file.
    """

    def daemonize(self):
        """
        Make the current process a daemon.
        """
        # See http://www.erlenstar.demon.co.uk/unix/faq_toc.html#TOC16
        if os.fork():   # launch child and...
            os._exit(0) # kill off parent
        os.setsid()
        if os.fork():   # launch child and...
            os._exit(0) # kill off parent again.
        os.umask(077)
        null = os.open('/dev/null', os.O_RDWR)
        for i in range(3):
            try:
                os.dup2(null, i)
            except OSError, e:
                if e.errno != errno.EBADF:
                    raise
        os.close(null)

    def checkPID(self):
        """
        Check current PID file.
        """
        pidfile = self.options['pidfile']
        if not pidfile:
            return
        if os.path.exists(pidfile):
            try:
                pid = int(open(pidfile).read())
            except ValueError:
                sys.exit('Pidfile %s contains non-numeric value' % pidfile)
            try:
                os.kill(pid, 0)
            except OSError, why:
                if why[0] == errno.ESRCH:
                    # The pid doesnt exists.
                    log.msg('Removing stale pidfile %s' % pidfile, isError=True)
                    os.remove(pidfile)
                else:
                    sys.exit("Can't check status of PID %s from pidfile %s: %s" %
                             (pid, pidfile, why[1]))
            else:
                sys.exit("""\
    Another twistd server is running, PID %s\n
    This could either be a previously started instance of your application or a
    different application entirely. To start a new one, either run it in some other
    directory, or use the --pidfile and --logfile parameters to avoid clashes.
    """ %  pid)

    def removePID(self):
        """
        Remove PID file.
        """
        pidfile = self.options['pidfile']
        if not pidfile:
            return
        try:
            os.unlink(pidfile)
        except OSError, e:
            if e.errno == errno.EACCES or e.errno == errno.EPERM:
                log.msg("Warning: No permission to delete pid file")
            else:
                log.msg("Failed to unlink PID file:")
                log.err()
        except:
            log.msg("Failed to unlink PID file:")
            log.err()


class AppLogger(app.AppLogger):
    """
    Custom logger for unix.
    """

    def getLogObserver(self):
        """
        Create and return a suitable log observer for the given configuration.

        The observer will go to syslog using the prefix C{prefix} if C{sysLog}
        is true. Otherwise, it will go to the file named C{logfilename} or, if
        C{nodaemon} is true and C{logfilename} is C{"-"}, to stdout.

        @return: An object suitable to be passed to C{log.addObserver}.
        """
        logfilename = self.options['logfile']
        sysLog = self.options['syslog']
        prefix = self.options['prefix']
        nodaemon = self.options['nodaemon']
        if sysLog:
            observer = syslog.SyslogObserver(prefix).emit
        else:
            if logfilename == '-':
                if not nodaemon:
                    print 'daemons cannot log to stdout'
                    os._exit(1)
                logFile = sys.stdout
            elif nodaemon and not logfilename:
                logFile = sys.stdout
            else:
                logFile = logfile.LogFile.fromFullPath(logfilename or 'twistd.log')
                try:
                    import signal
                except ImportError:
                    pass
                else:
                    def rotateLog(signal, frame):
                        from twisted.internet import reactor
                        reactor.callFromThread(logFile.rotate)
                    signal.signal(signal.SIGUSR1, rotateLog)
            observer = log.FileLogObserver(logFile).emit
        return observer


class AppRunner(app.AppRunner):
    """
    Custom runner for unix.
    """

    def shedPrivileges(self, euid, uid, gid):
        """
        Change privilege before execution.
        """
        if uid is not None or gid is not None:
            switchUID(uid, gid, euid)
            extra = euid and 'e' or ''
            log.msg('set %suid/%sgid %s/%s' % (extra, extra, uid, gid))

    def launchWithName(self, name):
        """
        Change process name.
        """
        if name and name != sys.argv[0]:
            exe = os.path.realpath(sys.executable)
            log.msg('Changing process name to ' + name)
            os.execv(exe, [name, sys.argv[0], '--originalname'] + sys.argv[1:])

    def setupEnvironment(self):
        """
        Manage the environment: chroot, rundir, daemonize.
        """
        if self.options['chroot'] is not None:
            os.chroot(self.options['chroot'])
            if self.options['rundir'] == '.':
                self.options['rundir'] = '/'
        os.chdir(self.options['rundir'])
        if not self.options['nodaemon']:
            self.config.daemonizer.daemonize()
        if self.options['pidfile']:
            open(self.options['pidfile'],'wb').write(str(os.getpid()))

    def startApplication(self, application):
        """
        Start the application: prepare the environment, change privileges, then
        call normal start.
        """
        if not self.options['originalname']:
            self.launchWithName(self.config.process.processName)
        self.setupEnvironment()
        service.IService(application).privilegedStartService()

        uid, gid = mktap.getid(self.options['uid'], self.options['gid'])
        if uid is None:
            uid = self.config.process.uid
        if gid is None:
            gid = self.config.process.gid

        self.shedPrivileges(self.options['euid'], uid, gid)
        app.AppRunner.startApplication(self, application)


class ApplicationConfig(app.ApplicationConfig):
    """
    Configuration specific to unix.

    @cvar daemonizerFactory: class used to create daemonizer.
    @type daemonizerFactory: C{class}

    @ivar daemonizer: utility item managing daemonization.
    @type daemonizer: L{app.ApplicationConfigItem}
    """
    runnerFactory = AppRunner
    loggerFactory = AppLogger
    daemonizerFactory = Daemonizer

    def __init__(self, options):
        """
        Create the configuration: call parent and instantiate daemonizer.
        """
        app.ApplicationConfig.__init__(self, options)
        self.daemonizer = self.daemonizerFactory(self, options)


class UnixApplicationRunner(app.ApplicationRunner):
    """
    An ApplicationRunner which does Unix-specific things, like fork,
    shed privileges, and maintain a PID file.
    """
    configFactory = ApplicationConfig

    def preApplication(self):
        """
        Do pre-application-creation setup.
        """
        self.config.daemonizer.checkPID()

    def postApplication(self):
        """
        To be called after the application is created: start the
        application and run the reactor. After the reactor stops,
        clean up PID files and such.
        """
        self.config.runner.start(self.application)
        # Here the application has stopped
        self.config.daemonizer.removePID()
        self.config.profiling.reportProfile(self.config.process.processName)
        self.config.logger.finalLog()

