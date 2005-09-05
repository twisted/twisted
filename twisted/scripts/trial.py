# -*- test-case-name: twisted.trial.test.test_trial -*-

# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.

# Author/Maintainer: Jonathan D. Simms <slyphon@twistedmatrix.com>
# Originally written by: Jonathan Lange <jml@twistedmatrix.com>
#                        and countless contributors

import sys, os, inspect, types, errno, pdb, new
import shutil, random, gc, re, warnings, time
import os.path as osp
from os.path import join as opj
from cStringIO import StringIO

from twisted.internet import defer
from twisted.application import app
from twisted.python import usage, reflect, failure, log
from twisted import plugin
from twisted.python.util import spewer
from twisted.spread import jelly
from twisted.trial import runner, util, itrial, remote
from twisted.trial import adapters, reporter, tdoctest
from twisted.trial.itrial import ITrialDebug
from twisted.trial.unittest import TestVisitor

import zope.interface as zi

class LogError(Exception):
    pass

class _DebugLogObserver(object):
    validChannels = ('reporter', 'kbd', 'parseargs',
                     'wait', 'testTests', 'timeout',
                     'reactor')

    def __init__(self, *channels):
        L = []
        for c in channels:
            if c not in self.validChannels:
                raise LogError, c
            L.append(c)
        self.channels = L
        self.install()

    def __call__(self, events):
        iface = events.get('iface', None)
        if (iface is not None
            and iface is not itrial.ITrialDebug):
            return
        for c in self.channels:
            if c in events:
                print "TRIAL DEBUG: %s" % (''.join(events[c]),)

    def install(self):
        log.addObserver(self)

    def remove(self):
        if self in log.theLogPublisher.observers:
            log.removeObserver(self)


class PluginError(Exception):
    pass

class PluginWarning(Warning):
    pass


class ArgumentError(Exception):
    """raised when trial can't figure out how to convert an argument into
    a runnable chunk of python
    """

# Yea, this is stupid.  Leave it for for command-line compatibility for a
# while, though.
TBFORMAT_MAP = {
    'plain': 'default',
    'default': 'default',
    'emacs': 'brief',
    'brief': 'brief',
    'cgitb': 'verbose',
    'verbose': 'verbose'
    }

