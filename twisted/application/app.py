# -*- test-case-name: twisted.test.test_application -*-
#
# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.

import sys, os, pdb, getpass, traceback, signal

from twisted.python import runtime, log, usage, reflect, failure, util, logfile
from twisted.persisted import sob
from twisted.application import service, reactors
from twisted.internet import defer
from twisted import copyright

# Expose the new implementation of installReactor at the old location.
from twisted.application.reactors import installReactor


def runWithProfiler(reactor, config):
    """Run reactor under standard profiler."""
    try:
        import profile
    except ImportError, e:
        s = "Failed to import module profile: %s" % e
        s += """
This is most likely caused by your operating system not including
profile.py due to it being non-free. Either do not use the option
--profile, or install profile.py; your operating system vendor
may provide it in a separate package.
"""
        traceback.print_exc(file=log.logfile)
        log.msg(s)
        log.deferr()
        sys.exit('\n' + s + '\n')

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
    try:
        import hotshot.stats
    except ImportError, e:
        s = "Failed to import module hotshot: %s" % e
        s += """
This is most likely caused by your operating system not including
profile.py due to it being non-free. Either do not use the option
--profile, or install profile.py; your operating system vendor
may provide it in a separate package.
"""
        traceback.print_exc(file=log.logfile)
        log.msg(s)
        log.deferr()
        sys.exit('\n' + s + '\n')

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

def fixPdb():
    def do_stop(self, arg):
        self.clear_all_breaks()
        self.set_continue()
        from twisted.internet import reactor
        reactor.callLater(0, reactor.stop)
        return 1

    def help_stop(self):
        print """stop - Continue execution, then cleanly shutdown the twisted reactor."""
    
    def set_quit(self):
        os._exit(0)

    pdb.Pdb.set_quit = set_quit
    pdb.Pdb.do_stop = do_stop
    pdb.Pdb.help_stop = help_stop

def runReactorWithLogging(config, oldstdout, oldstderr):
    from twisted.internet import reactor
    try:
        if config['profile']:
            if not config['nothotshot']:
                runWithHotshot(reactor, config)
            else:
                runWithProfiler(reactor, config)
        elif config['debug']:
            sys.stdout = oldstdout
            sys.stderr = oldstderr
            if runtime.platformType == 'posix':
                signal.signal(signal.SIGUSR2, lambda *args: pdb.set_trace())
                signal.signal(signal.SIGINT, lambda *args: pdb.set_trace())
            fixPdb()
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



class ApplicationRunner(object):
    """
    An object which helps running an application based on a config object.

    Subclass me and implement preApplication and postApplication
    methods. postApplication generally will want to run the reactor
    after starting the application.

    @ivar config: The config object, which provides a dict-like interface.
    @ivar application: Available in postApplication, but not
    preApplication. This is the application object.
    """
    def __init__(self, config):
        self.config = config

    def run(self):
        """Run the application."""
        self.preApplication()
        self.application = self.createOrGetApplication()
        self.postApplication()


    def preApplication(self):
        """
        Override in subclass.

        This should set up any state necessary before loading and
        running the Application.
        """
        raise NotImplementedError


    def postApplication(self):
        """
        Override in subclass.

        This will be called after the application has been loaded (so
        the C{application} attribute will be set). Generally this
        should start the application and run the reactor.
        """
        raise NotImplementedError


    def createOrGetApplication(self):
        """
        Create or load an Application based on the parameters found in the
        given L{ServerOptions} instance.

        If a subcommand was used, the L{service.IServiceMaker} that it
        represents will be used to construct a service to be added to
        a newly-created Application.

        Otherwise, an application will be loaded based on parameters in
        the config.
        """
        if self.config.subCommand:
            # If a subcommand was given, it's our responsibility to create
            # the application, instead of load it from a file.

            # loadedPlugins is set up by the ServerOptions.subCommands
            # property, which is iterated somewhere in the bowels of
            # usage.Options.
            plg = self.config.loadedPlugins[self.config.subCommand]
            ser = plg.makeService(self.config.subOptions)
            application = service.Application(plg.tapname)
            ser.setServiceParent(application)
        else:
            passphrase = getPassphrase(self.config['encrypted'])
            application = getApplication(self.config, passphrase)
        return application



