# -*- test-case-name: twisted.test.test_trial -*-
#
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

# FIXME
# - Hangs.

from twisted.python import usage, reflect, failure
from twisted.trial import unittest, util, reporter as reps
from twisted.application import app

import sys, os, types, inspect
import re

class Options(usage.Options):
    synopsis = """%s [options] [[file|package|module|TestCase|testmethod]...]
    """ % (os.path.basename(sys.argv[0]),)

    optFlags = [["help", "h"],
                ["text", "t", "Text mode (ignored)"],
                ["verbose", "v", "Verbose output"],
                ["timing", None, "Timing output"],
                ["bwverbose", "o", "Colorless verbose output"],
                ["jelly", "j", "Jelly (machine-readable) output"],
                ["summary", "s", "summary output"],
                ["debug", "b", "Run tests in the Python debugger. Will load '.pdbrc' from current directory if it exists."],
                ["profile", None, "Run tests under the Python profiler"],
                ["benchmark", None, "Run performance tests instead of unit tests."],
                ["until-failure", "u", "Repeat test until it fails"],
                ["recurse", "R", "Search packages recursively"]]

    optParameters = [["reactor", "r", None,
                      "Which reactor to use out of: " + \
                      ", ".join(app.reactorTypes.keys()) + "."],
                     ["logfile", "l", "test.log", "log file name"],
                     ["random", "z", None,
                      "Run tests in random order using the specified seed"],
                     ]

    tracer = None

    def __init__(self):
        usage.Options.__init__(self)
        self['modules'] = []
        self['packages'] = []
        self['testcases'] = []
        self['methods'] = []
        self['_couldNotImport'] = {}

    def opt_coverage(self, coverdir):
        """Generate coverage information in the given directory
        (relative to _trial_temp). Requires Python 2.3.3."""
        import trace

        # WOO MONKEY PATCH
        def find_executable_linenos(filename):
            """Return dict where keys are line numbers in the line number table."""
            #assert filename.endswith('.py') # YOU BASTARDS
            try:
                prog = open(filename).read()
            except IOError, err:
                print >> sys.stderr, ("Not printing coverage data for %r: %s"
                                      % (filename, err))
                return {}
            code = compile(prog, filename, "exec")
            strs = trace.find_strings(filename)
            return trace.find_lines(code, strs)

        #kaching!
        trace.find_executable_linenos = find_executable_linenos

        #countfile = abs(os.path.join('_trial_temp', 'coverage.count'))
        self.coverdir = os.path.abspath(os.path.join('_trial_temp', coverdir))
        self.tracer = trace.Trace(count=1, trace=0)#, infile=countfile, outfile=countfile)
        sys.settrace(self.tracer.globaltrace)

    def opt_reactor(self, reactorName):
        # this must happen before parseArgs does lots of imports
        app.installReactor(reactorName)
        print "Using %s reactor" % app.reactorTypes[reactorName]
        
    def opt_testmodule(self, file):
        "Module to find a test case for"
        # only look at the first two lines of the file. Try to behave as
        # much like emacs local-variables scanner as is sensible
        if not os.path.isfile(file):
            return
        # recognize twisted/test/test_foo.py, which is itself a test case
        d,f = os.path.split(file)
        if d == "twisted/test" and f.startswith("test_") and f.endswith(".py"):
            self['modules'].append("twisted.test." + f[:-3])
            return
        f = open(file, "r")
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

    def opt_module(self, module):
        "Module to test"
        self['modules'].append(module)

    def opt_package(self, package):
        "Package to test"
        self['packages'].append(package)

    def opt_testcase(self, case):
        "TestCase to test"
        self['testcases'].append(case)

    def opt_file(self, filename):
        "Filename of module to test"
        from twisted.python import reflect
        self['modules'].append(reflect.filenameToModuleName(filename))

    def opt_method(self, method):
        "Method to test"
        self['methods'].append(method)

    def opt_spew(self):
        """Print an insanely verbose log of everything that happens.  Useful
        when debugging freezes or locks in complex code."""
        from twisted.python.util import spewer
        sys.settrace(spewer)

    def opt_disablegc(self):
        """Disable the garbage collector"""
        import gc
        gc.disable()

    def opt_tbformat(self, opt):
        """Specify the format to display tracebacks with. Valid formats are 'plain' and 'emacs'."""
        if opt not in ('plain', 'emacs'):
            raise usage.UsageError("tbformat must be 'plain' or 'emacs'.")
        self['tbformat'] = opt

    opt_m = opt_module
    opt_p = opt_package
    opt_c = opt_testcase
    opt_M = opt_method

    opt_f = opt_file

    #     ["extra","x", None,
    #      "Add an extra argument.  "
    #      "(This is a hack necessary for "
    #      "interfacing with emacs's `gud'.)" ]
    extra = None
    def opt_extra(self, arg):
        """
        Add an extra argument.  (This is a hack necessary for interfacing with
        emacs's `gud'.)
        """
        if self.extra is None:
            self.extra = []
        self.extra.append(arg)

    opt_x = opt_extra

    def parseArgs(self, *args):
        if self.extra is not None:
            args = list(args)
            args.extend(self.extra)
        for arg in args:
            if (os.sep in arg):
                # It's a file.
                if not os.path.exists(arg):
                    import errno
                    raise IOError(errno.ENOENT, os.strerror(errno.ENOENT), arg)
                if arg.endswith(os.sep) and (arg != os.sep):
                    arg = arg[:-len(os.sep)]
                name = reflect.filenameToModuleName(arg)
                if os.path.isdir(arg):
                    self['packages'].append(name)
                else:
                    self['modules'].append(name)
                continue

            if arg.endswith('.py'):
                # *Probably* a file.
                if os.path.exists(arg):
                    arg = reflect.filenameToModuleName(arg)
                    self['modules'].append(arg)
                    continue

            # a non-default reactor must have been installed by now: it
            # imports the module, which installs a reactor
            try:
                arg = reflect.namedAny(arg)
            except ValueError:
                raise usage.UsageError, "Can't find anything named %r to run" % arg
            except:
                self['_couldNotImport'][arg] = failure.Failure()
                continue

            if inspect.ismodule(arg):
                filename = os.path.basename(arg.__file__)
                filename = os.path.splitext(filename)[0]
                if filename == '__init__':
                    self['packages'].append(arg)
                else:
                    self['modules'].append(arg)
            elif inspect.isclass(arg):
                self['testcases'].append(arg)
            elif inspect.ismethod(arg):
                self['methods'].append(arg)
            else:
                # Umm, seven?
                self['methods'].append(arg)

    def postOptions(self):
        if self['random'] is not None:
            try:
                self['random'] = long(self['random'])
            except ValueError:
                raise usage.UsageError("Argument to --random must be a positive integer")
            else:
                if self['random'] < 0:
                    raise usage.UsageError("Argument to --random must be a positive integer")
                elif self['random'] == 0:
                    import time
                    self['random'] = long(time.time() * 100)

        if not self.has_key('tbformat'):
            self['tbformat'] = 'plain'

