# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.names} example scripts.
"""

from zope.interface.verify import verifyObject, verifyClass

from twisted.internet import defer, interfaces
from twisted.names import client, error
from twisted.test.testutils import StandardExecutableExampleTestBase
from twisted.trial.unittest import TestCase
from twisted.names.test.test_rootresolve import MemoryReactor


class TestDnsTests(StandardExecutableExampleTestBase, TestCase):
    """
    Test the testdns.py example script.
    """

    exampleRelativePath = 'doc/names/examples/testdns.py'
    positionalArgCount = 1


    def test_mainReturnsDeferred(self):
        """
        L{testdns.main} when called with valid arguments, returns a
        deferred which is important for compatibility with
        L{twisted.internet.task.react}.
        """

        # DelayedCall.debug = True
        d = self.example.main(MemoryReactor(), 'foo.bar.example.com')
        self.assertIsInstance(d, defer.Deferred)



class GetHostByNameTests(StandardExecutableExampleTestBase, TestCase):
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

        # XXX: the tentative=True argument can be removed if and when
        # the #6328 branch is merged.
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



class DnsServiceTests(StandardExecutableExampleTestBase, TestCase):
    """
    Test the dns-service.py example script.
    """

    exampleRelativePath = 'doc/names/examples/dns-service.py'
    positionalArgCount = 3
