# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.names} example scripts.
"""

import os
import sys

from zope.interface.verify import verifyObject

from twisted.internet import defer, interfaces, utils
from twisted.names import client, error
from twisted.python import usage
from twisted.test.testutils import ExampleTestBase
from twisted.trial.unittest import TestCase



class NamesExampleTestBase(ExampleTestBase):
    """
    A base class for all the L{twisted.names} examples.

    @ivar positionalArgCount: The maximum number of positional
        arguments expected by the example script under test.
    """

    positionalArgCount = 0


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
            [str(x) for x in range(self.positionalArgCount + 1)])


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



class TestDnsTests(NamesExampleTestBase, TestCase):
    """
    Test the testdns.py example script.
    """

    exampleRelativePath = 'doc/names/examples/testdns.py'
    positionalArgCount = 1



class GetHostByNameTests(NamesExampleTestBase, TestCase):
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

        def fakeGetHostByName(host, timeout=None):
            lookedUp.append(host)
            return defer.succeed(fakeResult)
        self.patch(client, 'getHostByName', fakeGetHostByName)

        verifyObject(interfaces.IResolverSimple, client, tentative=True)

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



class DnsServiceTests(NamesExampleTestBase, TestCase):
    """
    Test the dns-service.py example script.
    """

    exampleRelativePath = 'doc/names/examples/dns-service.py'
    positionalArgCount = 3
