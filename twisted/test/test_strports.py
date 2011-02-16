# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.application.strports}.
"""

from twisted.trial.unittest import TestCase
from twisted.application import strports
from twisted.application import internet
from twisted.internet.test.test_endpoints import ParserTestCase
from twisted.internet.protocol import Factory
from twisted.internet.endpoints import TCP4ServerEndpoint, UNIXServerEndpoint



class DeprecatedParseTestCase(ParserTestCase):
    """
    L{strports.parse} is deprecated.  It's an alias for a method that is now
    private in L{twisted.internet.endpoints}.
    """

    def parse(self, *a, **kw):
        result = strports.parse(*a, **kw)
        warnings = self.flushWarnings([self.parse])
        self.assertEquals(len(warnings), 1)
        self.assertEquals(
            warnings[0]['message'],
            "twisted.application.strports.parse was deprecated "
            "in Twisted 10.2.0: in favor of twisted.internet.endpoints.serverFromString")
        return result


    def test_simpleNumeric(self):
        """
        Base numeric ports should be parsed as TCP.
        """
        self.assertEquals(self.parse('80', self.f),
                         ('TCP', (80, self.f), {'interface':'', 'backlog':50}))


    def test_allKeywords(self):
        """
        A collection of keyword arguments with no prefixed type, like 'port=80',
        will be parsed as keyword arguments to 'tcp'.
        """
        self.assertEquals(self.parse('port=80', self.f),
                         ('TCP', (80, self.f), {'interface':'', 'backlog':50}))



class ServiceTestCase(TestCase):
    """
    Tests for L{strports.service}.
    """

    def test_service(self):
        """
        L{strports.service} returns a L{StreamServerEndpointService}
        constructed with an endpoint produced from
        L{endpoint.serverFromString}, using the same syntax.
        """
        reactor = object() # the cake is a lie
        aFactory = Factory()
        aGoodPort = 1337
        svc = strports.service(
            'tcp:'+str(aGoodPort), aFactory, reactor=reactor)
        self.assertIsInstance(svc, internet.StreamServerEndpointService)

        # See twisted.application.test.test_internet.TestEndpointService.
        # test_synchronousRaiseRaisesSynchronously
        self.assertEquals(svc._raiseSynchronously, True)
        self.assertIsInstance(svc.endpoint, TCP4ServerEndpoint)
        # Maybe we should implement equality for endpoints.
        self.assertEquals(svc.endpoint._port, aGoodPort)
        self.assertIdentical(svc.factory, aFactory)
        self.assertIdentical(svc.endpoint._reactor, reactor)


    def test_serviceDefaultReactor(self):
        """
        L{strports.service} will use the default reactor when none is provided
        as an argument.
        """
        from twisted.internet import reactor as globalReactor
        aService = strports.service("tcp:80", None)
        self.assertIdentical(aService.endpoint._reactor, globalReactor)


    def test_serviceDeprecatedDefault(self):
        """
        L{strports.service} still accepts a 'default' argument, which will
        affect the parsing of 'default' (i.e. 'not containing a colon')
        endpoint descriptions, but this behavior is deprecated.
        """
        svc = strports.service("8080", None, "unix")
        self.assertIsInstance(svc.endpoint, UNIXServerEndpoint)
        warnings = self.flushWarnings([self.test_serviceDeprecatedDefault])
        self.assertEquals(warnings[0]['category'], DeprecationWarning)
        self.assertEquals(
            warnings[0]['message'],
            "The 'default' parameter was deprecated in Twisted 10.2.0.  "
            "Use qualified endpoint descriptions; for example, 'tcp:8080'.")
        self.assertEquals(len(warnings), 1)

        # Almost the same case, but slightly tricky - explicitly passing the old
        # default value, None, also must trigger a deprecation warning.
        svc = strports.service("tcp:8080", None, None)
        self.assertIsInstance(svc.endpoint, TCP4ServerEndpoint)
        warnings = self.flushWarnings([self.test_serviceDeprecatedDefault])
        self.assertEquals(warnings[0]['category'], DeprecationWarning)
        self.assertEquals(
            warnings[0]['message'],
            "The 'default' parameter was deprecated in Twisted 10.2.0.")
        self.assertEquals(len(warnings), 1)


    def test_serviceDeprecatedUnqualified(self):
        """
        Unqualified strport descriptions, i.e. "8080", are deprecated.
        """
        svc = strports.service("8080", None)
        self.assertIsInstance(svc.endpoint, TCP4ServerEndpoint)
        warnings = self.flushWarnings(
            [self.test_serviceDeprecatedUnqualified])
        self.assertEquals(warnings[0]['category'], DeprecationWarning)
        self.assertEquals(
            warnings[0]['message'],
            "Unqualified strport description passed to 'service'."
            "Use qualified endpoint descriptions; for example, 'tcp:8080'.")
        self.assertEquals(len(warnings), 1)


