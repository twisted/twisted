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

from twisted.python import usage
from twisted.trial import unittest
import sys, os

class Options(usage.Options):
    optFlags = [["help", "h"],
                ["text", "t", "Text mode (ignored)"],
                ["verbose", "v", "Verbose output"]]
    optParameters = [["reactor", "r", None,
                      "The Twisted reactor to install before running the tests (looked up as a module contained in twisted.internet)"],
                     ["logfile", "l", None, "log file name"]]

    def __init__(self):
        usage.Options.__init__(self)
        self['modules'] = []
        self['packages'] = []

    def opt_module(self, module):
        "Module to test"
        self['modules'].append(module)

    def opt_package(self, package):
        "Package to test"
        self['packages'].append(package)

    opt_m = opt_module
    opt_p = opt_package


def run():
    if len(sys.argv) == 1:
        sys.argv.append("--help")

    config = Options()
    try:
        config.parseOptions()
    except usage.error, ue:
        print "%s: %s" % (sys.argv[0], ue)
        os._exit(1)

    if config['reactor']:
        from twisted.python import reflect
        mod = 'twisted.internet.' + config['reactor']
        print "Using %s reactor" % mod
        reflect.namedModule(mod).install()

    suite = unittest.TestSuite()
    for package in config['packages']:
        suite.addPackage(package)
    for module in config['modules']:
        suite.addModule(module)

##     testdir = "_trial_temp"
##     if os.path.exists(testdir):
##         import shutil
##         shutil.rmtree(testdir)
##     os.mkdir(testdir)
##     os.chdir(testdir)

    if config['logfile']:
       from twisted.python import log
       log.startLogging(open(config['logfile'], 'a'), 0)

    if config['verbose']:
        suite.run(unittest.VerboseTextReporter(sys.stdout))
    else:
        suite.run(unittest.TextReporter(sys.stdout))

if __name__ == '__main__':
    run()
