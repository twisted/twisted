
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

"""
Amalgamate all Twisted testcases
"""

from pyunit import unittest
from twisted.internet import default
default.install()

import string
import traceback
import glob
import sys
from os import path

# List which tests we *aren't* running, rather than the ones we are.
# Less likely to forget about them this way.
exclude_tests = [
    'test_todo', # The PIM module doesn't exist anymore.
    ]

# If a module with this name is found, it's placed last on the list.
last_test = 'test_import'

class TestLoader(unittest.TestLoader):
    """TestLoader with a method to load all test_* modules in its package.
    """

    def __init__(self):
        self.load_errors = []
        self.excluded_tests = []

    def loadTestsFromMyPackage(self):
        """Loads everything named test_*.py in this directory.

        A test module may exclude itself from the suite by assigning
        a non-false value to EXCLUDE_FROM_BIGSUITE.
        """

        testpath = path.dirname(path.abspath(__file__))

        test_files = glob.glob(testpath + '/test_*.py')
        test_mNames = map(lambda fp: path.splitext(path.basename(fp))[0],
                         test_files)

        if last_test in test_mNames:
            test_mNames.remove(last_test)
            test_mNames.append(last_test)

        suites = []
        for name in test_mNames:
            if name in exclude_tests:
                self.excluded_tests.append((name,
                                            "in test_all.excluded_tests"))
                continue

            try:
                module = __import__('twisted.test.%s' % (name,),
                                    locals(), globals(), [name])
                excluded = getattr(module, 'EXCLUDE_FROM_BIGSUITE', None)
                if excluded:
                    self.excluded_tests.append((name, excluded))
                else:
                    suites.append(self.loadTestsFromModule(module))
            except ImportError:
                (type, value, tb) = sys.exc_info()
                errstring = traceback.format_exception(type, value, tb)
                del tb
                self.load_errors.append((name, errstring))

        bigSuite = self.suiteClass(suites)
        return bigSuite

    def loadErrorText(self):
        """Return a string explaining modules which didn't load."""

        lines = []
        for le in self.load_errors:
            lines.append("* %s:\n" % (le[0],))
            lines.extend(le[1])
            lines.append("\n")

        return string.join(lines, '')

from twisted.python import log, runtime
log.msg("opening test.log")
log.logfile = open("test.log", 'a')

def testSuite():
    """unittestgui wants a callable to return a suite."""

    return TestLoader().loadTestsFromMyPackage()