class Options(usage.Options):
    synopsis = """%s [options] [[file|package|module|TestCase|testmethod]...]
    """ % (os.path.basename(sys.argv[0]),)

    optFlags = [["help", "h"],
                ["rterrors", "e", "realtime errors, print out tracebacks as soon as they occur"],
                ["debug", "b", "Run tests in the Python debugger. Will load '.pdbrc' from current directory if it exists."],
                ["debug-stacktraces", "B", "Report Deferred creation and callback stack traces"],
                ["nopm", None, "don't automatically jump into debugger for postmorteming of exceptions"],
                ["dry-run", 'n', "do everything but run the tests"],
                ["profile", None, "Run tests under the Python profiler"],
                ["benchmark", None, "Run performance tests instead of unit tests."],
                ["until-failure", "u", "Repeat test until it fails"],
                ["recurse", "R", "Search packages recursively"],
                ['psyco', None, 'run tests with psyco.full() (EXPERIMENTAL)'],
                ['verbose', 'v', 'verbose color output (default)'],
                ['bwverbose', 'o', 'Colorless verbose output'],
                ['summary', 's', 'minimal summary output'],
                ['text', 't', 'terse text output'],
                ['timing', None, 'Timing output'],
                ['suppresswarnings', None, 'Only print warnings to log, not stdout'],
                ]

    optParameters = [["reactor", "r", None,
                      "Which reactor to use out of: " + \
                      ", ".join(app.reactorTypes.keys()) + "."],
                     ["logfile", "l", "test.log", "log file name"],
                     ["random", "z", None,
                      "Run tests in random order using the specified seed"],
                     ["reporter-args", None, None,
                      "a string passed to the reporter's 'args' kwarg"]]

    #zsh_altArgDescr = {"foo":"use this description for foo instead"}
    #zsh_multiUse = ["foo", "bar"]
    zsh_mutuallyExclusive = [("verbose", "bwverbose")]
    zsh_actions = {"reactor":"(%s)" % " ".join(app.reactorTypes.keys())}
    zsh_actionDescr = {"logfile":"log file name",
                       "random":"random seed"}
    zsh_extras = ["*:file|module|package|TestCase|testMethod:_files -g '*.py'"]

    fallbackReporter = reporter.TreeReporter
    defaultReporter = None

    def __init__(self):
        # make *absolutely* sure that we haven't loaded a reactor
        # by this point
        assert "twisted.internet.reactor" not in sys.modules
        usage.Options.__init__(self)
        self._logObserver = None
        self['modules'] = []
        self['packages'] = []
        self['testcases'] = []
        self['methods'] = []
        self['_couldNotImport'] = {}
        self['reporter'] = None
        self['debugflags'] = []
        self['cleanup'] = []

    def _loadReporters(self):
        self.pluginFlags, self.optToQual = [], {}
        self.plugins = plugin.getPlugins(itrial.IReporter)
        for p in self.plugins:
            self.pluginFlags.append([p.longOpt, p.shortOpt, p.description])
            qual = "%s.%s" % (p.module, p.klass)
            self.optToQual[p.longOpt] = qual

            # find the default
            d = getattr(p, 'default', None)
            if d is not None:
                self.defaultReporter = qual

        if self.defaultReporter is None:
            raise PluginError, "no default reporter specified"


    def getReporter(self):
        """return the class of the selected reporter
        @param config: a usage.Options instance after parsing options
        """
        if not hasattr(self, 'optToQual'):
            self._loadReporters()
        for opt, qual in self.optToQual.iteritems():
            if self[opt]:
                nany = reflect.namedAny(qual)
                log.msg(iface=ITrialDebug, reporter="reporter option: %s, returning %r" % (opt, nany))
                return nany
        else:
            return self.fallbackReporter

    def opt_reactor(self, reactorName):
        # this must happen before parseArgs does lots of imports
        app.installReactor(reactorName)
        print "Using %s reactor" % app.reactorTypes[reactorName]

    def opt_coverage(self, coverdir):
        """Generate coverage information in the given directory
        (relative to _trial_temp). Requires Python 2.3.3."""

        print "Setting coverage directory to %s." % (coverdir,)
        import trace

        # begin monkey patch --------------------------- 
        def find_executable_linenos(filename):
            """Return dict where keys are line numbers in the line number table."""
            #assert filename.endswith('.py') # YOU BASTARDS
            try:
                prog = open(filename).read()
                prog = '\n'.join(prog.splitlines()) + '\n'
            except IOError, err:
                sys.stderr.write("Not printing coverage data for %r: %s\n" % (filename, err))
                sys.stderr.flush()
                return {}
            code = compile(prog, filename, "exec")
            strs = trace.find_strings(filename)
            return trace.find_lines(code, strs)

        trace.find_executable_linenos = find_executable_linenos
        # end monkey patch ------------------------------

        self.coverdir = os.path.abspath(os.path.join('_trial_temp', coverdir))
        self.tracer = trace.Trace(count=1, trace=0)
        sys.settrace(self.tracer.globaltrace)


    def opt_testmodule(self, filename):
        "Module to grep for test cases (-*- test-case-name)"
        # only look at the first two lines of the file. Try to behave as
        # much like emacs local-variables scanner as is sensible

        # XXX: This doesn't make sense! ------------------------------------
        if not os.path.isfile(filename):
            return

        # recognize twisted/test/test_foo.py, which is itself a test case.
        # also twisted/web/test/test_foo.py
        d,f = os.path.split(filename)
        if (d.startswith("twisted/") and d.endswith("/test")
            and f.startswith("test_") and f.endswith(".py")):
            modname = filename.replace("/",".")[:-3]
            if modname not in self['modules']:
                self['modules'].append(modname)
            return
        # ------------------------------------------------------------------

        f = file(filename, "r")
        lines = [f.readline(), f.readline()]
        f.close()

        m = []
        for line in lines:
            # insist upon -*- delimiters
            res = re.search(r'-\*-(.*)-\*-', line)
            if res:
                # handle multiple variables
                for var in res.group(1).split(";"):
                    bits = var.split(":")
                    # ignore malformed variables
                    if len(bits) == 2 and bits[0].strip() == "test-case-name":
                        for module in bits[1].split(","):
                            module = module.strip()
                            # avoid duplicates
                            if module not in self['modules']:
                                self['modules'].append(module)


    def _deprecateOption(self, optName, alt):
        msg = ("the --%s option is deprecated, "
               "please just specify the %s on the command line "
               "and trial will do the right thing") % (optName, alt)
        warnings.warn(msg)

    def opt_module(self, module):
        "Module to test (DEPRECATED)"
        self._deprecateOption('module', "fully qualified module name")
        self._tryNamedAny(module)

    def opt_package(self, package):
        "Package to test (DEPRECATED)"
        self._deprecateOption('package', "fully qualified package name")
        self._tryNamedAny(package)

    def opt_testcase(self, case):
        "TestCase to test (DEPRECATED)"
        self._deprecateOption('testcase', "fully qualified TestCase name")
        self._tryNamedAny(case)

    def opt_file(self, filename):
        "Filename of module to test (DEPRECATED)"
        self._deprecateOption('file', "path to your test file")
        self._handleFile(filename)

    def opt_method(self, method):
        "Method to test (DEPRECATED)"
        self._deprecateOption('method', "fully qualified method name")
        self._tryNamedAny(method)

    def _handleFile(self, filename):
        m = None
        if osp.isfile(filename):
            try:
                mname = reflect.filenameToModuleName(filename)
                self._tryNamedAny(mname)
            except ArgumentError:
                # okay, not in PYTHONPATH...
                path, fullname = osp.split(filename)
                name, ext = osp.splitext(fullname)
                m = new.module(name)
                sourcestring = file(filename, 'r').read()
                sourcestring = sourcestring.replace('\r\n', '\n')
                code = compile(sourcestring, filename, 'exec')
                exec code in m.__dict__
                sys.modules[name] = m
        self['modules'].append(m)

    def opt_spew(self):
        """Print an insanely verbose log of everything that happens.  Useful
        when debugging freezes or locks in complex code."""
        sys.settrace(spewer)
        
    def opt_reporter(self, opt=None):
        """the fully-qualified name of the class to use as the reporter for
        this run. The class must implement twisted.trial.itrial.IReporter.
        by default, the stream argument will be sys.stdout
        """
        if opt is None:
            raise UsageError, 'must specify a fully qualified class name'
        self['reporter'] = reflect.namedAny(opt)

    def opt_disablegc(self):
        """Disable the garbage collector"""
        gc.disable()

    def opt_tbformat(self, opt):
        """Specify the format to display tracebacks with. Valid formats are 'plain', 'emacs',
        and 'cgitb' which uses the nicely verbose stdlib cgitb.text function"""
        try:
            self['tbformat'] = TBFORMAT_MAP[opt]
        except KeyError:
            raise usage.UsageError("tbformat must be 'plain', 'emacs', or 'cgitb'.")


    extra = None
    def opt_extra(self, arg):
        """
        Add an extra argument.  (This is a hack necessary for interfacing with
        emacs's `gud'.)
        """
        if self.extra is None:
            self.extra = []
        self.extra.append(arg)

    def opt_recursionlimit(self, arg):
        """see sys.setrecursionlimit()"""
        try:
            sys.setrecursionlimit(int(arg))
        except (TypeError, ValueError):
            raise usage.UsageError, "argument to recursionlimit must be an integer"

    def opt_trialdebug(self, arg):
        """turn on trial's internal debugging flags"""
        try:
            self._logObserver = _DebugLogObserver(arg)
        except LogError, e:
            raise usage.UsageError, "%s not a valid debugging channel" % (e.args[0])


    # the short, short version
    opt_c = opt_testcase
    opt_f = opt_file
    opt_m = opt_module
    opt_M = opt_method
    opt_p = opt_package
    opt_x = opt_extra

    tracer = None

    def _tryNamedAny(self, arg):
        try:
            try:
                n = reflect.namedAny(arg)
            except ValueError, ve:
                if ve.args == ('Empty module name',):
                    raise ArgumentError
                else:
                    raise
        except ArgumentError:
            raise
        except:
            f = failure.Failure()
            f.printTraceback()
            self['_couldNotImport'][arg] = f
            return

        # okay, we can use named any to import it, so now wtf is it?
        if inspect.ismodule(n):
            filename = os.path.basename(n.__file__)
            filename = os.path.splitext(filename)[0]
            if filename == '__init__':
                self['packages'].append(n)
            else:
                self['modules'].append(n)
        elif inspect.isclass(n):
            self['testcases'].append(n)
        elif inspect.ismethod(n):
            self['methods'].append(n)
        else:
            raise ArgumentError, "could not figure out how to use %s" % arg
            #self['methods'].append(n)


    def parseArgs(self, *args):
        def _dbg(msg):
            if self._logObserver is not None:
                log.msg(iface=ITrialDebug, parseargs=msg)

        if self.extra is not None:
            args = list(args)
            args.extend(self.extra)

        for arg in args:
            _dbg("arg: %s" % (arg,))
            
            if not os.sep in arg and not arg.endswith('.py'):
                # simplest case, someone writes twisted.test.test_foo on the
                # command line only one option, use namedAny
                try:
                    self._tryNamedAny(arg)
                except ArgumentError:
                    pass
                else:
                    continue
            
            # make sure the user isn't smoking crack
            if not os.path.exists(arg):
                raise IOError(errno.ENOENT, os.strerror(errno.ENOENT), arg)

            # if the argument ends in os.sep, it *must* be a directory (if it's
            # valid) directories must be modules/packages, so use
            # filenameToModuleName
            if arg.endswith(os.sep) and arg != os.sep:
                _dbg("arg endswith os.sep")
                arg = arg[:-len(os.sep)]
                _dbg("arg now %s" % (arg,))
                modname = reflect.filenameToModuleName(arg)
                self._tryNamedAny(modname)
                continue
                
            elif arg.endswith('.py'):
                _dbg("*Probably* a file.")
                if osp.exists(arg):
                    self._handleFile(arg)
                    continue

            elif osp.isdir(arg):
                if osp.exists(opj(arg, '__init__.py')):
                    modname = reflect.filenameToModuleName(arg)
                    self._tryNamedAny(modname)
                    continue
                
            raise ArgumentError, ("argument %r appears to be "
                 "invalid, rather than doing something incredibly stupid, "
                 "I'm blowing up" % (arg,))


    def postOptions(self):
        self['_origdir'] = os.getcwd()
        # Want to do this stuff as early as possible
        _setUpTestdir()
        _setUpLogging(self)

        def _mustBeInt():
            raise usage.UsageError("Argument to --random must be a positive "
                                   "integer")
            
        if self['random'] is not None:
            try:
                self['random'] = long(self['random'])
            except ValueError:
                _mustBeInt()
            else:
                if self['random'] < 0:
                    _mustBeInt()
                elif self['random'] == 0:
                    self['random'] = long(time.time() * 100)

        if not self.has_key('tbformat'):
            self['tbformat'] = 'default'

        if self['psyco']:
            try:
                import psyco
                psyco.full()
            except ImportError:
                print "couldn't import psyco, so continuing on without..."

        if self['nopm']:
            if not self['debug']:
                raise usage.UsageError("you must specify --debug when using "
                                       "--nopm ")
            failure.DO_POST_MORTEM = False