def getApplication(config, passphrase):
    s = [(config[t], t)
           for t in ['python', 'xml', 'source', 'file'] if config[t]][0]
    filename, style = s[0], {'file':'pickle'}.get(s[1],s[1])
    try:
        log.msg("Loading %s..." % filename)
        application = service.loadApplication(filename, style, passphrase)
        log.msg("Loaded.")
    except Exception, e:
        s = "Failed to load application: %s" % e
        if isinstance(e, KeyError) and e.args[0] == "application":
            s += """
Could not find 'application' in the file. To use 'twistd -y', your .tac
file must create a suitable object (e.g., by calling service.Application())
and store it in a variable named 'application'. twistd loads your .tac file
and scans the global variables for one of this name.

Please read the 'Using Application' HOWTO for details.
"""
        traceback.print_exc(file=log.logfile)
        log.msg(s)
        log.deferr()
        sys.exit('\n' + s + '\n')
    return application

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


def _reactorZshAction():
    return "(%s)" % " ".join([r.shortName for r in reactors.getReactorTypes()])

class ReactorSelectionMixin:
    """
    Provides options for selecting a reactor to install.
    """
    zsh_actions = {"reactor" : _reactorZshAction}
    def opt_help_reactors(self):
        """
        Display a list of possibly available reactor names.
        """
        for r in reactors.getReactorTypes():
            print '    ', r.shortName, '\t', r.description
        raise SystemExit(0)


    def opt_reactor(self, shortName):
        """
        Which reactor to use (see --help-reactors for a list of possibilities)
        """
        # Actually actually actually install the reactor right at this very
        # moment, before any other code (for example, a sub-command plugin)
        # runs and accidentally imports and installs the default reactor.
        #
        # This could probably be improved somehow.
        installReactor(shortName)
    opt_r = opt_reactor




class ServerOptions(usage.Options, ReactorSelectionMixin):

    optFlags = [['savestats', None,
                 "save the Stats object rather than the text output of "
                 "the profiler."],
                ['no_save','o',   "do not save state on shutdown"],
                ['encrypted', 'e',
                 "The specified tap/aos/xml file is encrypted."],
                ['nothotshot', None,
                 "Don't use the 'hotshot' profiler even if it's available."]]

    optParameters = [['logfile','l', None,
                      "log to a specified file, - for stdout"],
                     ['profile', 'p', None,
                      "Run in profile mode, dumping results to specified file"],
                     ['file','f','twistd.tap',
                      "read the given .tap file"],
                     ['python','y', None,
                      "read an application from within a Python file (implies -o)"],
                     ['xml', 'x', None,
                      "Read an application from a .tax file "
                      "(Marmalade format)."],
                     ['source', 's', None,
                      "Read an application from a .tas file (AOT format)."],
                     ['rundir','d','.',
                      'Change to a supplied directory before running'],
                     ['report-profile', None, None,
                      'E-mail address to use when reporting dynamic execution '
                      'profiler stats.  This should not be combined with '
                      'other profiling options.  This will only take effect '
                      'if the application to be run has an application '
                      'name.']]

    #zsh_altArgDescr = {"foo":"use this description for foo instead"}
    #zsh_multiUse = ["foo", "bar"]
    zsh_mutuallyExclusive = [("file", "python", "xml", "source")]
    zsh_actions = {"file":'_files -g "*.tap"',
                   "python":'_files -g "*.(tac|py)"',
                   "xml":'_files -g "*.tax"',
                   "source":'_files -g "*.tas"',
                   "rundir":"_dirs"}
    #zsh_actionDescr = {"logfile":"log file name", "random":"random seed"}

    def __init__(self, *a, **kw):
        self['debug'] = False
        usage.Options.__init__(self, *a, **kw)

    def opt_debug(self):
        """
        run the application in the Python Debugger (implies nodaemon),
        sending SIGUSR2 will drop into debugger
        """
        defer.setDebugging(True)
        failure.startDebugMode()
        self['debug'] = True
    opt_b = opt_debug


    def opt_spew(self):
        """Print an insanely verbose log of everything that happens.
        Useful when debugging freezes or locks in complex code."""
        sys.settrace(util.spewer)
        try:
            import threading
        except ImportError:
            return
        threading.settrace(util.spewer)


    def parseOptions(self, options=None):
        if options is None:
            options = sys.argv[1:] or ["--help"]
        usage.Options.parseOptions(self, options)

    def postOptions(self):
        if self.subCommand or self['python']:
            self['no_save'] = True

    def subCommands(self):
        from twisted import plugin
        plugins = plugin.getPlugins(service.IServiceMaker)
        self.loadedPlugins = {}
        for plug in plugins:
            self.loadedPlugins[plug.tapname] = plug
            yield (plug.tapname, None, lambda: plug.options(), plug.description)
    subCommands = property(subCommands)



def run(runApp, ServerOptions):
    config = ServerOptions()
    try:
        config.parseOptions()
    except usage.error, ue:
        print config
        print "%s: %s" % (sys.argv[0], ue)
    else:
        runApp(config)


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
