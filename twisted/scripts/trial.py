#!/usr/bin/env python
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

from twisted.python import usage, reflect
from twisted.trial import unittest
import sys, os, types, inspect

class Options(usage.Options):
    synopsis = """%s [options] [[file|package|module|TestCase|testmethod]...]
    """ % (
        os.path.basename(sys.argv[0]),)
    optFlags = [["help", "h"],
                ["text", "t", "Text mode (ignored)"],
                ["verbose", "v", "Verbose output"],
                ["bwverbose", "o", "Colorless verbose output"],
                ["jelly", "j", "Jelly (machine-readable) output"],
                ["summary", "s", "summary output"],
                ["debug", "b", "Run tests in the Python debugger"]]
    optParameters = [["reactor", "r", None,
                      "The Twisted reactor to install before running the tests (looked up as a module contained in twisted.internet)"],
                     ["logfile", "l", "test.log", "log file name"],
                     ["random", "z", None,
                      "Run tests in random order using the specified seed"]]

    def __init__(self):
        usage.Options.__init__(self)
        self['modules'] = []
        self['packages'] = []
        self['testcases'] = []
        self['methods'] = []

    def opt_reactor(self, reactorName):
        # this must happen before parseArgs does lots of imports
        mod = 'twisted.internet.' + reactorName
        print "Using %s reactor" % mod
        reflect.namedModule(mod).install()
        
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

    opt_m = opt_module
    opt_p = opt_package
    opt_c = opt_testcase
    opt_M = opt_method

    opt_f = opt_file

    def parseArgs(self, *args):
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

            # this is a problem: it imports the module, which installs a
            # reactor, and this happens before --reactor is processed
            try:
                arg = reflect.namedAny(arg)
            except ValueError:
                raise usage.UsageError, "Can't find anything named %r to run" % arg

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

def run():
    if len(sys.argv) == 1:
        sys.argv.append("--help")

    config = Options()
    try:
        config.parseOptions()
    except usage.error, ue:
        print "%s: %s" % (sys.argv[0], ue)
        os._exit(1)

    suite = unittest.TestSuite()
    for package in config['packages']:
        suite.addPackage(package)
    for module in config['modules']:
        suite.addModule(module)
    for testcase in config['testcases']:
        if type(testcase) is types.StringType:
            case = reflect.namedObject(testcase)
        else:
            case = testcase
        if type(case) is types.ClassType and unittest.isTestClass(case):
            suite.addTestClass(case)
    for testmethod in config['methods']:
        suite.addMethod(testmethod)

    testdir = "_trial_temp"
    if os.path.exists(testdir):
       import shutil
       shutil.rmtree(testdir)
    os.mkdir(testdir)
    os.chdir(testdir)

    if config['logfile']:
       from twisted.python import log
       log.startLogging(open(config['logfile'], 'a'), 0)

    if config['verbose']:
        reporter = unittest.TreeReporter(sys.stdout)
    elif config['bwverbose']:
        reporter = unittest.VerboseTextReporter(sys.stdout)
    elif config['summary']:
        reporter = unittest.MinimalReporter(sys.stdout)
    elif config['jelly']:
        import twisted.trial.remote
        reporter = twisted.trial.remote.JellyReporter(sys.stdout)
    else:
        reporter = unittest.TextReporter(sys.stdout)

    if config['debug']:
        reporter.debugger = 1
        import pdb
        dbg = pdb.Pdb()
        try:
            rcFile = open("../.pdbrc")
        except IOError:
            pass
        else:
            dbg.rcLines.extend(rcFile.readlines())
        dbg.run("suite.run(reporter, config['random'])", globals(), locals())
    else:
        suite.run(reporter, config['random'])
        sys.exit(not reporter.allPassed())

if __name__ == '__main__':
    run()
