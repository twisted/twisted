"""mDNS with service discovery support.

Usage:

1. Call the module-level function startListening() when your app
   wishes to use mDNS, before doing any other operation. Call the
   module-level function stopListening() when your app finishes using
   mDNS.

2. Use top level functions resolve() and subscribeService().

This makes sure you only run one resolver per process.
"""

# TODO
#
# Check TTL of responses is 255
#
# Make ServiceSubscriptions pickleable?!

import random

from twisted.internet import reactor, defer, protocol
from twisted.protocols import dns
from twisted.python import failure
from twisted.python.components import Interface
from twisted.persisted.styles import Ephemeral


MDNS_ADDRESS = "224.0.0.251"


class ISubscriber(Interface):

    def serviceAdded(self, name, host, port):
        """Service connected to network."""

    def serviceRemoved(self, name, host, port):
        """Service is no longer in network."""


class IServiceSubscription(Interface):
    """Subscription to a SRV-style service, e.g. '_http._tcp.local'."""

    def unsubscribe(self, subscriber):
        """Remove an ISubscriber."""

    def getServices(self):
        """Return list of tuples (name, host, port)."""


class ServiceSubscription(Ephemeral):
    """
    Startup behaviour:
    1. Send out multicast asking for 'domains' (what's that going to mean)?
    with QU set.
    2. After that send standard multicast with known answers at growing intervals.

    New records get TTL timeout, at close to expiry (80, 90, 95 percent) we do
    query for them.
    """

    __implements__ = IServiceSubscription,

    def __init__(self, service, resolver):
        self.service = service
        self.resolver = resolver
        self.subscribers = []
        self.addresses = {} # map name to (domainname, port)
        self.intervals = self._generateIntervals()
        self._sendQuery()

    def _sendQuery(self):
        """Send out the DNS query for this service."""
        # XXX add Known Answers, first should be set to ask for unicast
        self.resolver.protocol.write([dns.Query(self.service, dns.PTR, dns.IN)])
        self._scheduledQuery = reactor.callLater(self.intervals.next(),
                                                 self._sendQuery)
    
    def _generateIntervals(self):
        """Intervals of querying for the records."""
        for i in (1, 3, 7, 15, 31, 63, 128):
            yield i
        while True:
            yield 256
    
    def unsubscribe(self, subscriber):
        self.subscribers.remove(subscriber)
        if not self.subscribers:
            self._scheduledQuery.cancel()
            self.resolver._removeSubscription(self.service)

    def subscribe(self, subscriber):
        self.subscribers.append(subscriber)

    def gotPTR(self, record):
        """Called by resolver with PTR for our service type."""
        name = str(record.payload.name)
        if not self.addresses.has_key(name):
            self.resolver.query(dns.Query(name, dns.SRV, dns.IN))
        
    def gotSRV(self, name, record):
        """Called by resolver with SRV for our service type."""
        # XXX deal with TTLs
        if self.addresses.has_key(name):
            return         # XXX deal with TTLs
        self.addresses[name] = str(record.target), record.port
        for s in self.subscribers:
            s.serviceAdded(name, str(record.target), record.port)


