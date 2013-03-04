# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.names} example scripts.
"""

import os
import sys
from StringIO import StringIO

from twisted.internet import defer, utils
from twisted.names import client, error
from twisted.python.filepath import FilePath
from twisted.python import usage
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

    positionalArgCount = 0

    def setUp(self):
        """
        Add our example directory to the path and record which modules are
        currently loaded.
        """
        self.fakeErr = StringIO()
        self.originalErr, sys.stderr = sys.stderr, self.fakeErr
        self.fakeOut = StringIO()
        self.originalOut, sys.stdout = sys.stdout, self.fakeOut

        self.originalPath = sys.path[:]
        self.originalModules = sys.modules.copy()

        # Get branch root
        here = FilePath(__file__).parent().parent().parent().parent()

        # Find the example script within this branch
        for childName in self.exampleRelativePath.split('/'):
            here = here.child(childName)
            if not here.exists():
                raise SkipTest(
                    "Examples (%s) not found - cannot test" % (here.path,))
        self.examplePath = here

        # Add the example parent folder to the Python path
        sys.path.append(self.examplePath.parent().path)

        # Import the example as a module
        moduleName = self.examplePath.basename().split('.')[0]
        self.example = __import__(moduleName)


    def tearDown(self):
        """
        Remove the example directory from the path and remove all
        modules loaded by the test from sys.modules.
        """
        sys.modules.clear()
        sys.modules.update(self.originalModules)
        sys.path[:] = self.originalPath
        sys.stderr = self.originalErr


    def test_executable(self):
        """
        The example scripts should have an if __name__ ==
        '__main__' so that they do something when called.
        """
        args = [self.examplePath.path, '--help']
        d = utils.getProcessOutput(sys.executable, args, env=os.environ)
        def whenComplete(res):
            self.assertEqual(
                res.splitlines()[0],
                self.example.Options().synopsis)
        d.addCallback(whenComplete)
        return d


    def test_shebang(self):
        """
        The example scripts start with the standard shebang line.
        """
        self.assertEquals(
            self.examplePath.open().readline().rstrip(),
            '#!/usr/bin/env python')


    def test_definedOptions(self):
        """
        Example scripts contain an Options class which is a subclass
        of l{twisted.python.usage.Options]
        """
        self.assertIsInstance(self.example.Options(), usage.Options)


    def test_usageMessageConsistency(self):
        """
        The example script usage message should begin with a "Usage:"
        summary line.
        """
        out = self.example.Options.synopsis
        self.assertTrue(
            out.startswith('Usage:'),
            'Usage message first line should start with "Usage:". '
            'Actual: %r' % (out,))


    def test_usageChecksPositionalArguments(self):
        """
        The example script validates positional arguments
        """
        options = self.example.Options()
        options.parseOptions(
            [str(x) for x in range(self.positionalArgCount)])
        self.assertRaises(
            usage.UsageError,
            options.parseOptions,
            [str(x) for x in range(self.positionalArgCount+1)])


    def test_usageErrorsBeginWithUsage(self):
        """
        The example script prints a full usage message to stderr if it
        is passed incorrect command line arguments
        """
        self.assertRaises(
            SystemExit,
            self.example.main,
            None, '--unexpected_option')
        err = self.fakeErr.getvalue()
        usageMessage = str(self.example.Options())
        self.assertEqual(
            err[:len(usageMessage)],
            usageMessage)


    def test_usageErrorsEndWithError(self):
        """
        The example script prints an "Error:" summary on the last line
        of stderr when incorrect arguments are supplied.
        """
        self.assertRaises(
            SystemExit,
            self.example.main,
            None, '--unexpected_option')
        err = self.fakeErr.getvalue().splitlines()
        self.assertTrue(
            err[-1].startswith('ERROR:'),
            'Usage message last line should start with "ERROR:" '
            'Actual: %r' % (err[-1],))



class TestDnsTests(ExampleTestBase, TestCase):
    """
    Test the testdns.py example script.
    """

    exampleRelativePath = 'doc/names/examples/testdns.py'
    positionalArgCount = 1



class GetHostByNameTests(ExampleTestBase, TestCase):
    """
    Test the gethostbyname.py example script.
    """

    exampleRelativePath = 'doc/names/examples/gethostbyname.py'
    positionalArgCount = 1


    def test_lookupSuccess(self):
        """
        L{gethostbyname.main} uses
        L{twisted.names.client.getHostByName} to resolve a hostname
        asynchronously and returns its deferred result.
        """
        fakeName = 'foo.bar.example.com'
        fakeResult = '192.0.2.1'
        lookedUp = []

        def fakeGetHostByName(host):
            lookedUp.append(host)
            return defer.succeed(fakeResult)
        self.patch(client, 'getHostByName', fakeGetHostByName)

        d = self.example.main(None, fakeName)
        self.assertIsInstance(d, defer.Deferred)

        def whenFinished(res):
            self.assertEqual(lookedUp, [fakeName])
            self.assertEquals(self.fakeOut.getvalue(), fakeResult + '\n')
        d.addBoth(whenFinished)


    def test_printResult(self):
        """
        L{gethostbyname.printResult} accepts an IP address and prints
        it to stdout.
        """
        self.example.printResult('192.0.2.1', 'foo.bar.example.com')
        self.assertEquals(self.fakeOut.getvalue(), '192.0.2.1' + '\n')


    def test_printResultNoResult(self):
        """
        L{gethostbyname.printResult} accepts an error message to
        stderr if it is passed and empty address.
        """
        self.example.printResult('', 'foo.bar.example.com')
        self.assertEquals(
            self.fakeErr.getvalue(),
            "ERROR: No IP adresses found for name 'foo.bar.example.com'\n")


    def test_printErrorExpected(self):
        """
        L{gethostbyname.printError} accepts an L{defer.failure.Failure} and prints
        an error message to stderr if it is an instance of L{error.DNSNameError}.
        """
        self.example.printError(
            defer.failure.Failure(error.DNSNameError()), 'foo.bar.example.com')
        self.assertEquals(
            self.fakeErr.getvalue(),
            "ERROR: hostname not found 'foo.bar.example.com'\n")


    def test_printErrorUnexpected(self):
        """
        L{gethostbyname.printError} accepts an
        L{defer.failure.Failure} and raises the enclosed exception if
        it is not an instance of L{error.DNSNameError}.
        """
        self.assertRaises(
            defer.failure.Failure,
            self.example.printError,
            defer.failure.Failure(NotImplementedError()),
            'foo.bar.example.com')



class DnsServiceTests(ExampleTestBase, TestCase):
    """
    Test the dns-service.py example script.
    """

    exampleRelativePath = 'doc/names/examples/dns-service.py'
    positionalArgCount = 3
