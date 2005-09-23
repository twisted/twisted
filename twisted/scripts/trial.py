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
from twisted.trial import adapters, reporter
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


def _parseLocalVariables(line):
    """Accepts a single line in Emacs local variable declaration format and
    returns a dict of all the variables {name: value}.
    Raises ValueError if 'line' is in the wrong format.

    See http://www.gnu.org/software/emacs/manual/html_node/File-Variables.html
    """
    paren = '-*-'
    start = line.find(paren) + len(paren)
    end = line.rfind(paren)
    if start == -1 or end == -1:
        raise ValueError("%r not a valid local variable declaration" % (line,))
    items = line[start:end].split(';')
    localVars = {}
    for item in items:
        if len(item.strip()) == 0:
            continue
        split = item.split(':')
        if len(split) != 2:
            raise ValueError("%r contains invalid declaration %r"
                             % (line, item))
        localVars[split[0].strip()] = split[1].strip()
    return localVars


def loadLocalVariables(filename):
    """Accepts a filename and attempts to load the Emacs variable declarations
    from that file, simulating what Emacs does.

    See http://www.gnu.org/software/emacs/manual/html_node/File-Variables.html
    """
    f = file(filename, "r")
    lines = [f.readline(), f.readline()]
    f.close()
    for line in lines:
        try:
            return _parseLocalVariables(line)
        except ValueError:
            pass
    return {}


def isTestFile(filename):
    """Returns true if 'filename' looks like a file containing unit tests.
    False otherwise.  Doesn't care whether filename exists.
    """
    basename = os.path.basename(filename)
    return (basename.startswith('test_')
            and os.path.splitext(basename)[1] == ('.py'))


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
        usage.Options.__init__(self)
        self._logObserver = None
        self['tests'] = []
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
        "Filename to grep for test cases (-*- test-case-name)"
        # If the filename passed to this parameter looks like a test module
        # we just add that to the test suite.
        #
        # If not, we inspect it for an Emacs buffer local variable called
        # 'test-case-name'.  If that variable is declared, we try to add its
        # value to the test suite as a module.
        #
        # This parameter allows automated processes (like Buildbot) to pass
        # a list of files to Trial with the general expectation of "these files,
        # whatever they are, will get tested"
        if not os.path.isfile(filename):
            raise usage.UsageError("File %r doesn't exist" % (filename,))
        filename = os.path.abspath(filename)
        if isTestFile(filename):
            self['tests'].append(filename)
            return            
        else:
            localVars = loadLocalVariables(filename)
            moduleName = localVars.get('test-case-name', None)
        if moduleName is not None and moduleName not in self['tests']:
            self['tests'].append(moduleName)

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

    opt_x = opt_extra

    tracer = None

    def parseArgs(self, *args):
        def _dbg(msg):
            if self._logObserver is not None:
                log.msg(iface=ITrialDebug, parseargs=msg)
        self['tests'].extend(args)
        if self.extra is not None:
            self['tests'].extend(self.extra)

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


def _getRunner(config):
    def _dbg(msg):
        log.msg(iface=itrial.ITrialDebug, parseargs=msg)
    reporterKlass = _getReporter(config)
    log.msg(iface=ITrialDebug, reporter="using reporter reporterKlass: %r"
            % (reporterKlass,))

    reporter = reporterKlass(tbformat=config['tbformat'],
                             args=config['reporter-args'],
                             realtime=config['rterrors'])
    root = runner.TrialRoot(reporter)
    root.addTest(_getSuite(config, reporter))
    return root


def _getSuite(config, reporter):
    loader = _getLoader(config, reporter)
    suite = runner.TestSuite()
    for test in config['tests']:
        if isinstance(test, str):
            suite.addTest(loader.loadByName(test, recurse=config['recurse']))
        else:
            suite.addTest(loader.loadAnything(test,
                                              recurse=config['recurse']))
    for error in loader.getImportErrors():
        reporter.reportImportError(*error)
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


def _getLoader(config, reporter):
    loader = runner.SafeTestLoader()
    if config['random']:
        randomer = random.Random()
        randomer.seed(config['random'])
        loader.sorter = lambda x : randomer.random()
        reporter.write('Running tests shuffled with seed %d\n'
                       % config['random'])
    return loader


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

def _doDebuggingRun(config, suite):
    _getDebugger(config).runcall(suite.run)

def _doProfilingRun(config, suite):
    if config['until-failure']:
        raise RuntimeError, \
              "you cannot use both --until-failure and --profile"
    import profile
    prof = profile.Profile()
    try:
        prof.runcall(suite.run)
        prof.dump_stats('profile.data')
    except SystemExit:
        pass
    prof.print_stats()

def call_until_failure(f, *args, **kwargs):
    count = 1
    print "Test Pass %d" % count
    suite = f(*args, **kwargs)
    while suite.reporter.wasSuccessful():
        count += 1
        print "Test Pass %d" % count
        suite = f(*args, **kwargs)
    return suite


class DryRunVisitor(TestVisitor):

    def __init__(self, reporter):
        self.reporter = reporter
        
    def visitModule(self, testModuleSuite):
        orig = testModuleSuite.original
        self.reporter.startModule(orig)

    def visitModuleAfter(self, testModuleSuite):
        orig = testModuleSuite.original
        self.reporter.endModule(orig)

    def visitClass(self, testClassSuite):
        orig = testClassSuite.original
        self.reporter.startClass(orig)

    def visitClassAfter(self, testClassSuite):
        orig = testClassSuite.original
        self.reporter.endClass(orig)

    def visitCase(self, testCase):
        self.reporter.startTest(testCase)
        self.reporter.endTest(testCase)


def reallyRun(config):
    root = _getRunner(config)
    if config['dry-run']:
        root.setStartTime()
        root.visit(DryRunVisitor(root.reporter))
        root._kickStopRunningStuff()
    elif config['until-failure']:
        if config['debug']:
            _getDebugger(config).runcall(call_until_failure, root.run)
        else:
            call_until_failure(root.run)
    elif config['debug']:
        _doDebuggingRun(config, root)
    elif config['profile']:
        _doProfilingRun(config, root)
    else:
        root.run()
    return root


def run():
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

    sys.exit(not suite.reporter.wasSuccessful())

