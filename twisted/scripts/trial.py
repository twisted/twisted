# -*- test-case-name: twisted.trial.test.test_script -*-

# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.


import sys, os, shutil, random, gc, time

from twisted.internet import defer
from twisted.application import app
from twisted.python import usage, reflect, failure, log
from twisted import plugin
from twisted.python.util import spewer
from twisted.trial import runner, itrial, reporter


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


def getTestModules(filename):
    testCaseVar = loadLocalVariables(filename).get('test-case-name', None)
    if testCaseVar is None:
        return []
    return testCaseVar.split(',')


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
                ["no-recurse", "N", "Don't recurse into packages"],
                ['suppresswarnings', None,
                 'Only print warnings to log, not stdout. DEPRECATED.'],
                ['help-reporters', None,
                 "Help on available output plugins (reporters)"]
                ]

    optParameters = [["reactor", "r", None,
                      "Which reactor to use out of: " + \
                      ", ".join(app.reactorTypes.keys()) + "."],
                     ["logfile", "l", "test.log", "log file name"],
                     ["random", "z", None,
                      "Run tests in random order using the specified seed"],
                     ['temp-directory', None, '_trial_temp',
                      'Path to use as working directory for tests.']]

    zsh_actions = {"reactor":"(%s)" % " ".join(app.reactorTypes.keys()),
                   "tbformat":"(plain emacs cgitb)"}
    zsh_actionDescr = {"logfile":"log file name",
                       "random":"random seed"}
    zsh_extras = ["*:file|module|package|TestCase|testMethod:_files -g '*.py'"]

    fallbackReporter = reporter.TreeReporter
    extra = None
    tracer = None

    def __init__(self):
        self['tests'] = []
        self._loadReporters()

        # Yes, I know I'm mutating a class variable.
        self.zsh_actions["reporter"] = "(%s)" % " ".join(self.optToQual.keys())
        usage.Options.__init__(self)

    def _loadReporters(self):
        if self._supportsColor():
            default = 'verbose'
        else:
            default = 'bwverbose'
        self.optToQual = {}
        for p in plugin.getPlugins(itrial.IReporter):
            qual = "%s.%s" % (p.module, p.klass)
            self.optToQual[p.longOpt] = qual
            if p.longOpt == default:
                self['reporter'] = reflect.namedAny(qual)

    def _supportsColor(self):
        supportedTerms = ['xterm', 'xterm-color', 'linux', 'screen']
        if not os.environ.has_key('TERM'):
            return False
        return os.environ['TERM'] in supportedTerms

    def opt_reactor(self, reactorName):
        # this must happen before parseArgs does lots of imports
        app.installReactor(reactorName)
        print "Using %s reactor" % app.reactorTypes[reactorName]

    def opt_coverage(self):
        """
        Generate coverage information in the given directory (relative to
        trial temporary working directory). Requires Python 2.3.3.
        """
        coverdir = 'coverage'
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

        self.coverdir = os.path.abspath(os.path.join(self['temp-directory'], coverdir))
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
        else:
            for test in getTestModules(filename):
                if test not in self['tests']:
                    self['tests'].append(test)
            self['tests'].extend(getTestModules(filename))

    def opt_spew(self):
        """Print an insanely verbose log of everything that happens.  Useful
        when debugging freezes or locks in complex code."""
        sys.settrace(spewer)
        
    def opt_reporter(self, opt):
        """The reporter to use for this test run.  See --help-reporters
        for more info.
        """
        if opt in self.optToQual:
            opt = self.optToQual[opt]
        else:
            raise usage.UsageError("Only pass names of Reporter plugins to "
                                   "--reporter. See --help-reporters for "
                                   "more info.")
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
        self['tests'].extend(args)
        if self.extra is not None:
            self['tests'].extend(self.extra)

    def postOptions(self):
        if self['suppresswarnings']:
            warnings.warn('--suppresswarnings deprecated. Is a no-op',
                          category=DeprecationWarning)
        if not self.has_key('tbformat'):
            self['tbformat'] = 'default'
        if self['nopm']:
            if not self['debug']:
                raise usage.UsageError("you must specify --debug when using "
                                       "--nopm ")
            failure.DO_POST_MORTEM = False

    
def _initialDebugSetup(config):
    # do this part of debug setup first for easy debugging of import failures
    if config['debug']:
        failure.startDebugMode()
    if config['debug'] or config['debug-stacktraces']:
        defer.setDebugging(True)


def _getSuite(config):
    loader = _getLoader(config)
    suite = runner.TestSuite()
    recurse = not config['no-recurse']
    for test in config['tests']:
        if isinstance(test, str):
            suite.addTest(loader.loadByName(test, recurse))
        else:
            suite.addTest(loader.loadAnything(test, recurse))
    return suite
    

def _getLoader(config):
    loader = runner.TestLoader()
    if config['random']:
        randomer = random.Random()
        randomer.seed(config['random'])
        loader.sorter = lambda x : randomer.random()
        print 'Running tests shuffled with seed %d\n' % config['random']
    return loader


def _makeRunner(config):
    mode = None
    if config['debug']:
        mode = runner.TrialRunner.DEBUG
    if config['dry-run']:
        mode = runner.TrialRunner.DRY_RUN
    return runner.TrialRunner(config['reporter'],
                              mode=mode,
                              profile=config['profile'],
                              logfile=config['logfile'],
                              tracebackFormat=config['tbformat'],
                              realTimeErrors=config['rterrors'],
                              workingDirectory=config['temp-directory'])


def run():
    if len(sys.argv) == 1:
        sys.argv.append("--help")
    config = Options()
    try:
        config.parseOptions()
    except usage.error, ue:
        raise SystemExit, "%s: %s" % (sys.argv[0], ue)
    _initialDebugSetup(config)
    trialRunner = _makeRunner(config)
    suite = _getSuite(config)
    if config['until-failure']:
        test_result = trialRunner.runUntilFailure(suite)
    else:
        test_result = trialRunner.run(suite)
    if config.tracer:
        sys.settrace(None)
        results = config.tracer.results()
        results.write_results(show_missing=1, summary=False,
                              coverdir=config.coverdir)
    sys.exit(not test_result.wasSuccessful())

