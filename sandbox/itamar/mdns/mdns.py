# TODO
#
# Check TTL of responses is 255
#
# Service discovery APIs

from twisted.internet import reactor
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
        self.addresses = {} # map name to (host, port)

    def unsubscribe(self, subscriber):
        self.subscribers.remove(subscriber)
        if not self.subscribers:
            del self.service.subscriptions[self.service]

    def subscribe(self, subscriber):
        self.subscribers.append(subscriber)

    def gotSRV(self, name, record):
        """Called by resolver with SRV for our service type."""
        # XXX deal with TTLs
        self.addresses[name] = str(record.target), record.port
        for s in self.subscribers:
            s.serviceAdded(name, str(record.target), record.port)


class mDNSResolver:
    """Resolve mDNS queries.

    This implements the continous resolving method, so it also knows
    what domains are available in the local network. As such there
    is only need for one such object during a program's lifetime.
    """

    def __init__(self):
        self.protocol = mDNSDatagramProtocol(self)
        self.subscriptions = {}

    # external API
    
    def startListening(self):
        self.protocol.startListening()
        # XXX set QU
        self._sendQuery([dns.Query('_workstation._tcp.local', dns.PTR, dns.IN)])
    
    def stopListening(self):
        # XXX
        pass
            
    def subscribeService(self, service, subscriber):
        assert isinstance(service, str)
        if not self.subscriptions.has_key(service):
            self.subscriptions[service] = ServiceSubscription(service, self)
        self.subscriptions[service].subscribe(subscriber)
    
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
                        subscription.gotSRV(name, r.payload)
                    break
    
    def _cbGotQueryResult(self, result):
        self.messageReceived(result, self.protocol)
    
    def _sendQuery(self, queries):
        """Send a query."""
        self.protocol.query((MDNS_ADDRESS, 5353), queries).addCallback(
            self._cbGotQueryResult)


class mDNSDatagramProtocol(dns.DNSDatagramProtocol):
    """Multicast DNS support."""

    def startListening(self):
        reactor.listenMulticast(5353, self, listenMultiple=True)
        self.transport.joinGroup(MDNS_ADDRESS)
        self.transport.setTTL(255)


if __name__ == '__main__':
    class Sub:
        def serviceAdded(self, *args):
            print args
    
    d = mDNSResolver()
    print "Subscribing to _workstation._tcp.local, which should show all Macs on network"
    d.subscribeService("_workstation._tcp.local", Sub())
    d.startListening()
    reactor.run()
