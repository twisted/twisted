# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.names.tap}.
"""
import os
import sys
from StringIO import StringIO

from twisted.python.filepath import FilePath
from twisted.trial.unittest import SkipTest, TestCase


class ExampleTestBase(object):
    """
    This is a mixin which adds an example to the path, tests it, and then
    removes it from the path and unimports the modules which the test loaded.
    Test cases which test example code and documentation listings should use
    this.

    This is done this way so that examples can live in isolated path entries,
    next to the documentation, replete with their own plugin packages and
    whatever other metadata they need.  Also, example code is a rare instance
    of it being valid to have multiple versions of the same code in the
    repository at once, rather than relying on version control, because
    documentation will often show the progression of a single piece of code as
    features are added to it, and we want to test each one.
    """

    examplePath = None

    def setUp(self):
        """
        Add our example directory to the path and record which modules are
        currently loaded.
        """
        self.fakeErr = StringIO()
        self.originalErr, sys.stderr = sys.stderr, self.fakeErr
        self.originalPath = sys.path[:]
        self.originalModules = sys.modules.copy()
        here = FilePath(__file__).parent().parent().parent().parent()
        for childName in self.examplePath:
            here = here.child(childName)
        if not here.exists():
            raise SkipTest("Examples (%s) not found - cannot test" % (here.path,))
        sys.path.append(here.parent().path)
        # Import the example as a module
        moduleName = here.basename().split('.')[0]
        self.example = __import__(moduleName)
        self.examplePath = here


    def tearDown(self):
        """
        Remove the example directory from the path and remove all modules loaded by
        the test from sys.modules.
        """
        sys.modules.clear()
        sys.modules.update(self.originalModules)
        sys.path[:] = self.originalPath
        sys.stderr = self.originalErr


    def test_executable(self):
        """
        The example scripts should start with the standard shebang
        line and should be executable.
        """
        self.assertEquals(
            self.examplePath.open().readline().rstrip(),
            '#!/usr/bin/env python')

        mode = oct(os.stat(self.examplePath.path).st_mode)[-3:]
        self.assertEquals(
            mode, '775',
            'Wrong permissions. %r on %r' % (mode, self.examplePath.path))


    def test_usage(self):
        """
        The example script prints a usage message to stderr and raises
        SystemExit if it is passed incorrect command line
        arguments. The first line should contain a USAGE summary and
        the last line should contain an ERROR, explaining that
        incorrect arguments were supplied.
        """
        self.assertRaises(SystemExit, self.example.main, None)
        err = self.fakeErr.getvalue().splitlines()
        self.assertEquals(err[0][:len('USAGE:')], 'USAGE:')
        self.assertEquals(err[-1][:len('ERROR:')], 'ERROR:')


class TestDnsTests(ExampleTestBase, TestCase):
    """
    Tests for the testdns.py example script.
    """

    examplePath = 'doc/names/examples/testdns.py'.split('/')


class GetHostByNameTests(ExampleTestBase, TestCase):
    """
    Tests for the gethostbyname.py example script.
    """

    examplePath = 'doc/names/examples/gethostbyname.py'.split('/')


class DnsServiceTests(ExampleTestBase, TestCase):
    """
    Tests for the dns-service.py example script.
    """

    examplePath = 'doc/names/examples/dns-service.py'.split('/')
