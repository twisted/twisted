"""mDNS.

Usage:

1. Call the module-level function startListening() when your app wishes
   to use mDNS. Call the module-level function sttopListening() when your app finishes
   using mDNS.

2. Use top level functions getIP() and subscribeService().

This makes sure you only run one resolver per process.
"""

# TODO
#
# Check TTL of responses is 255
#
# Service discovery APIs

from twisted.internet import reactor, defer
from twisted.protocols import dns
from twisted.python.components import Interface


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


class ServiceSubscription:
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
        self.resolver._sendQuery([dns.Query(service, dns.PTR, dns.IN)])
        # XXX schedule stage new lookups at intervals
    
    def unsubscribe(self, subscriber):
        self.subscribers.remove(subscriber)
        if not self.subscribers:
            self.resolver._removeSubscription(self.service)

    def subscribe(self, subscriber):
        self.subscribers.append(subscriber)

    def gotSRV(self, name, record):
        """Called by resolver with SRV for our service type."""
        # XXX deal with TTLs
        # XXX supress duplicates
        self.addresses[name] = str(record.target), record.port
        for s in self.subscribers:
            s.serviceAdded(name, str(record.target), record.port)


class mDNSResolver:
    """Resolve mDNS queries.

    This implements the continous resolving method, so it also knows
    what domains are available in the local network. As such there
    is only need for one such object during a program's lifetime.
    """

    _users = 0

    def __init__(self):
        self.protocol = mDNSDatagramProtocol(self)
        self.subscriptions = {} # map service name to ServiceSubscription
        self.cachedDomains = {} # map .local domain name to IP

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

    def getIP(self, domain):
        """Do A lookup."""
        if self.cachedDomains.has_key(domain):
            return defer.succeed(self.cachedDomains[domain])
        else:
            # XXX do lookup
            pass
    
    # internal methods
    
    def messageReceived(self, message, protocol, address = None):
        #print message.queries, message.answers
        for r in message.answers:
            if r.type == dns.PTR:
                service = r.name.name
                if self.subscriptions.has_key(service):
                    self._sendQuery([dns.Query(r.payload.name.name, dns.SRV, dns.IN)])
            elif r.type == dns.SRV:
                name = r.name.name
                for service, subscription in self.subscriptions.items():
                    if name.endswith(service):
                        # we might have gotten A record with this SRV, so to make sure we have its
                        # IP cached we put off the notification slightly
                        reactor.callLater(0, subscription.gotSRV, name[:-len(service) - 1], r.payload)
                    break
            elif r.type == dns.A:
                # XXX need to deal with TTL
                self.cachedDomains[str(r.name)] = r.payload.dottedQuad()
    
    def _cbGotQueryResult(self, result):
        self.messageReceived(result, self.protocol)
    
    def _sendQuery(self, queries):
        """Send a query."""
        self.protocol.query((MDNS_ADDRESS, 5353), queries).addCallback(
            self._cbGotQueryResult)

    def _removeSubscription(self, service):
        """Called by ServiceSubscription to remove itself."""
        del self.subscription[service]


class mDNSDatagramProtocol(dns.DNSDatagramProtocol):
    """Multicast DNS support."""

    def startListening(self):
        reactor.listenMulticast(5353, self, listenMultiple=True)
        self.transport.joinGroup(MDNS_ADDRESS)
        self.transport.setTTL(255)


theResolver = mDNSResolver()
startListening = theResolver.startListening
stopListening = theResolver.stopListening
getIP = theResolver.getIP
subscribeService = theResolver.subscribeService


__all__ = ["IServiceSubscription", "ISubscriber", "stopListening", "startListening",
           "getIP", "subscribeService"]


if __name__ == '__main__':
    class Sub:
        def _resolved(self, ip, host):
            print host, "is actually", ip
        
        def serviceAdded(self, name, host, port):
            print "%s is ('%s', %s)" % (name, host, port)
            getIP(host).addCallback(self._resolved, host)
    
    startListening()
    print "Subscribing to _workstation._tcp.local, which should show all Macs on network"
    subscribeService("_workstation._tcp.local", Sub())
    reactor.run()
