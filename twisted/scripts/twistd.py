
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

#Don't use twistd on windows
from twisted.python import runtime
import sys
if runtime.platformType != 'posix':
    sys.exit("Please use twistw on windows, not twistd")
# End hack

from twisted.python import log, syslog
from twisted.python.util import switchUID
from twisted.application import app, service
from twisted import copyright
import os, errno, signal

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
                    ]

    def opt_version(self):
        """Print version information and exit.
        """
        print 'twistd (the Twisted daemon) %s' % copyright.version
        print copyright.copyright
        sys.exit()


def checkPID(pidfile):
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

def startLogging(logfilename, sysLog, prefix, nodaemon):
    if logfilename == '-':
        if not nodaemon:
            print 'daemons cannot log to stdout'
            os._exit(1)
        logFile = sys.stdout
    elif sysLog:
        syslog.startLogging(prefix)
    elif nodaemon and not logfilename:
        logFile = sys.stdout
    else:
        logFile = app.getLogFile(logfilename or 'twistd.log')
        def rotateLog(signal, frame):
            from twisted.internet import reactor
            reactor.callLater(0, logFile.rotate)
        signal.signal(signal.SIGUSR1, rotateLog)
    if not sysLog:
        log.startLogging(logFile)
    sys.stdout.flush()


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
    switchUID(uid, gid, euid)
    extra = euid and 'e' or ''
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
    process = service.IProcess(application, None)
    if not config['originalname']:
        launchWithName(process.processName)
    setupEnvironment(config)
    service.IService(application).privilegedStartService()
    shedPrivileges(config['euid'], process.uid, process.gid)
    app.startApplication(application, not config['no_save'])


def runApp(config):
    checkPID(config['pidfile'])
    passphrase = app.getPassphrase(config['encrypted'])
    app.installReactor(config['reactor'])
    config['nodaemon'] = config['nodaemon'] or config['debug']
    oldstdout = sys.stdout
    oldstderr = sys.stderr
    startLogging(config['logfile'], config['syslog'], config['prefix'],
                 config['nodaemon'])
    app.initialLog()
    application = app.getApplication(config, passphrase)
    startApplication(config, application)
    app.runReactorWithLogging(config, oldstdout, oldstderr)
    removePID(config['pidfile'])
    app.reportProfile(config['report-profile'],
                      service.IProcess(application).processName)
    log.msg("Server Shut Down.")


def run():
    app.run(runApp, ServerOptions)


if __name__ == "__main__":
     run()