# options
# ----------------------------------------------------------
# config and run

def _monkeyPatchPyunit():
    # MONKEY PATCH -----------------------------------------
    unittest = eval("__import__('unittest')", {}, {})
    from twisted.trial import unittest as twunit
    unittest.TestCase = twunit.TestCase
    # ------------------------------------------------------

    
def _initialDebugSetup(config):
    # do this part of debug setup first for easy debugging of import failures
    if config['debug']:
        failure.startDebugMode()
    if config['debug'] or config['debug-stacktraces']:
        defer.setDebugging(True)


def _setUpLogging(config):
    if config['logfile']:
       # we should SEE deprecation warnings
       def seeWarnings(x):
           if x.has_key('warning'):
               print
               print x['format'] % x
       if not config['suppresswarnings']:
           log.addObserver(seeWarnings)
       if config['logfile'] == '-':
           logFileObj = sys.stdout
       else:
           logFileObj = file(config['logfile'], 'a')
       log.startLogging(logFileObj, 0)


def _getReporter(config):
    log.msg(iface=ITrialDebug, reporter="config['reporter']: %s"
            % (config['reporter'],))
    if config['reporter'] is not None:
        return config['reporter']

    reporter = config.getReporter()
    log.msg(iface=ITrialDebug, reporter="using reporter class: %r"
            % (reporter,))
    return reporter

