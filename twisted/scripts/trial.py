# -*- test-case-name: twisted.trial.test.test_trial -*-

# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.


import sys, os, errno, pdb, shutil, random, gc, warnings, time

from twisted.internet import defer
from twisted.application import app
from twisted.python import usage, reflect, failure, log
from twisted import plugin
from twisted.python.util import spewer
from twisted.trial import runner, itrial, reporter
from twisted.trial.unittest import TestVisitor


class PluginError(Exception):
    pass


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
                ["rterrors", "e", "realtime errors, print out tracebacks as "
                 "soon as they occur"],
                ["debug", "b", "Run tests in the Python debugger. Will load "
                 "'.pdbrc' from current directory if it exists."],
                ["debug-stacktraces", "B", "Report Deferred creation and "
                 "callback stack traces"],
                ["nopm", None, "don't automatically jump into debugger for "
                 "postmorteming of exceptions"],
                ["dry-run", 'n', "do everything but run the tests"],
                ["profile", None, "Run tests under the Python profiler"],
                ["until-failure", "u", "Repeat test until it fails"],
                ["recurse", "R",
                 "Search packages recursively (enabled by default, DEPRECATED)"],
                ["no-recurse", "N", "Don't recurse into packages"],
                ['psyco', None, 'run tests with psyco.full() (EXPERIMENTAL)'],
                ['suppresswarnings', None,
                 'Only print warnings to log, not stdout'],
                ['help-reporters', None,
                 "Help on available output plugins (reporters)"]
                ]

    optParameters = [["reactor", "r", None,
                      "Which reactor to use out of: " + \
                      ", ".join(app.reactorTypes.keys()) + "."],
                     ["logfile", "l", "test.log", "log file name"],
                     ["random", "z", None,
                      "Run tests in random order using the specified seed"],
                     ["reporter-args", None, None,
                      "a string passed to the reporter's 'args' kwarg. "
                      "DEPRECATED"]]

    zsh_actions = {"reactor":"(%s)" % " ".join(app.reactorTypes.keys())}
    zsh_actionDescr = {"logfile":"log file name",
                       "random":"random seed"}
    zsh_extras = ["*:file|module|package|TestCase|testMethod:_files -g '*.py'"]

    fallbackReporter = reporter.TreeReporter
    extra = None
    tracer = None

    def __init__(self):
        self['tests'] = []
        self['reporter'] = None
        self._loadReporters()
        usage.Options.__init__(self)

    def _loadReporters(self):
        self.optToQual = {}
        for p in plugin.getPlugins(itrial.IReporter):
            self.optFlags.append([p.longOpt, p.shortOpt, p.description])
            qual = "%s.%s" % (p.module, p.klass)
            self.optToQual[p.longOpt] = qual
            if getattr(p, 'default', False):
                self.fallbackReporter = reflect.namedAny(qual)

    def getReporter(self):
        """return the class of the selected reporter
        @param config: a usage.Options instance after parsing options
        """
        if not hasattr(self, 'optToQual'):
            self._loadReporters()
        for opt, qual in self.optToQual.iteritems():
            if self[opt]:
                warnings.warn('Setting the reporter using flags is deprecated.'
                              ' Use --reporter instead',
                              category=DeprecationWarning)
                nany = reflect.namedAny(qual)
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
        warnings.warn("--coverage will become a flag in Twisted 2.2",
                      stacklevel=4, category=DeprecationWarning)
        print "Setting coverage directory to %s." % (coverdir,)
        import trace

        # begin monkey patch ---------------------------
        #   Before Python 2.4, this function asserted that 'filename' had
        #   to end with '.py'  This is wrong for at least two reasons:
        #   1.  We might be wanting to find executable line nos in a script
        #   2.  The implementation should use os.splitext
        #   This monkey patch is the same function as in the stdlib (v2.3)
        #   but with the assertion removed.
        def find_executable_linenos(filename):
            """Return dict where keys are line numbers in the line number
            table.
            """
            #assert filename.endswith('.py') # YOU BASTARDS
            try:
                prog = open(filename).read()
                prog = '\n'.join(prog.splitlines()) + '\n'
            except IOError, err:
                sys.stderr.write("Not printing coverage data for %r: %s\n"
                                 % (filename, err))
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
            sys.stderr.write("File %r doesn't exist\n" % (filename,))
            return
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
        """The reporter to use for this test run.  See --help-reporters
        for more info.
        """
        if opt is None:
            raise UsageError, 'must specify a fully qualified class name'
        if opt in self.optToQual:
            opt = self.optToQual[opt]
        else:
            warnings.warn("Only pass names of Reporter plugins to --reporter. "
                          "See --help-reporters for more info.",
                          category=DeprecationWarning)
        self['reporter'] = reflect.namedAny(opt)

    def opt_help_reporters(self):
        synopsis = ("Trial's output can be customized using plugins called "
                    "Reporters. You can\nselect any of the following "
                    "reporters using --reporter=<foo>\n")
        print synopsis
        for p in plugin.getPlugins(itrial.IReporter):
            print '   ', p.longOpt, '\t', p.description
        print
        sys.exit(0)
        
    def opt_disablegc(self):
        """Disable the garbage collector"""
        gc.disable()

    def opt_tbformat(self, opt):
        """Specify the format to display tracebacks with. Valid formats are
        'plain', 'emacs', and 'cgitb' which uses the nicely verbose stdlib
        cgitb.text function"""
        try:
            self['tbformat'] = TBFORMAT_MAP[opt]
        except KeyError:
            raise usage.UsageError(
                "tbformat must be 'plain', 'emacs', or 'cgitb'.")

    def opt_extra(self, arg):
        """
        Add an extra argument.  (This is a hack necessary for interfacing with
        emacs's `gud'.)
        """
        if self.extra is None:
            self.extra = []
        self.extra.append(arg)
    opt_x = opt_extra

    def opt_recursionlimit(self, arg):
        """see sys.setrecursionlimit()"""
        try:
            sys.setrecursionlimit(int(arg))
        except (TypeError, ValueError):
            raise usage.UsageError(
                "argument to recursionlimit must be an integer")

    def opt_psyco(self):
        warnings.warn("--psyco option is deprecated and does nothing. "
                      "Will be removed in Twisted 2.2",
                      stacklevel=4, category=DeprecationWarning)

    def opt_recurse(self):
        warnings.warn("-R, --recurse are now the default. The options are "
                      "deprecated, and will be remove in Twisted 2.2",
                      stacklevel=4, category=DeprecationWarning)

    def opt_random(self, option):
        try:
            self['random'] = long(option)
        except ValueError:
            raise usage.UsageError(
                "Argument to --random must be a positive integer")
        else:
            if self['random'] < 0:
                raise usage.UsageError(
                    "Argument to --random must be a positive integer")
            elif self['random'] == 0:
                self['random'] = long(time.time() * 100)

    def parseArgs(self, *args):
        ## XXX - hack around the directory changing evil
        safeArgs = []
        for arg in args:
            if os.path.exists(arg):
                arg = os.path.abspath(arg)
            safeArgs.append(arg)
        self['tests'].extend(safeArgs)
        if self.extra is not None:
            self['tests'].extend(self.extra)

    def postOptions(self):
        self['_origdir'] = os.getcwd()
        # Want to do this stuff as early as possible
        _setUpTestdir()
        _setUpLogging(self)
        if not self.has_key('tbformat'):
            self['tbformat'] = 'default'
        if self['nopm']:
            if not self['debug']:
                raise usage.UsageError("you must specify --debug when using "
                                       "--nopm ")
            failure.DO_POST_MORTEM = False
        if self['reporter-args']:
            warnings.warn("--reporter-args is deprecated. Use plugin instead.",
                          category=DeprecationWarning)

    
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
    if config['reporter'] is not None:
        reporterKlass = config['reporter']
    else:
        reporterKlass = config.getReporter()
    reporter = reporterKlass(tbformat=config['tbformat'],
                             args=config['reporter-args'],
                             realtime=config['rterrors'])
    return reporter


