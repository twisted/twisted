# -*- test-case-name: twisted.test.test_application -*-
#
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
from twisted.python import runtime, log, usage, reflect, failure, util, logfile
from twisted.persisted import sob
from twisted.application import compat, service
from twisted import copyright
import sys, os, pdb, profile, getpass, traceback, signal

reactorTypes = {
    'wx': 'twisted.internet.wxreactor',
    'gtk': 'twisted.internet.gtkreactor',
    'gtk2': 'twisted.internet.gtk2reactor',
    'glade': 'twisted.internet.gladereactor',
    'default': 'twisted.internet.default',
    'win32': 'twisted.internet.win32eventreactor',
    'win': 'twisted.internet.win32eventreactor',
    'poll': 'twisted.internet.pollreactor',
    'qt': 'twisted.internet.qtreactor',
    'cf' : 'twisted.internet.cfreactor',
    'kqueue': 'twisted.internet.kqreactor'
    }

def installReactor(reactor):
    if reactor:
        reflect.namedModule(reactorTypes[reactor]).install()

def runWithProfiler(reactor, config):
    """Run reactor under standard profiler."""
    p = profile.Profile()
    p.runcall(reactor.run)
    if config['savestats']:
        p.dump_stats(config['profile'])
    else:
        # XXX - omfg python sucks
        tmp, sys.stdout = sys.stdout, open(config['profile'], 'a')
        p.print_stats()
        sys.stdout, tmp = tmp, sys.stdout
        tmp.close()

def runWithHotshot(reactor, config):
    """Run reactor under hotshot profiler."""
    import hotshot, hotshot.stats
    # this writes stats straight out
    p = hotshot.Profile(config["profile"])
    p.runcall(reactor.run)
    if config["savestats"]:
        # stats are automatically written to file, nothing to do
        return
    else:
        s = hotshot.stats.load(config["profile"])
        s.strip_dirs()
        s.sort_stats(-1)
        tmp, sys.stdout = sys.stdout, open(config['profile'], 'w')
        s.print_stats()
        sys.stdout, tmp = tmp, sys.stdout
        tmp.close()

def runReactorWithLogging(config, oldstdout, oldstderr):
    from twisted.internet import reactor
    try:
        if config['profile']:
            if sys.version_info[:2] > (2, 2):
                runWithHotshot(reactor, config)
            else:
                runWithProfiler(reactor, config)
        elif config['debug']:
            failure.startDebugMode()
            sys.stdout = oldstdout
            sys.stderr = oldstderr
            if runtime.platformType == 'posix':
                signal.signal(signal.SIGUSR2, lambda *args: reactor.callLater(0, pdb.set_trace))
            pdb.runcall(reactor.run)
        else:
            reactor.run()
    except:
        if config['nodaemon']:
            file = oldstdout
        else:
            file = open("TWISTD-CRASH.log",'a')
        traceback.print_exc(file=file)
        file.flush()


def getPassphrase(needed):
    if needed:
        return getpass.getpass('Passphrase: ')
    else:
        return None

def getSavePassphrase(needed):
    if needed:
        passphrase = util.getPassword("Encryption passphrase: ")
    else:
        return None

def reportProfile(report_profile, name):
    if not report_profile:
        return
    if name:
        from twisted.python.dxprofile import report
        log.msg("Sending DXP stats...")
        report(report_profile, name)
        log.msg("DXP stats sent.")
    else:
        log.err("--report-profile specified but application has no "
                "name (--appname unspecified)")

class ServerOptions(usage.Options):

    optFlags = [['savestats', None,
                 "save the Stats object rather than the text output of "
                 "the profiler."],
                ['debug', 'b',
                 "run the application in the Python Debugger "
                 "(implies nodaemon), sending SIGUSR2 will drop into debugger"],
                ['no_save','o',   "do not save state on shutdown"],
                ['encrypted', 'e',
                 "The specified tap/aos/xml file is encrypted."]]

    optParameters = [['logfile','l', None,
                      "log to a specified file, - for stdout"],
                     ['profile', 'p', None,
                      "Run in profile mode, dumping results to specified file"],
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

    def opt_spew(self):
        """Print an insanely verbose log of everything that happens.  Useful
        when debugging freezes or locks in complex code."""
        sys.settrace(util.spewer)

    def parseOptions(self, options=None):
        usage.Options.parseOptions(self, options or sys.argv[1:] or ["--help"])

def getLoaders():
    d = {}
    for p in plugin.getPlugIns("apploader"):
        module = p.load()
        for loader in p.loaderFactories:
            d[loader] = getattr(module, loader)()
    return d
                        

def run(runApp, ServerOptions):
    config = ServerOptions()
    loaders = getLoaders()
    config.optParameters.extend([l.getParameter() for l in loaders])
    try:
        config.parseOptions()
    except usage.error, ue:
        print config
        print "%s: %s" % (sys.argv[0], ue)
    else:
        runApp(config, loaders)

def initialLog():
    from twisted.internet import reactor
    log.msg("twistd %s (%s %s) starting up" % (copyright.version,
                                               sys.executable,
                                               runtime.shortPythonVersion()))
    log.msg('reactor class: %s' % reactor.__class__)


def convertStyle(filein, typein, passphrase, fileout, typeout, encrypt):
    application = service.loadApplication(filein, typein, passphrase)
    sob.IPersistable(application).setStyle(typeout)
    passphrase = getSavePassphrase(encrypt)
    if passphrase:
        fileout = None
    sob.IPersistable(application).save(filename=fileout, passphrase=passphrase)

def startApplication(application, save):
    from twisted.internet import reactor
    service.IService(application).startService()
    if save:
         p = sob.IPersistable(application)
         reactor.addSystemEventTrigger('after', 'shutdown', p.save, 'shutdown')
    reactor.addSystemEventTrigger('before', 'shutdown',
                                  service.IService(application).stopService)

def getLogFile(logfilename):
    logPath = os.path.abspath(logfilename)
    logFile = logfile.LogFile(os.path.basename(logPath),
                              os.path.dirname(logPath))
    return logFile