def _getJanitor(config=None):
    j = util._Janitor()
    return j

def _getSuite(config):
    def _dbg(msg):
        log.msg(iface=itrial.ITrialDebug, parseargs=msg)
    reporterKlass = _getReporter(config)
    log.msg(iface=ITrialDebug, reporter="using reporter reporterKlass: %r"
            % (reporterKlass,))
    
    suite = runner.TrialRoot(reporterKlass(
        tbformat=config['tbformat'],
        args=config['reporter-args'],
        realtime=config['rterrors']),
        _getJanitor(),
        benchmark=config['benchmark'])
    suite.couldNotImport.update(config['_couldNotImport'])
    
    for package in config['packages']:
        if isinstance(package, types.StringType):
            try:
                package = reflect.namedModule(package)
            except ImportError, e:
                suite.couldNotImport[package] = failure.Failure()
                continue
        if config['recurse']:
            _dbg("addPackageRecursive(%s)" % (package,))
            try:
                suite.addPackageRecursive(package)
            except ImportError:
                suite.couldNotImport[package] = failure.Failure()
                continue
        else:
            _dbg("addPackage(%s)" % (package,))
            suite.addPackage(package)

    for module in config['modules']:
        _dbg("addingModules: %s" % module)
        suite.addModule(module)
    for testcase in config['testcases']:
        if isinstance(testcase, types.StringType):
            case = reflect.namedObject(testcase)
        else:
            case = testcase
        suite.addTestClass(case)
    for testmethod in config['methods']:
        suite.addMethod(testmethod)
    return suite


