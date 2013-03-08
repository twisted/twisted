# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Test cases for Twisted.names' root resolver.
"""

from random import randrange

from zope.interface import implementer
from zope.interface.verify import verifyClass

from twisted.python.log import msg
from twisted.trial import util
from twisted.trial.unittest import TestCase
from twisted.internet.defer import Deferred, succeed, gatherResults
from twisted.internet.task import Clock
from twisted.internet.address import IPv4Address
from twisted.internet.interfaces import IReactorUDP, IUDPTransport
from twisted.names.root import Resolver, lookupNameservers, lookupAddress
from twisted.names.root import extractAuthority, discoverAuthority, retry
from twisted.names.dns import (
    IN, HS, A, NS, CNAME, OK, ENAME, Record_CNAME,
    Name, Query, Message, RRHeader, Record_A, Record_NS)
from twisted.names.error import DNSNameError, ResolverError


def getOnePayload(results):
    """
    From the result of a L{Deferred} returned by L{IResolver.lookupAddress},
    return the payload of the first record in the answer section.
    """
    ans, auth, add = results
    return ans[0].payload


def getOneAddress(results):
    """
    From the result of a L{Deferred} returned by L{IResolver.lookupAddress},
    return the first IPv4 address from the answer section.
    """
    return getOnePayload(results).dottedQuad()



@implementer(IUDPTransport)
class MemoryDatagramTransport(object):
    """
    This L{IUDPTransport} implementation enforces the usual connection rules
    and captures sent traffic in a list for later inspection.

    @ivar _host: The host address to which this transport is bound.
    @ivar _protocol: The protocol connected to this transport.
    @ivar _sentPackets: A C{list} of two-tuples of the datagrams passed to
        C{write} and the addresses to which they are destined.

    @ivar _connectedTo: C{None} if this transport is unconnected, otherwise an
        address to which all traffic is supposedly sent.

    @ivar _maxPacketSize: An C{int} giving the maximum length of a datagram
        which will be successfully handled by C{write}.
    """
    def __init__(self, host, protocol, maxPacketSize):
        self._host = host
        self._protocol = protocol
        self._sentPackets = []
        self._connectedTo = None
        self._maxPacketSize = maxPacketSize


    def getHost(self):
        """
        Return the address which this transport is pretending to be bound
        to.
        """
        return IPv4Address('UDP', *self._host)


    def connect(self, host, port):
        """
        Connect this transport to the given address.
        """
        if self._connectedTo is not None:
            raise ValueError("Already connected")
        self._connectedTo = (host, port)


    def write(self, datagram, addr=None):
        """
        Send the given datagram.
        """
        if addr is None:
            addr = self._connectedTo
        if addr is None:
            raise ValueError("Need an address")
        if len(datagram) > self._maxPacketSize:
            raise ValueError("Packet too big")
        self._sentPackets.append((datagram, addr))


    def stopListening(self):
        """
        Shut down this transport.
        """
        self._protocol.stopProtocol()
        return succeed(None)

verifyClass(IUDPTransport, MemoryDatagramTransport)



@implementer(IReactorUDP)
class MemoryReactor(Clock):
    """
    An L{IReactorTime} and L{IReactorUDP} provider.

    Time is controlled deterministically via the base class, L{Clock}.  UDP is
    handled in-memory by connecting protocols to instances of
    L{MemoryDatagramTransport}.

    @ivar udpPorts: A C{dict} mapping port numbers to instances of
        L{MemoryDatagramTransport}.
    """
    def __init__(self):
        Clock.__init__(self)
        self.udpPorts = {}


    def listenUDP(self, port, protocol, interface='', maxPacketSize=8192):
        """
        Pretend to bind a UDP port and connect the given protocol to it.
        """
        if port == 0:
            while True:
                port = randrange(1, 2 ** 16)
                if port not in self.udpPorts:
                    break
        if port in self.udpPorts:
            raise ValueError("Address in use")
        transport = MemoryDatagramTransport(
            (interface, port), protocol, maxPacketSize)
        self.udpPorts[port] = transport
        protocol.makeConnection(transport)
        return transport

verifyClass(IReactorUDP, MemoryReactor)



class RootResolverTests(TestCase):
    """
    Tests for L{twisted.names.root.Resolver}.
    """
    def _queryTest(self, filter):
        """
        Invoke L{Resolver._query} and verify that it sends the correct DNS
        query.  Deliver a canned response to the query and return whatever the
        L{Deferred} returned by L{Resolver._query} fires with.

        @param filter: The value to pass for the C{filter} parameter to
            L{Resolver._query}.
        """
        reactor = MemoryReactor()
        resolver = Resolver([], reactor=reactor)
        d = resolver._query(
            Query(b'foo.example.com', A, IN), [('1.1.2.3', 1053)], (30,),
            filter)

        # A UDP port should have been started.
        portNumber, transport = reactor.udpPorts.popitem()

        # And a DNS packet sent.
        [(packet, address)] = transport._sentPackets

        msg = Message()
        msg.fromStr(packet)

        # It should be a query with the parameters used above.
        self.assertEqual(msg.queries, [Query(b'foo.example.com', A, IN)])
        self.assertEqual(msg.answers, [])
        self.assertEqual(msg.authority, [])
        self.assertEqual(msg.additional, [])

        response = []
        d.addCallback(response.append)
        self.assertEqual(response, [])

        # Once a reply is received, the Deferred should fire.
        del msg.queries[:]
        msg.answer = 1
        msg.answers.append(RRHeader(b'foo.example.com', payload=Record_A('5.8.13.21')))
        transport._protocol.datagramReceived(msg.toStr(), ('1.1.2.3', 1053))
        return response[0]


    def test_filteredQuery(self):
        """
        L{Resolver._query} accepts a L{Query} instance and an address, issues
        the query, and returns a L{Deferred} which fires with the response to
        the query.  If a true value is passed for the C{filter} parameter, the
        result is a three-tuple of lists of records.
        """
        answer, authority, additional = self._queryTest(True)
        self.assertEqual(
            answer,
            [RRHeader(b'foo.example.com', payload=Record_A('5.8.13.21', ttl=0))])
        self.assertEqual(authority, [])
        self.assertEqual(additional, [])


    def test_unfilteredQuery(self):
        """
        Similar to L{test_filteredQuery}, but for the case where a false value
        is passed for the C{filter} parameter.  In this case, the result is a
        L{Message} instance.
        """
        message = self._queryTest(False)
        self.assertIsInstance(message, Message)
        self.assertEqual(message.queries, [])
        self.assertEqual(
            message.answers,
            [RRHeader(b'foo.example.com', payload=Record_A('5.8.13.21', ttl=0))])
        self.assertEqual(message.authority, [])
        self.assertEqual(message.additional, [])


    def _respond(self, answers=[], authority=[], additional=[], rCode=OK):
        """
        Create a L{Message} suitable for use as a response to a query.

        @param answers: A C{list} of two-tuples giving data for the answers
            section of the message.  The first element of each tuple is a name
            for the L{RRHeader}.  The second element is the payload.
        @param authority: A C{list} like C{answers}, but for the authority
            section of the response.
        @param additional: A C{list} like C{answers}, but for the
            additional section of the response.
        @param rCode: The response code the message will be created with.

        @return: A new L{Message} initialized with the given values.
        """
        response = Message(rCode=rCode)
        for (section, data) in [(response.answers, answers),
                                (response.authority, authority),
                                (response.additional, additional)]:
            section.extend([
                    RRHeader(name, record.TYPE, getattr(record, 'CLASS', IN),
                             payload=record)
                    for (name, record) in data])
        return response


    def _getResolver(self, serverResponses, maximumQueries=10):
        """
        Create and return a new L{root.Resolver} modified to resolve queries
        against the record data represented by C{servers}.

        @param serverResponses: A mapping from dns server addresses to
            mappings.  The inner mappings are from query two-tuples (name,
            type) to dictionaries suitable for use as **arguments to
            L{_respond}.  See that method for details.
        """
        roots = ['1.1.2.3']
        resolver = Resolver(roots, maximumQueries)

        def query(query, serverAddresses, timeout, filter):
            msg("Query for QNAME %s at %r" % (query.name, serverAddresses))
            for addr in serverAddresses:
                try:
                    server = serverResponses[addr]
                except KeyError:
                    continue
                records = server[query.name.name, query.type]
                return succeed(self._respond(**records))
        resolver._query = query
        return resolver


    def test_lookupAddress(self):
        """
        L{root.Resolver.lookupAddress} looks up the I{A} records for the
        specified hostname by first querying one of the root servers the
        resolver was created with and then following the authority delegations
        until a result is received.
        """
        servers = {
            ('1.1.2.3', 53): {
                (b'foo.example.com', A): {
                    'authority': [(b'foo.example.com', Record_NS(b'ns1.example.com'))],
                    'additional': [(b'ns1.example.com', Record_A('34.55.89.144'))],
                    },
                },
            ('34.55.89.144', 53): {
                (b'foo.example.com', A): {
                    'answers': [(b'foo.example.com', Record_A('10.0.0.1'))],
                    }
                },
            }
        resolver = self._getResolver(servers)
        d = resolver.lookupAddress(b'foo.example.com')
        d.addCallback(getOneAddress)
        d.addCallback(self.assertEqual, '10.0.0.1')
        return d


    def test_lookupChecksClass(self):
        """
        If a response includes a record with a class different from the one
        in the query, it is ignored and lookup continues until a record with
        the right class is found.
        """
        badClass = Record_A('10.0.0.1')
        badClass.CLASS = HS
        servers = {
            ('1.1.2.3', 53): {
                ('foo.example.com', A): {
                    'answers': [('foo.example.com', badClass)],
                    'authority': [('foo.example.com', Record_NS('ns1.example.com'))],
                    'additional': [('ns1.example.com', Record_A('10.0.0.2'))],
                },
            },
            ('10.0.0.2', 53): {
                ('foo.example.com', A): {
                    'answers': [('foo.example.com', Record_A('10.0.0.3'))],
                },
            },
        }
        resolver = self._getResolver(servers)
        d = resolver.lookupAddress('foo.example.com')
        d.addCallback(getOnePayload)
        d.addCallback(self.assertEqual, Record_A('10.0.0.3'))
        return d


    def test_missingGlue(self):
        """
        If an intermediate response includes no glue records for the
        authorities, separate queries are made to find those addresses.
        """
        servers = {
            ('1.1.2.3', 53): {
                (b'foo.example.com', A): {
                    'authority': [(b'foo.example.com', Record_NS(b'ns1.example.org'))],
                    # Conspicuous lack of an additional section naming ns1.example.com
                    },
                (b'ns1.example.org', A): {
                    'answers': [(b'ns1.example.org', Record_A('10.0.0.1'))],
                    },
                },
            ('10.0.0.1', 53): {
                (b'foo.example.com', A): {
                    'answers': [(b'foo.example.com', Record_A('10.0.0.2'))],
                    },
                },
            }
        resolver = self._getResolver(servers)
        d = resolver.lookupAddress(b'foo.example.com')
        d.addCallback(getOneAddress)
        d.addCallback(self.assertEqual, '10.0.0.2')
        return d


    def test_missingName(self):
        """
        If a name is missing, L{Resolver.lookupAddress} returns a L{Deferred}
        which fails with L{DNSNameError}.
        """
        servers = {
            ('1.1.2.3', 53): {
                (b'foo.example.com', A): {
                    'rCode': ENAME,
                    },
                },
            }
        resolver = self._getResolver(servers)
        d = resolver.lookupAddress(b'foo.example.com')
        return self.assertFailure(d, DNSNameError)


    def test_answerless(self):
        """
        If a query is responded to with no answers or nameserver records, the
        L{Deferred} returned by L{Resolver.lookupAddress} fires with
        L{ResolverError}.
        """
        servers = {
            ('1.1.2.3', 53): {
                ('example.com', A): {
                    },
                },
            }
        resolver = self._getResolver(servers)
        d = resolver.lookupAddress('example.com')
        return self.assertFailure(d, ResolverError)


    def test_delegationLookupError(self):
        """
        If there is an error resolving the nameserver in a delegation response,
        the L{Deferred} returned by L{Resolver.lookupAddress} fires with that
        error.
        """
        servers = {
            ('1.1.2.3', 53): {
                ('example.com', A): {
                    'authority': [('example.com', Record_NS('ns1.example.com'))],
                    },
                ('ns1.example.com', A): {
                    'rCode': ENAME,
                    },
                },
            }
        resolver = self._getResolver(servers)
        d = resolver.lookupAddress('example.com')
        return self.assertFailure(d, DNSNameError)


    def test_delegationLookupEmpty(self):
        """
        If there are no records in the response to a lookup of a delegation
        nameserver, the L{Deferred} returned by L{Resolver.lookupAddress} fires
        with L{ResolverError}.
        """
        servers = {
            ('1.1.2.3', 53): {
                ('example.com', A): {
                    'authority': [('example.com', Record_NS('ns1.example.com'))],
                    },
                ('ns1.example.com', A): {
                    },
                },
            }
        resolver = self._getResolver(servers)
        d = resolver.lookupAddress('example.com')
        return self.assertFailure(d, ResolverError)


    def test_lookupNameservers(self):
        """
        L{Resolver.lookupNameservers} is like L{Resolver.lookupAddress}, except
        it queries for I{NS} records instead of I{A} records.
        """
        servers = {
            ('1.1.2.3', 53): {
                (b'example.com', A): {
                    'rCode': ENAME,
                    },
                (b'example.com', NS): {
                    'answers': [(b'example.com', Record_NS(b'ns1.example.com'))],
                    },
                },
            }
        resolver = self._getResolver(servers)
        d = resolver.lookupNameservers(b'example.com')
        def getOneName(results):
            ans, auth, add = results
            return ans[0].payload.name
        d.addCallback(getOneName)
        d.addCallback(self.assertEqual, Name(b'ns1.example.com'))
        return d


    def test_returnCanonicalName(self):
        """
        If a I{CNAME} record is encountered as the answer to a query for
        another record type, that record is returned as the answer.
        """
        servers = {
            ('1.1.2.3', 53): {
                (b'example.com', A): {
                    'answers': [(b'example.com', Record_CNAME(b'example.net')),
                                (b'example.net', Record_A('10.0.0.7'))],
                    },
                },
            }
        resolver = self._getResolver(servers)
        d = resolver.lookupAddress(b'example.com')
        d.addCallback(lambda results: results[0]) # Get the answer section
        d.addCallback(
            self.assertEqual,
            [RRHeader(b'example.com', CNAME, payload=Record_CNAME(b'example.net')),
             RRHeader(b'example.net', A, payload=Record_A('10.0.0.7'))])
        return d


    def test_followCanonicalName(self):
        """
        If no record of the requested type is included in a response, but a
        I{CNAME} record for the query name is included, queries are made to
        resolve the value of the I{CNAME}.
        """
        servers = {
            ('1.1.2.3', 53): {
                ('example.com', A): {
                    'answers': [('example.com', Record_CNAME('example.net'))],
                },
                ('example.net', A): {
                    'answers': [('example.net', Record_A('10.0.0.5'))],
                },
            },
        }
        resolver = self._getResolver(servers)
        d = resolver.lookupAddress('example.com')
        d.addCallback(lambda results: results[0]) # Get the answer section
        d.addCallback(
            self.assertEqual,
            [RRHeader('example.com', CNAME, payload=Record_CNAME('example.net')),
             RRHeader('example.net', A, payload=Record_A('10.0.0.5'))])
        return d


    def test_detectCanonicalNameLoop(self):
        """
        If there is a cycle between I{CNAME} records in a response, this is
        detected and the L{Deferred} returned by the lookup method fails
        with L{ResolverError}.
        """
        servers = {
            ('1.1.2.3', 53): {
                ('example.com', A): {
                    'answers': [('example.com', Record_CNAME('example.net')),
                                ('example.net', Record_CNAME('example.com'))],
                },
            },
        }
        resolver = self._getResolver(servers)
        d = resolver.lookupAddress('example.com')
        return self.assertFailure(d, ResolverError)


    def test_boundedQueries(self):
        """
        L{Resolver.lookupAddress} won't issue more queries following
        delegations than the limit passed to its initializer.
        """
        servers = {
            ('1.1.2.3', 53): {
                # First query - force it to start over with a name lookup of
                # ns1.example.com
                ('example.com', A): {
                    'authority': [('example.com', Record_NS('ns1.example.com'))],
                },
                # Second query - let it resume the original lookup with the
                # address of the nameserver handling the delegation.
                ('ns1.example.com', A): {
                    'answers': [('ns1.example.com', Record_A('10.0.0.2'))],
                },
            },
            ('10.0.0.2', 53): {
                # Third query - let it jump straight to asking the
                # delegation server by including its address here (different
                # case from the first query).
                ('example.com', A): {
                    'authority': [('example.com', Record_NS('ns2.example.com'))],
                    'additional': [('ns2.example.com', Record_A('10.0.0.3'))],
                },
            },
            ('10.0.0.3', 53): {
                # Fourth query - give it the answer, we're done.
                ('example.com', A): {
                    'answers': [('example.com', Record_A('10.0.0.4'))],
                },
            },
        }

        # Make two resolvers.  One which is allowed to make 3 queries
        # maximum, and so will fail, and on which may make 4, and so should
        # succeed.
        failer = self._getResolver(servers, 3)
        failD = self.assertFailure(
            failer.lookupAddress('example.com'), ResolverError)

        succeeder = self._getResolver(servers, 4)
        succeedD = succeeder.lookupAddress('example.com')
        succeedD.addCallback(getOnePayload)
        succeedD.addCallback(self.assertEqual, Record_A('10.0.0.4'))

        return gatherResults([failD, succeedD])


    def test_discoveredAuthorityDeprecated(self):
        """
        Calling L{Resolver.discoveredAuthority} produces a deprecation warning.
        """
        resolver = Resolver([])
        d = resolver.discoveredAuthority('127.0.0.1', 'example.com', IN, A, (0,))

        warnings = self.flushWarnings([
                self.test_discoveredAuthorityDeprecated])
        self.assertEqual(warnings[0]['category'], DeprecationWarning)
        self.assertEqual(
            warnings[0]['message'],
            'twisted.names.root.Resolver.discoveredAuthority is deprecated since '
            'Twisted 10.0.  Use twisted.names.client.Resolver directly, instead.')
        self.assertEqual(len(warnings), 1)

        # This will time out quickly, but we need to wait for it because there
        # are resources associated with.
        d.addErrback(lambda ignored: None)
        return d



class StubDNSDatagramProtocol:
    """
    A do-nothing stand-in for L{DNSDatagramProtocol} which can be used to avoid
    network traffic in tests where that kind of thing doesn't matter.
    """
    def query(self, *a, **kw):
        return Deferred()



_retrySuppression = util.suppress(
    category=DeprecationWarning,
    message=(
        'twisted.names.root.retry is deprecated since Twisted 10.0.  Use a '
        'Resolver object for retry logic.'))


class DiscoveryToolsTests(TestCase):
    """
    Tests for the free functions in L{twisted.names.root} which help out with
    authority discovery.  Since these are mostly deprecated, these are mostly
    deprecation tests.
    """
    def test_lookupNameserversDeprecated(self):
        """
        Calling L{root.lookupNameservers} produces a deprecation warning.
        """
        # Don't care about the return value, since it will never have a result,
        # since StubDNSDatagramProtocol doesn't actually work.
        lookupNameservers('example.com', '127.0.0.1', StubDNSDatagramProtocol())

        warnings = self.flushWarnings([
                self.test_lookupNameserversDeprecated])
        self.assertEqual(warnings[0]['category'], DeprecationWarning)
        self.assertEqual(
            warnings[0]['message'],
            'twisted.names.root.lookupNameservers is deprecated since Twisted '
            '10.0.  Use twisted.names.root.Resolver.lookupNameservers '
            'instead.')
        self.assertEqual(len(warnings), 1)
    test_lookupNameserversDeprecated.suppress = [_retrySuppression]


    def test_lookupAddressDeprecated(self):
        """
        Calling L{root.lookupAddress} produces a deprecation warning.
        """
        # Don't care about the return value, since it will never have a result,
        # since StubDNSDatagramProtocol doesn't actually work.
        lookupAddress('example.com', '127.0.0.1', StubDNSDatagramProtocol())

        warnings = self.flushWarnings([
                self.test_lookupAddressDeprecated])
        self.assertEqual(warnings[0]['category'], DeprecationWarning)
        self.assertEqual(
            warnings[0]['message'],
            'twisted.names.root.lookupAddress is deprecated since Twisted '
            '10.0.  Use twisted.names.root.Resolver.lookupAddress '
            'instead.')
        self.assertEqual(len(warnings), 1)
    test_lookupAddressDeprecated.suppress = [_retrySuppression]


    def test_extractAuthorityDeprecated(self):
        """
        Calling L{root.extractAuthority} produces a deprecation warning.
        """
        extractAuthority(Message(), {})

        warnings = self.flushWarnings([
                self.test_extractAuthorityDeprecated])
        self.assertEqual(warnings[0]['category'], DeprecationWarning)
        self.assertEqual(
            warnings[0]['message'],
            'twisted.names.root.extractAuthority is deprecated since Twisted '
            '10.0.  Please inspect the Message object directly.')
        self.assertEqual(len(warnings), 1)


    def test_discoverAuthorityDeprecated(self):
        """
        Calling L{root.discoverAuthority} produces a deprecation warning.
        """
        discoverAuthority(
            'example.com', ['10.0.0.1'], p=StubDNSDatagramProtocol())

        warnings = self.flushWarnings([
                self.test_discoverAuthorityDeprecated])
        self.assertEqual(warnings[0]['category'], DeprecationWarning)
        self.assertEqual(
            warnings[0]['message'],
            'twisted.names.root.discoverAuthority is deprecated since Twisted '
            '10.0.  Use twisted.names.root.Resolver.lookupNameservers '
            'instead.')
        self.assertEqual(len(warnings), 1)

    # discoverAuthority is implemented in terms of deprecated functions,
    # too.  Ignore those.
    test_discoverAuthorityDeprecated.suppress = [
        util.suppress(
            category=DeprecationWarning,
            message=(
                'twisted.names.root.lookupNameservers is deprecated since '
                'Twisted 10.0.  Use '
                'twisted.names.root.Resolver.lookupNameservers instead.')),
        _retrySuppression]


    def test_retryDeprecated(self):
        """
        Calling L{root.retry} produces a deprecation warning.
        """
        retry([0], StubDNSDatagramProtocol())

        warnings = self.flushWarnings([
                self.test_retryDeprecated])
        self.assertEqual(warnings[0]['category'], DeprecationWarning)
        self.assertEqual(
            warnings[0]['message'],
            'twisted.names.root.retry is deprecated since Twisted '
            '10.0.  Use a Resolver object for retry logic.')
        self.assertEqual(len(warnings), 1)
