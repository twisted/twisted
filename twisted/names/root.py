# -*- test-case-name: twisted.names.test.test_rootresolve -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Resolver implementation for querying successive authoritative servers to
lookup a record, starting from the root nameservers.

@author: Jp Calderone

todo::
    robustify it
    documentation
"""

import warnings

from twisted.python.failure import Failure
from twisted.internet import defer
from twisted.names import dns, common, error


def retry(t, p, *args):
    """
    Issue a query one or more times.

    This function is deprecated.  Use one of the resolver classes for retry
    logic, or implement it yourself.
    """
    warnings.warn(
        "twisted.names.root.retry is deprecated since Twisted 10.0.  Use a "
        "Resolver object for retry logic.", category=DeprecationWarning,
        stacklevel=2)

    assert t, "Timeout is required"
    t = list(t)
    def errback(failure):
        failure.trap(defer.TimeoutError)
        if not t:
            return failure
        return p.query(timeout=t.pop(0), *args
            ).addErrback(errback
            )
    return p.query(timeout=t.pop(0), *args
        ).addErrback(errback
        )



class _DummyController:
    """
    A do-nothing DNS controller.  This is useful when all messages received
    will be responses to previously issued queries.  Anything else received
    will be ignored.
    """
    def messageReceived(self, *args):
        pass



class Resolver(common.ResolverBase):
    """
    L{Resolver} implements recursive lookup starting from a specified list of
    root servers.

    @ivar hints: A C{list} of C{str} giving the dotted quad representation
        of IP addresses of root servers at which to begin resolving names.

    @ivar _maximumQueries: A C{int} giving the maximum number of queries
        which will be attempted to resolve a single name.

    @ivar _reactor: A L{IReactorTime} and L{IReactorUDP} provider to use to
        bind UDP ports and manage timeouts.
    """
    def __init__(self, hints, maximumQueries=10, reactor=None):
        common.ResolverBase.__init__(self)
        self.hints = hints
        self._maximumQueries = maximumQueries
        self._reactor = reactor


    def _roots(self):
        """
        Return a list of two-tuples representing the addresses of the root
        servers, as defined by C{self.hints}.
        """
        return [(ip, dns.PORT) for ip in self.hints]


    def _query(self, query, servers, timeout, filter):
        """
        Issue one query and return a L{Deferred} which fires with its response.

        @param query: The query to issue.
        @type query: L{dns.Query}

        @param servers: The servers which might have an answer for this
            query.
        @type servers: L{list} of L{tuple} of L{str} and L{int}

        @param timeout: A timeout on how long to wait for the response.
        @type timeout: L{tuple} of L{int}

        @param filter: A flag indicating whether to filter the results.  If
            C{True}, the returned L{Deferred} will fire with a three-tuple of
            lists of L{RRHeaders} (like the return value of the I{lookup*}
            methods of L{IResolver}.  IF C{False}, the result will be a
            L{Message} instance.
        @type filter: L{bool}

        @return: A L{Deferred} which fires with the response or a timeout
            error.
        @rtype: L{Deferred}
        """
        from twisted.names import client
        r = client.Resolver(servers=servers, reactor=self._reactor)
        d = r.queryUDP([query], timeout)
        if filter:
            d.addCallback(r.filterAnswers)
        return d


    def _lookup(self, name, cls, type, timeout):
        """
        Implement name lookup by recursively discovering the authoritative
        server for the name and then asking it, starting at one of the servers
        in C{self.hints}.
        """
        if timeout is None:
            # A series of timeouts for semi-exponential backoff, summing to an
            # arbitrary total of 60 seconds.
            timeout = (1, 3, 11, 45)
        return self._discoverAuthority(
            dns.Query(name, type, cls), self._roots(), timeout,
            self._maximumQueries)


    def _discoverAuthority(self, query, servers, timeout, queriesLeft):
        """
        Issue a query to a server and follow a delegation if necessary.

        @param query: The query to issue.
        @type query: L{dns.Query}

        @param servers: The servers which might have an answer for this
            query.
        @type servers: L{list} of L{tuple} of L{str} and L{int}

        @param timeout: A C{tuple} of C{int} giving the timeout to use for this
            query.

        @param queriesLeft: A C{int} giving the number of queries which may
            yet be attempted to answer this query before the attempt will be
            abandoned.

        @return: A L{Deferred} which fires with a three-tuple of lists of
            L{RRHeaders} giving the response, or with a L{Failure} if there is
            a timeout or response error.
        """
        # Stop now if we've hit the query limit.
        if queriesLeft <= 0:
            return Failure(
                error.ResolverError("Query limit reached without result"))

        d = self._query(query, servers, timeout, False)
        d.addCallback(
            self._discoveredAuthority, query, timeout, queriesLeft - 1)
        return d


    def _discoveredAuthority(self, response, query, timeout, queriesLeft):
        """
        Interpret the response to a query, checking for error codes and
        following delegations if necessary.

        @param response: The L{Message} received in response to issuing C{query}.
        @type response: L{Message}

        @param query: The L{dns.Query} which was issued.
        @type query: L{dns.Query}.

        @param timeout: The timeout to use if another query is indicated by
            this response.
        @type timeout: L{tuple} of L{int}

        @param queriesLeft: A C{int} giving the number of queries which may
            yet be attempted to answer this query before the attempt will be
            abandoned.

        @return: A L{Failure} indicating a response error, a three-tuple of
            lists of L{RRHeaders} giving the response to C{query} or a
            L{Deferred} which will fire with one of those.
        """
        if response.rCode != dns.OK:
            return Failure(self.exceptionForCode(response.rCode)(response))

        # Turn the answers into a structure that's a little easier to work with.
        records = {}
        for answer in response.answers:
            records.setdefault(answer.name, []).append(answer)

        def findAnswerOrCName(name, type, cls):
            cname = None
            for record in records.get(name, []):
                if record.cls ==  cls:
                    if record.type == type:
                        return record
                    elif record.type == dns.CNAME:
                        cname = record
            # If there were any CNAME records, return the last one.  There's
            # only supposed to be zero or one, though.
            return cname

        seen = set()
        name = query.name
        record = None
        while True:
            seen.add(name)
            previous = record
            record = findAnswerOrCName(name, query.type, query.cls)
            if record is None:
                if name == query.name:
                    # If there's no answer for the original name, then this may
                    # be a delegation.  Code below handles it.
                    break
                else:
                    # Try to resolve the CNAME with another query.
                    d = self._discoverAuthority(
                        dns.Query(str(name), query.type, query.cls),
                        self._roots(), timeout, queriesLeft)
                    # We also want to include the CNAME in the ultimate result,
                    # otherwise this will be pretty confusing.
                    def cbResolved(results):
                        answers, authority, additional = results
                        answers.insert(0, previous)
                        return (answers, authority, additional)
                    d.addCallback(cbResolved)
                    return d
            elif record.type == query.type:
                return (
                    response.answers,
                    response.authority,
                    response.additional)
            else:
                # It's a CNAME record.  Try to resolve it from the records
                # in this response with another iteration around the loop.
                if record.payload.name in seen:
                    raise error.ResolverError("Cycle in CNAME processing")
                name = record.payload.name


        # Build a map to use to convert NS names into IP addresses.
        addresses = {}
        for rr in response.additional:
            if rr.type == dns.A:
                addresses[rr.name.name] = rr.payload.dottedQuad()

        hints = []
        traps = []
        for rr in response.authority:
            if rr.type == dns.NS:
                ns = rr.payload.name.name
                if ns in addresses:
                    hints.append((addresses[ns], dns.PORT))
                else:
                    traps.append(ns)
        if hints:
            return self._discoverAuthority(
                query, hints, timeout, queriesLeft)
        elif traps:
            d = self.lookupAddress(traps[0], timeout)
            def getOneAddress(results):
                answers, authority, additional = results
                return answers[0].payload.dottedQuad()
            d.addCallback(getOneAddress)
            d.addCallback(
                lambda hint: self._discoverAuthority(
                    query, [(hint, dns.PORT)], timeout, queriesLeft - 1))
            return d
        else:
            return Failure(error.ResolverError(
                    "Stuck at response without answers or delegation"))


    def discoveredAuthority(self, auth, name, cls, type, timeout):
        warnings.warn(
            'twisted.names.root.Resolver.discoveredAuthority is deprecated since '
            'Twisted 10.0.  Use twisted.names.client.Resolver directly, instead.',
            category=DeprecationWarning, stacklevel=2)
        from twisted.names import client
        q = dns.Query(name, type, cls)
        r = client.Resolver(servers=[(auth, dns.PORT)])
        d = r.queryUDP([q], timeout)
        d.addCallback(r.filterAnswers)
        return d



def lookupNameservers(host, atServer, p=None):
    warnings.warn(
        'twisted.names.root.lookupNameservers is deprecated since Twisted '
        '10.0.  Use twisted.names.root.Resolver.lookupNameservers instead.',
        category=DeprecationWarning, stacklevel=2)
    # print 'Nameserver lookup for', host, 'at', atServer, 'with', p
    if p is None:
        p = dns.DNSDatagramProtocol(_DummyController())
        p.noisy = False
    return retry(
        (1, 3, 11, 45),                     # Timeouts
        p,                                  # Protocol instance
        (atServer, dns.PORT),               # Server to query
        [dns.Query(host, dns.NS, dns.IN)]   # Question to ask
    )

def lookupAddress(host, atServer, p=None):
    warnings.warn(
        'twisted.names.root.lookupAddress is deprecated since Twisted '
        '10.0.  Use twisted.names.root.Resolver.lookupAddress instead.',
        category=DeprecationWarning, stacklevel=2)
    # print 'Address lookup for', host, 'at', atServer, 'with', p
    if p is None:
        p = dns.DNSDatagramProtocol(_DummyController())
        p.noisy = False
    return retry(
        (1, 3, 11, 45),                     # Timeouts
        p,                                  # Protocol instance
        (atServer, dns.PORT),               # Server to query
        [dns.Query(host, dns.A, dns.IN)]    # Question to ask
    )

def extractAuthority(msg, cache):
    warnings.warn(
        'twisted.names.root.extractAuthority is deprecated since Twisted '
        '10.0.  Please inspect the Message object directly.',
        category=DeprecationWarning, stacklevel=2)
    records = msg.answers + msg.authority + msg.additional
    nameservers = [r for r in records if r.type == dns.NS]

    # print 'Records for', soFar, ':', records
    # print 'NS for', soFar, ':', nameservers

    if not nameservers:
        return None, nameservers
    if not records:
        raise IOError("No records")
    for r in records:
        if r.type == dns.A:
            cache[str(r.name)] = r.payload.dottedQuad()
    for r in records:
        if r.type == dns.NS:
            if str(r.payload.name) in cache:
                return cache[str(r.payload.name)], nameservers
    for addr in records:
        if addr.type == dns.A and addr.name == r.name:
            return addr.payload.dottedQuad(), nameservers
    return None, nameservers

def discoverAuthority(host, roots, cache=None, p=None):
    warnings.warn(
        'twisted.names.root.discoverAuthority is deprecated since Twisted '
        '10.0.  Use twisted.names.root.Resolver.lookupNameservers instead.',
        category=DeprecationWarning, stacklevel=4)

    if cache is None:
        cache = {}

    rootAuths = list(roots)

    parts = host.rstrip('.').split('.')
    parts.reverse()

    authority = rootAuths.pop()

    soFar = ''
    for part in parts:
        soFar = part + '.' + soFar
        # print '///////',  soFar, authority, p
        msg = defer.waitForDeferred(lookupNameservers(soFar, authority, p))
        yield msg
        msg = msg.getResult()

        newAuth, nameservers = extractAuthority(msg, cache)

        if newAuth is not None:
            # print "newAuth is not None"
            authority = newAuth
        else:
            if nameservers:
                r = str(nameservers[0].payload.name)
                # print 'Recursively discovering authority for', r
                authority = defer.waitForDeferred(discoverAuthority(r, roots, cache, p))
                yield authority
                authority = authority.getResult()
                # print 'Discovered to be', authority, 'for', r
##            else:
##                # print 'Doing address lookup for', soFar, 'at', authority
##                msg = defer.waitForDeferred(lookupAddress(soFar, authority, p))
##                yield msg
##                msg = msg.getResult()
##                records = msg.answers + msg.authority + msg.additional
##                addresses = [r for r in records if r.type == dns.A]
##                if addresses:
##                    authority = addresses[0].payload.dottedQuad()
##                else:
##                    raise IOError("Resolution error")
    # print "Yielding authority", authority
    yield authority

discoverAuthority = defer.deferredGenerator(discoverAuthority)

def makePlaceholder(deferred, name):
    def placeholder(*args, **kw):
        deferred.addCallback(lambda r: getattr(r, name)(*args, **kw))
        return deferred
    return placeholder

class DeferredResolver:
    def __init__(self, resolverDeferred):
        self.waiting = []
        resolverDeferred.addCallback(self.gotRealResolver)

    def gotRealResolver(self, resolver):
        w = self.waiting
        self.__dict__ = resolver.__dict__
        self.__class__ = resolver.__class__
        for d in w:
            d.callback(resolver)

    def __getattr__(self, name):
        if name.startswith('lookup') or name in ('getHostByName', 'query'):
            self.waiting.append(defer.Deferred())
            return makePlaceholder(self.waiting[-1], name)
        raise AttributeError(name)

def bootstrap(resolver):
    """Lookup the root nameserver addresses using the given resolver

    Return a Resolver which will eventually become a C{root.Resolver}
    instance that has references to all the root servers that we were able
    to look up.
    """
    domains = [chr(ord('a') + i) for i in range(13)]
    # f = lambda r: (log.msg('Root server address: ' + str(r)), r)[1]
    f = lambda r: r
    L = [resolver.getHostByName('%s.root-servers.net' % d).addCallback(f) for d in domains]
    d = defer.DeferredList(L)
    d.addCallback(lambda r: Resolver([e[1] for e in r if e[0]]))
    return DeferredResolver(d)