def _setUpTestdir():
    testdir = osp.normpath(osp.abspath("_trial_temp"))
    if osp.exists(testdir):
       try:
           shutil.rmtree(testdir)
       except OSError, e:
           print ("could not remove path, caught OSError [Errno %s]: %s"
                  % (e.errno,e.strerror))
           try:
               os.rename(testdir, os.path.abspath("_trial_temp_old%s"
                                                  % random.randint(0, 99999999)))
           except OSError, e:
               print ("could not rename path, caught OSError [Errno %s]: %s"
                      % (e.errno,e.strerror))
               raise

    os.mkdir(testdir)
    os.chdir(testdir)


def _getDebugger(config):
    dbg = pdb.Pdb()
    try:
        import readline
    except ImportError:
        print "readline module not available"
        hasattr(sys, 'exc_clear') and sys.exc_clear()
        pass

    origdir = config['_origdir']
    for path in opj(origdir, '.pdbrc'), opj(origdir, 'pdbrc'):
        if osp.exists(path):
            try:
                rcFile = file(path, 'r')
            except IOError:
                hasattr(sys, 'exc_clear') and sys.exc_clear()
            else:
                dbg.rcLines.extend(rcFile.readlines())
    return dbg

def _setUpDebugging(config, suite):
    suite.debugger = suite.reporter.debugger = True
    _getDebugger(config).runcall(suite.run, config['random'])

