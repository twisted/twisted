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
#
# Publishing!!!!
#
# host names are unicode
# compare host names case-insensitively

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

    def serviceRemoved(self, name):
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
        # in all cases name is unicode string, the Instance part of the
        # <Instance>.<Service>.<Domain> full string
        self.addresses = {} # map name to (domainname, port)
        self.expires = {} # map name to DelayedCall
        self.timeouts = {} # mpa name to list of timeouts
        self.intervals = self._generateIntervals()
        self._sendQuery()

    def getName(self, instanceName):
        return unicode(instanceName[:-len(self.service) - 1], "UTF-8")
    
    def _sendQuery(self):
        """Send out the DNS query for this service."""
        # XXX add Known Answers, first should be set to ask for unicast
        self.resolver.protocol.write(queries=[dns.Query(self.service, dns.PTR, dns.IN)])
        self._scheduledQuery = reactor.callLater(self.intervals.next(),
                                                 self._sendQuery)
    
    def _generateIntervals(self):
        """Intervals of querying for the records."""
        for i in (1, 3, 7, 15, 31, 63, 128, 256):
            yield i
        while True:
            yield 600
    
    def unsubscribe(self, subscriber):
        self.subscribers.remove(subscriber)
        if not self.subscribers:
            self._scheduledQuery.cancel()
            self.resolver._removeSubscription(self.service)

    def subscribe(self, subscriber):
        self.subscribers.append(subscriber)

    def gotPTR(self, record):
        """Called by resolver with PTR for our service type."""
        # we use the SRV's TTL to expire PTR records, as if the SRV
        # goes away the PTR is useless, and so long as it exists
        # we're happy.
        name = self.getName(str(record.name))
        if not self.addresses.has_key(name):
            self.resolver.query(dns.Query(str(record.name), dns.SRV, dns.IN))

    def _expire(self, name, write=True):
        assert isinstance(name, unicode)
        timeouts = self.timeouts[name]
        if timeouts:
            self.expires[name] = reactor.callLater(timeouts[0], self._expire, name)
            self.timeouts[name] = timeouts[1:]
            if write:
                self.resolver.protocol.write(queries=[
                    dns.Query("%s.%s" % (name.encode("UTF-8"), self.service), dns.SRV, dns.IN)])
        else:
            del self.expires[name]
            del self.timeouts[name]
            del self.addresses[name]
            for s in self.subscribers:
                s.serviceRemoved(name)
    
    def gotSRV(self, instanceName, record):
        """Called by resolver with SRV for our service type."""
        name = self.getName(instanceName)
        ttl = record.ttl
        timeouts = [((x + random.uniform(0, 0.02))) * ttl for x in (0.8, 0.05, 0.05)]
        if self.addresses.has_key(name):            
            self.expires[name].cancel()
            self.timeouts[name] = timeouts
            self._expire(name, write=False)
            return
        self.addresses[name] = str(record.target), record.port
        self.timeouts[name] = timeouts
        self._expire(name, write=False)
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
        name = str(query.name)
        if self.queries.has_key((query.type, name)):
            self.queries[(query.type, name)][0].append(d)
        else:
            self.queries[(query.type, name)] = [[d], timeouts[1:]]
            reactor.callLater(timeouts[0], self._queryTimeout, query)
            self.protocol.write(queries=[query])
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
            self.protocol.write(queries=[query])

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
            return self.query(dns.Query(domain, dns.A, dns.IN)).addCallback(
                self._cbResolved, domain)
    
    # internal methods
    
    def messageReceived(self, message, address):
        #print message.queries, message.answers, message.answer
        if not message.answer:
            # a query. it might have some Known Answers, but those
            # are not authorative and should be ignored.
            return
        for r in message.answers:
            # Mac OS X doesn't set authoritative bit?!
            #if not r.isAuthoritative():
            #    continue
            pattern = (r.type, str(r.name))
            if self.queries.has_key(pattern):
                for d in self.queries[pattern][0]:
                    d.callback(message)
                del self.queries[pattern]
            if r.type == dns.PTR:
                service = r.name.name
                if self.subscriptions.has_key(service):
                    self.subscriptions[service].gotPTR(r.payload)
            elif r.type == dns.SRV:
                instanceName = r.name.name
                for service, subscription in self.subscriptions.items():
                    # for service '_ichat._tcp.local', the name for
                    # iChat user might be 'Mr Smith._ichat._tcp.local'
                    if instanceName.endswith(service):
                        # we might have gotten A record with this SRV, so to make sure we have its
                        # IP cached we put off the notification slightly
                        reactor.callLater(0, subscription.gotSRV, instanceName, r.payload)
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
        reactor.listenMulticast(5353, self, maxPacketSize=1024, listenMultiple=True)
        self.transport.joinGroup(MDNS_ADDRESS)
        self.transport.setTTL(255)

    def datagramReceived(self, data, addr):
        m = dns.Message()
        m.fromStr(data)
        self.mResolver.messageReceived(m, addr)

    def write(self, queries=(), answers=(), id=None):
        if id is None:
            id = random.randrange(2 ** 10, 2 ** 15)
        m = dns.Message(id, recDes=1)
        m.queries = queries
        m.answers = answers
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
