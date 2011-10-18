# -*- test-case-name: twisted.test.test_twistd -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

import os, errno, sys

from twisted.python import log, syslog, logfile, usage
from twisted.python.util import switchUID, uidFromString, gidFromString
from twisted.application import app, service
from twisted import copyright


def _umask(value):
    return int(value, 8)


class ServerOptions(app.ServerOptions):
    synopsis = "Usage: twistd [options]"

    optFlags = [['nodaemon','n',  "don't daemonize, don't use default umask of 0077"],
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
                     ['uid', 'u', None, "The uid to run as.", uidFromString],
                     ['gid', 'g', None, "The gid to run as.", gidFromString],
                     ['umask', None, None,
                      "The (octal) file creation mask to apply.", _umask],
                    ]

    compData = usage.Completions(
        optActions={"pidfile": usage.CompleteFiles("*.pid"),
                    "chroot": usage.CompleteDirs(descr="chroot directory"),
                    "gid": usage.CompleteGroups(descr="gid to run as"),
                    "uid": usage.CompleteUsernames(descr="uid to run as"),
                    "prefix": usage.Completer(descr="syslog prefix"),
                    },
        )

    def opt_version(self):
        """Print version information and exit.
        """
        print 'twistd (the Twisted daemon) %s' % copyright.version
        print copyright.copyright
        sys.exit()


    def postOptions(self):
        app.ServerOptions.postOptions(self)
        if self['pidfile']:
            self['pidfile'] = os.path.abspath(self['pidfile'])


def checkPID(pidfile):
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



class UnixAppLogger(app.AppLogger):
    """
    A logger able to log to syslog, to files, and to stdout.

    @ivar _syslog: A flag indicating whether to use syslog instead of file
        logging.
    @type _syslog: C{bool}

    @ivar _syslogPrefix: If C{sysLog} is C{True}, the string prefix to use for
        syslog messages.
    @type _syslogPrefix: C{str}

    @ivar _nodaemon: A flag indicating the process will not be daemonizing.
    @type _nodaemon: C{bool}
    """

    def __init__(self, options):
        app.AppLogger.__init__(self, options)
        self._syslog = options.get("syslog", False)
        self._syslogPrefix = options.get("prefix", "")
        self._nodaemon = options.get("nodaemon", False)


    def _getLogObserver(self):
        """
        Create and return a suitable log observer for the given configuration.

        The observer will go to syslog using the prefix C{_syslogPrefix} if
        C{_syslog} is true.  Otherwise, it will go to the file named
        C{_logfilename} or, if C{_nodaemon} is true and C{_logfilename} is
        C{"-"}, to stdout.

        @return: An object suitable to be passed to C{log.addObserver}.
        """
        if self._syslog:
            return syslog.SyslogObserver(self._syslogPrefix).emit

        if self._logfilename == '-':
            if not self._nodaemon:
                sys.exit('Daemons cannot log to stdout, exiting!')
            logFile = sys.stdout
        elif self._nodaemon and not self._logfilename:
            logFile = sys.stdout
        else:
            if not self._logfilename:
                self._logfilename = 'twistd.log'
            logFile = logfile.LogFile.fromFullPath(self._logfilename)
            try:
                import signal
            except ImportError:
                pass
            else:
                # Override if signal is set to None or SIG_DFL (0)
                if not signal.getsignal(signal.SIGUSR1):
                    def rotateLog(signal, frame):
                        from twisted.internet import reactor
                        reactor.callFromThread(logFile.rotate)
                    signal.signal(signal.SIGUSR1, rotateLog)
        return log.FileLogObserver(logFile).emit



def daemonize():
    # See http://www.erlenstar.demon.co.uk/unix/faq_toc.html#TOC16
    if os.fork():   # launch child and...
        os._exit(0) # kill off parent
    os.setsid()
    if os.fork():   # launch child and...
        os._exit(0) # kill off parent again.
    null = os.open('/dev/null', os.O_RDWR)
    for i in range(3):
        try:
            os.dup2(null, i)
        except OSError, e:
            if e.errno != errno.EBADF:
                raise
    os.close(null)