def call_until_failure(reporter, callable, *args, **kwargs):
    count = 1
    print "Test Pass %d" % count
    callable(*args, **kwargs)
    while reporter.allPassed():
        count += 1
        print "Test Pass %d" % count
        callable(*args, **kwargs)

def run():
    if len(sys.argv) == 1:
        sys.argv.append("--help")

    config = Options()
    try:
        config.parseOptions()
    except usage.error, ue:
        print "%s: %s" % (sys.argv[0], ue)
        os._exit(1)

    reporter = reallyRun(config)

    if config.tracer:
        sys.settrace(None)
        results = config.tracer.results()
        results.write_results(show_missing=1, summary=False, coverdir=config.coverdir)

    sys.exit(not reporter.allPassed())

def reallyRun(config):
    # do this part of debug setup first for easy debugging of import failures
    if config['debug']:
        from twisted.internet import defer
        from twisted.python import failure
        defer.Deferred.debug = True
        failure.startDebugMode()

    suite = unittest.TestSuite(config['benchmark'])
    suite.couldNotImport.update(config['_couldNotImport'])
    if config['recurse']:
        for package in config['packages']:
            suite.addPackageRecursive(package)
    else:
        for package in config['packages']:
            suite.addPackage(package)
    for module in config['modules']:
        suite.addModule(module)
    for testcase in config['testcases']:
        if type(testcase) is types.StringType:
            case = reflect.namedObject(testcase)
        else:
            case = testcase
        if type(case) is types.ClassType and util.isTestClass(case):
            suite.addTestClass(case)
    for testmethod in config['methods']:
        suite.addMethod(testmethod)

    testdir = os.path.abspath("_trial_temp")
    if os.path.exists(testdir):
       import shutil, random
       try:
          shutil.rmtree(testdir)
       except OSError, e:
          print "Error deleting:", e
          os.rename(testdir, os.path.abspath("_trial_temp_old%s" % random.randint(0, 99999999)))
    os.mkdir(testdir)
    os.chdir(testdir)

    if config['logfile']:
       from twisted.python import log
       # we should SEE deprecation warnings
       def seeWarnings(x):
           if x.has_key('warning'):
               print
               print x['format'] % x
       log.addObserver(seeWarnings)
       log.startLogging(open(config['logfile'], 'a'), 0)

    tbformat = config['tbformat']

    # XXX Yuck. We should just have a --reporter option. Then we could
    # have a dict of {reportername: reporterclass}, look up
    # config['reporter'] in it, and instantiate the result with the
    # args.

    if config['verbose']:
        reporter = reps.TreeReporter(sys.stdout, tbformat)
    elif config['bwverbose']:
        reporter = reps.VerboseTextReporter(sys.stdout, tbformat)
    elif config['summary']:
        reporter = reps.MinimalReporter(sys.stdout)
    elif config['jelly']:
        import twisted.trial.remote
        reporter = twisted.trial.remote.JellyReporter(sys.stdout)
    elif config['timing']:
        reporter = reps.TimingTextReporter(sys.stdout, tbformat)
    else:
        reporter = reps.TextReporter(sys.stdout, tbformat)

    if config['debug']:
        reporter.debugger = 1
        import pdb
        dbg = pdb.Pdb()
        try:
            rcFile = open("../.pdbrc")
        except IOError:
            hasattr(sys, 'exc_clear') and sys.exc_clear()
        else:
            dbg.rcLines.extend(rcFile.readlines())
        if config['until-failure']:
            call_until_failure(reporter,
                               dbg.run,
                               "suite.run(reporter, config['random'])",
                               globals(), locals())
        else:
            dbg.run("suite.run(reporter, config['random'])",
                    globals(), locals())
    elif config['profile']:
        if config['until-failure']:
            raise RuntimeError, \
                  "you cannot use both --until-failure and --profile"
        import profile
        prof = profile.Profile()
        try:
            prof.runcall(suite.run, reporter, config['random'])
            prof.dump_stats('profile.data')
        except SystemExit:
            pass
        prof.print_stats()
    else:
        if config['until-failure']:
            call_until_failure(reporter,
                               suite.run, reporter, config['random'])
        else:
            suite.run(reporter, config['random'])
    return reporter

if __name__ == '__main__':
    run()