class mDNSResolver(Ephemeral):
    """Resolve mDNS queries.

    This implements the continous resolving method, so it also knows
    what domains are available in the local network. As such there
    is only need for one such object during a program's lifetime.
    """

    _users = 0
    timeouts = (1, 3, 7)
    
    def __init__(self):
        self.protocol = mDNSDatagramProtocol(self)
        self.subscriptions = {} # map service name to ServiceSubscription
        self.cachedDomains = {} # map domain name to IP
        self.domainExpires = {} # map domain name to DelayedCall
        self.queries = {} # map tuple (dns type, name) to [list of Deferreds, list timeouts]
    
    # external API
    
    def startListening(self):
        self._users += 1
        if self._users == 1:
            self.protocol.startListening()
    
    def stopListening(self):
        if self._users == 0:
            # or raise error?
            return
        self._users -= 1
        if self._users == 0:
            self.protocol.transport.stopListening()
            # XXX other cleanup
    
    def subscribeService(self, service, subscriber):
        assert isinstance(service, str)
        if not self.subscriptions.has_key(service):
            self.subscriptions[service] = ServiceSubscription(service, self)
        self.subscriptions[service].subscribe(subscriber)

    def query(self, query, timeouts=None):
        """Return Deferred of dns.Message.

        @param query: a dns.Query.
        """
        if timeouts is None:
            timeouts = self.timeouts
        d = defer.Deferred()
        if self.queries.has_key((query.type, str(query.name))):
            self.queries[(query.type, str(query.name))][0].append(d)
        else:
            self.queries[(query.type, str(query.name))] = [[d], timeouts[1:]]
            reactor.callLater(timeouts[0], self._queryTimeout, query)
            self.protocol.write([query])
        return d
    
    def _queryTimeout(self, query):
        l = self.queries.get((query.type, str(query.name)))
        if not l:
            return
        timeouts = l[1]
        if not timeouts:
            del self.queries[(query.type, str(query.name))]
            for d in l[0]:
                d.errback(failure.Failure(dns.DNSQueryTimeoutError(query)))
        elif self.protocol.transport:
            l[1] = timeouts[1:]
            reactor.callLater(timeouts[0], self._queryTimeout, query)
            self.protocol.write([query])

    def _cbResolved(self, message, domain):
        for r in message.answers:
            if r.type == dns.A and str(r.name) == domain:
                return r.payload.dottedQuad()
        return failure.Failure(dns.DNSQueryTimeoutError(domain))
    
    def resolve(self, domain):
        """Do a A record lookup for domain.

        @return: Deferred of the IP address.
        """
        if self.cachedDomains.has_key(domain):
            return defer.succeed(self.cachedDomains[domain])
        else:
            return self.query(dns.Query(domain, dns.ALL_RECORDS, dns.IN)).addCallback(
                self._cbResolved, domain)
    
    # internal methods
    
    def messageReceived(self, message, address):
        print message.queries, message.answers
        for r in message.answers:
            pattern = (r.type, str(r.name))
            if self.queries.has_key(pattern):
                for d in self.queries[pattern][0]:
                    d.callback(message)
                del self.queries[pattern]
            if r.type == dns.PTR:
                service = r.name.name
                if self.subscriptions.has_key(service):
                    self.subscriptions[service].gotPTR(r)
            elif r.type == dns.SRV:
                name = r.name.name
                for service, subscription in self.subscriptions.items():
                    # for service '_ichat._tcp.local', the name for
                    # iChat user might be 'Mr Smith._ichat._tcp.local'
                    if name.endswith(service):
                        # we might have gotten A record with this SRV, so to make sure we have its
                        # IP cached we put off the notification slightly
                        reactor.callLater(0, subscription.gotSRV, name[:-len(service) - 1], r.payload)
                        break
            elif r.type == dns.A:
                name = str(r.name)
                if self.domainExpires.has_key(name):
                    self.domainExpires[name].delay(r.payload.ttl)
                else:
                    self.cachedDomains[name] = r.payload.dottedQuad()
                    self.domainExpires[name] = reactor.callLater(r.payload.ttl, self._expireDomain, name)
    
    def _removeSubscription(self, service):
        """Called by ServiceSubscription to remove itself."""
        del self.subscriptions[service]

    def _expireDomain(self, name):
        """Called when cached domain expires."""
        del self.cachedDomains[name]
        del self.domainExpires[name]


class mDNSDatagramProtocol(protocol.DatagramProtocol):
    """Multicast DNS support."""
    
    def __init__(self, mResolver):
        self.mResolver = mResolver

    def startListening(self):
        reactor.listenMulticast(5353, self, listenMultiple=True)
        self.transport.joinGroup(MDNS_ADDRESS)
        self.transport.setTTL(255)

    def datagramReceived(self, data, addr):
        m = dns.Message()
        m.fromStr(data)
        self.mResolver.messageReceived(m, addr)

    def write(self, queries, id=None):
        if id is None:
            id = random.randrange(2 ** 10, 2 ** 15)
        m = dns.Message(id, recDes=1)
        m.queries = queries
        self.transport.write(m.toStr(), (MDNS_ADDRESS, 5353))


theResolver = mDNSResolver()
startListening = theResolver.startListening
stopListening = theResolver.stopListening
resolve = theResolver.resolve
subscribeService = theResolver.subscribeService


__all__ = ["IServiceSubscription", "ISubscriber", "stopListening", "startListening",
           "resolve", "subscribeService"]


if __name__ == '__main__':
    class Sub:
        def _resolved(self, ip, host):
            print host, "is actually", ip

        def serviceAdded(self, name, host, port):
            print "%s is ('%s', %s)" % (name, host, port)
            resolve(host).addCallback(self._resolved, host)
            resolve("nosuchhost.local").addCallback(self._resolved, "nosuchhost.local")
    startListening()
    print "Subscribing to _workstation._tcp.local, which should show all Macs on network"
    subscribeService("_workstation._tcp.local", Sub())
    reactor.run()