def launchWithName(name):
    if name and name != sys.argv[0]:
        exe = os.path.realpath(sys.executable)
        log.msg('Changing process name to ' + name)
        os.execv(exe, [name, sys.argv[0], '--originalname'] + sys.argv[1:])



class UnixApplicationRunner(app.ApplicationRunner):
    """
    An ApplicationRunner which does Unix-specific things, like fork,
    shed privileges, and maintain a PID file.
    """
    loggerFactory = UnixAppLogger

    def preApplication(self):
        """
        Do pre-application-creation setup.
        """
        checkPID(self.config['pidfile'])
        self.config['nodaemon'] = (self.config['nodaemon']
                                   or self.config['debug'])
        self.oldstdout = sys.stdout
        self.oldstderr = sys.stderr


    def postApplication(self):
        """
        To be called after the application is created: start the
        application and run the reactor. After the reactor stops,
        clean up PID files and such.
        """
        self.startApplication(self.application)
        self.startReactor(None, self.oldstdout, self.oldstderr)
        self.removePID(self.config['pidfile'])


    def removePID(self, pidfile):
        """
        Remove the specified PID file, if possible.  Errors are logged, not
        raised.

        @type pidfile: C{str}
        @param pidfile: The path to the PID tracking file.
        """
        if not pidfile:
            return
        try:
            os.unlink(pidfile)
        except OSError, e:
            if e.errno == errno.EACCES or e.errno == errno.EPERM:
                log.msg("Warning: No permission to delete pid file")
            else:
                log.err(e, "Failed to unlink PID file")
        except:
            log.err(None, "Failed to unlink PID file")


    def setupEnvironment(self, chroot, rundir, nodaemon, umask, pidfile):
        """
        Set the filesystem root, the working directory, and daemonize.

        @type chroot: C{str} or L{NoneType}
        @param chroot: If not None, a path to use as the filesystem root (using
            L{os.chroot}).

        @type rundir: C{str}
        @param rundir: The path to set as the working directory.

        @type nodaemon: C{bool}
        @param nodaemon: A flag which, if set, indicates that daemonization
            should not be done.

        @type umask: C{int} or L{NoneType}
        @param umask: The value to which to change the process umask.

        @type pidfile: C{str} or L{NoneType}
        @param pidfile: If not C{None}, the path to a file into which to put
            the PID of this process.
        """
        daemon = not nodaemon

        if chroot is not None:
            os.chroot(chroot)
            if rundir == '.':
                rundir = '/'
        os.chdir(rundir)
        if daemon and umask is None:
            umask = 077
        if umask is not None:
            os.umask(umask)
        if daemon:
            daemonize()
        if pidfile:
            f = open(pidfile,'wb')
            f.write(str(os.getpid()))
            f.close()


    def shedPrivileges(self, euid, uid, gid):
        """
        Change the UID and GID or the EUID and EGID of this process.

        @type euid: C{bool}
        @param euid: A flag which, if set, indicates that only the I{effective}
            UID and GID should be set.

        @type uid: C{int} or C{NoneType}
        @param uid: If not C{None}, the UID to which to switch.

        @type gid: C{int} or C{NoneType}
        @param gid: If not C{None}, the GID to which to switch.
        """
        if uid is not None or gid is not None:
            extra = euid and 'e' or ''
            desc = '%suid/%sgid %s/%s' % (extra, extra, uid, gid)
            try:
                switchUID(uid, gid, euid)
            except OSError:
                log.msg('failed to set %s (are you root?) -- exiting.' % desc)
                sys.exit(1)
            else:
                log.msg('set %s' % desc)


    def startApplication(self, application):
        """
        Configure global process state based on the given application and run
        the application.

        @param application: An object which can be adapted to
            L{service.IProcess} and L{service.IService}.
        """
        process = service.IProcess(application)
        if not self.config['originalname']:
            launchWithName(process.processName)
        self.setupEnvironment(
            self.config['chroot'], self.config['rundir'],
            self.config['nodaemon'], self.config['umask'],
            self.config['pidfile'])

        service.IService(application).privilegedStartService()

        uid, gid = self.config['uid'], self.config['gid']
        if uid is None:
            uid = process.uid
        if gid is None:
            gid = process.gid

        self.shedPrivileges(self.config['euid'], uid, gid)
        app.startApplication(application, not self.config['no_save'])