def _getSuite(config, reporter):
    loader = _getLoader(config, reporter)
    suite = runner.TestSuite()
    recurse = not config['no-recurse']
    for test in config['tests']:
        if isinstance(test, str):
            suite.addTest(loader.loadByName(test, recurse))
        else:
            suite.addTest(loader.loadAnything(test, recurse))
    for error in loader.getImportErrors():
        reporter.reportImportError(*error)
    return suite
    

def _setUpTestdir():
    testdir = os.path.normpath(os.path.abspath("_trial_temp"))
    if os.path.exists(testdir):
       try:
           shutil.rmtree(testdir)
       except OSError, e:
           print ("could not remove path, caught OSError [Errno %s]: %s"
                  % (e.errno,e.strerror))
           try:
               os.rename(testdir,
                         os.path.abspath("_trial_temp_old%s"
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
    origdir = config['_origdir']
    for path in (os.path.join(origdir, '.pdbrc'),
                 os.path.join(origdir, 'pdbrc')):
        if os.path.exists(path):
            try:
                rcFile = file(path, 'r')
            except IOError:
                hasattr(sys, 'exc_clear') and sys.exc_clear()
            else:
                dbg.rcLines.extend(rcFile.readlines())
    return dbg

def _doDebuggingRun(config, root, suite):
    _getDebugger(config).runcall(root.run, suite)

def _doProfilingRun(config, root, suite):
    if config['until-failure']:
        raise RuntimeError, \
              "you cannot use both --until-failure and --profile"
    import profile
    prof = profile.Profile()
    try:
        prof.runcall(root.run, suite)
        prof.dump_stats('profile.data')
    except SystemExit:
        pass
    prof.print_stats()

def call_until_failure(reporter, f, *args, **kwargs):
    count = 1
    print "Test Pass %d" % count
    suite = f(*args, **kwargs)
    while reporter.wasSuccessful():
        count += 1
        print "Test Pass %d" % count
        f(*args, **kwargs)
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
    reporter = _getReporter(config)
    suite = _getSuite(config, reporter)
    root = runner.TrialRoot(reporter)
    if config['dry-run']:
        root.setStartTime()
        suite.visit(DryRunVisitor(root.reporter))
        root._kickStopRunningStuff()
    elif config['until-failure']:
        if config['debug']:
            _getDebugger(config).runcall(call_until_failure, reporter,
                                         root.run, suite)
        else:
            call_until_failure(reporter, root.run, suite)
    elif config['debug']:
        _doDebuggingRun(config, root, suite)
    elif config['profile']:
        _doProfilingRun(config, root, suite)
    else:
        root.run(suite)
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

