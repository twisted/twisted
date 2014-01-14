# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for docs/names/howto/listings/auth_override.py
"""

from override_server import DynamicResolver

from twisted.internet import defer, reactor
from twisted.names import dns, error, server, client
from twisted.trial.unittest import SynchronousTestCase, TestCase, FailTest



class RaisedArguments(Exception):
    """
    An exception for recording raised arguments.
    """
    def __init__(self, args, kwargs):
        self.args = args
        self.kwargs = kwargs



class DNSAssertionsMixin(object):
    """
    A custom assertion and helpers for comparing the results of IResolver.lookup
    methods.

    Compares the RRHeaders and Record payloads separately.
    """
    def _justPayloads(self, headers):
        """
        Return only the payloads from a list of headers.
        """
        return [h.payload for h in headers]


    def _allPayloads(self, sections):
        """
        Return all the payloads from the three section lists typically returned from
        IResolver.lookup methods.
        """
        payloads = []
        for section in sections:
            payloads.append(self._justPayloads(section))
        return payloads


    def assertEqualResolverResponse(self, expected, actual):
        """
        Compare the headers and payloads from the section lists returned by
        IResolver.lookup methods.

        Failures are accompaned by a print out of the headers and payloads.
        """
        try:
            self.assertEqual(expected, actual)
        except FailTest:
            self.fail(
                'Header / Payload mismatch:\n\n'
                'Headers: \n%r\n%r\n'
                'Payloads: \n%r\n%r\n' % (expected,
                                          actual,
                                          self._allPayloads(expected),
                                          self._allPayloads(actual))
            )



class Raiser(object):
    """
    A fake which can be patched on top of a method under test to verify its call
    signature.
    """
    def __init__(self, exception):
        self._exception = exception


    def call(self, *args, **kwargs):
        raise self._exception(args, kwargs)



class DynamicResolverTests(SynchronousTestCase, DNSAssertionsMixin):
    def test_queryCallsDynamicResponseRequired(self):
        """
        query calls _dynamicResponseRequired with the supplied query to determine
        whether the answer should be calculated dynamically.
        """
        r = DynamicResolver()

        class ExpectedException(RaisedArguments):
            pass

        r._dynamicResponseRequired = Raiser(ExpectedException).call

        dummyQuery = object()

        e = self.assertRaises(ExpectedException, r.query, dummyQuery)
        self.assertEqual(
            ((dummyQuery,), {}),
            (e.args, e.kwargs)
        )


    def test_dynamicResponseRequiredType(self):
        """
        DynamicResolver._dynamicResponseRequired returns True if query.type == A
        else False.
        """
        r = DynamicResolver()
        self.assertEqual(
            (True, False),
            (r._dynamicResponseRequired(dns.Query(name=b'workstation1.example.com', type=dns.A)),
             r._dynamicResponseRequired(dns.Query(name=b'workstation1.example.com', type=dns.SOA)))
        )


    def test_dynamicResponseRequiredName(self):
        """
        DynamicResolver._dynamicResponseRequired returns True if query.name
        begins with the word host, else False.
        """
        r = DynamicResolver()
        self.assertEqual(
            (True, False),
            (r._dynamicResponseRequired(dns.Query(name=b'workstation1.example.com', type=dns.A)),
             r._dynamicResponseRequired(dns.Query(name=b'foo1.example.com', type=dns.A)),)
        )


    def test_queryCallsDoDynamicResponse(self):
        """
        DynamicResolver.query will call _doDynamicResponse to calculate the response
        to a dynamic query.
        """
        r = DynamicResolver()

        r._dynamicResponseRequired = lambda query: True

        class ExpectedException(RaisedArguments):
            pass

        r._doDynamicResponse = Raiser(ExpectedException).call

        dummyQuery = object()
        e = self.assertRaises(
            ExpectedException,
            r.query, dummyQuery
        )
        self.assertEqual(
            ((dummyQuery,), {}),
            (e.args, e.kwargs)
        )


    def test_doDynamicResponseWorkstation1(self):
        """
        _doDynamicResponse takes the trailing integer in the first label of the
        query name and uses it as the last octet of the rerurned IP address.
        """
        r = DynamicResolver()
        self.assertEqualResolverResponse(
            ([dns.RRHeader(name='workstation1.example.com', payload=dns.Record_A(address='172.0.2.1', ttl=0))], [], []),
            r._doDynamicResponse(dns.Query('workstation1.example.com'))
        )


    def test_doDynamicResponseWorkstation2(self):
        """
        """
        r = DynamicResolver()
        self.assertEqualResolverResponse(
            ([dns.RRHeader(name='workstation2.example.com', payload=dns.Record_A(address='172.0.2.2', ttl=0))], [], []),
            r._doDynamicResponse(dns.Query('workstation2.example.com'))
        )


    def test_querySuccess(self):
        """
        query returns a deferred success wrapping the results lists from
        _doDynamicResponse.
        """
        r = DynamicResolver()
        r._dynamicResponseRequired = lambda query: True
        dummyResponse = object()
        r._doDynamicResponse = lambda query: dummyResponse
        res = self.successResultOf(r.query(dns.Query()))
        self.assertIs(dummyResponse, res)


    def test_queryDomainError(self):
        """
        query returns a deferred failure wrapping DomainError if the query is not to
        be handled dynamically.
        """
        r = DynamicResolver()
        r._dynamicResponseRequired = lambda query: False
        d = r.query(dns.Query(b'foo.example.com'))
        self.failureResultOf(d, error.DomainError)



class RoundTripTests(TestCase, DNSAssertionsMixin):
    """
    Functional tests which setup a listening server and send it requests using a
    network client.
    """
    def buildClientServer(self, fallbackResolver=None):
        resolvers = [DynamicResolver()]
        if fallbackResolver is not None:
            resolvers.append(fallbackResolver)
        s = server.DNSServerFactory(
            authorities=resolvers,
        )

        listeningPort = reactor.listenUDP(0, dns.DNSDatagramProtocol(controller=s))
        self.addCleanup(listeningPort.stopListening)
        return client.Resolver(servers=[('127.0.0.1', listeningPort.getHost().port)])


    def test_query(self):
        """
        """
        hostname = b'workstation1.example.com'

        expected = (
            [dns.RRHeader(name=hostname, payload=dns.Record_A('172.0.2.1', ttl=0))],
            [],
            []
        )

        r = self.buildClientServer()

        return r.lookupAddress(hostname).addCallback(
            self.assertEqualResolverResponse,
            expected
        )


    def test_queryFallback(self):
        """
        """
        hostname = b'workstation1.example.com'

        expectedAnswer = dns.RRHeader(name=hostname, type=dns.TXT, payload=dns.Record_TXT('Foo', ttl=0))

        class FakeFallbackResolver(object):
            def query(self, query, timeout):
                return defer.succeed(([expectedAnswer], [], []))
        fbr = FakeFallbackResolver()
        r = self.buildClientServer(fallbackResolver=fbr)

        expected = (
            [expectedAnswer],
            [],
            []
        )

        return r.lookupText(hostname).addCallback(
            self.assertEqualResolverResponse,
            expected
        )