def _doProfilingRun(config, suite):
    if config['until-failure']:
        raise RuntimeError, \
              "you cannot use both --until-failure and --profile"
    import profile
    prof = profile.Profile()
    try:
        prof.runcall(suite.run, config['random'])
        prof.dump_stats('profile.data')
    except SystemExit:
        pass
    prof.print_stats()

def call_until_failure(f, *args, **kwargs):
    count = 1
    print "Test Pass %d" % count
    suite = f(*args, **kwargs)
    while itrial.ITestStats(suite).allPassed:
        count += 1
        print "Test Pass %d" % count
        suite = f(*args, **kwargs)
    return suite


class DryRunVisitor(TestVisitor):

    def __init__(self, reporter):
        self.reporter = reporter
        
    def visitModule(self, testModuleSuite):
        # FIXME -- the reporter expects this to be a real module
        orig = testModuleSuite.original
        if hasattr(orig, '__name__'):
            self.reporter.startModule(orig)

    def visitModuleAfter(self, testModuleSuite):
        # FIXME -- the reporter expects this to be a real module
        orig = testModuleSuite.original
        if hasattr(orig, '__name__'):
            self.reporter.endModule(orig)

    def visitClass(self, testClassSuite):
        # FIXME -- the reporter expects _testCase to be a real class
        if hasattr(testClassSuite, '_testCase'):
            self.reporter.startClass(testClassSuite._testCase)

    def visitClassAfter(self, testClassSuite):
        # FIXME -- the reporter expects _testCase to be a real class
        if hasattr(testClassSuite, '_testCase'):
            self.reporter.endClass(testClassSuite._testCase)

    def visitCase(self, testCase):
        self.reporter.startTest(testCase)
        self.reporter.endTest(testCase)


def reallyRun(config):
    if not config['dry-run'] and config['until-failure']:
        if not config['debug']:
            def _doRun(config):
                suite = _getSuite(config)
                suite.run(config['random'])
                return suite
            return call_until_failure(_doRun, config)
        else:
            def _doRun(config):
                suite = _getSuite(config)
                suite.debugger = suite.reporter.debugger = True
                suite.run(config['random'])
                return suite
            return _getDebugger(config).runcall(call_until_failure, _doRun,
                                                config)

    suite = _getSuite(config)
    if config['dry-run']:
        suite.setStartTime()
        suite.visit(DryRunVisitor(suite.reporter))
        suite._kickStopRunningStuff()
    elif config['debug']:
        _setUpDebugging(config, suite)
    elif config['profile']:
        _doProfilingRun(config, suite)
    else:
        suite.run(config['random'])
    return suite


def run():
    _monkeyPatchPyunit()

    if len(sys.argv) == 1:
        sys.argv.append("--help")

    config = Options()

    try:
        config.parseOptions()
    except usage.error, ue:
        raise SystemExit, "%s: %s" % (sys.argv[0], ue)

    _initialDebugSetup(config)

    suite = reallyRun(config)

    if config.tracer:
        sys.settrace(None)
        results = config.tracer.results()
        results.write_results(show_missing=1, summary=False,
                              coverdir=config.coverdir)

    sys.exit(not itrial.ITestStats(suite).allPassed)

