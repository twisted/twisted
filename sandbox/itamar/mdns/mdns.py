# TODO
#
# Check TTL of responses is 255
#
# Service discovery APIs

from twisted.internet import reactor
from twisted.protocols import dns
from twisted.python.components import Interface


class ISubscriber(Interface):

    def domainAdded(self, domain):
        """Domain connected to network."""

    def domainRemoved(self, domain):
        """Domain is no longer in network."""


class mDNSResolver:
    """Resolve mDNS queries.

    This implements the continous resolving method, so it also knows
    what domains are available in the local network. As such there
    is only need for one such object during a program's lifetime.

    Startup behaviour:
    1. Send out multicast asking for 'domains' (what's that going to mean)?
    with QU set.
    2. After that send standard multicast with known answers at growing intervals.

    New records get TTL timeout, at close to expiry (80, 90, 95 percent) we do
    query for them.
    """

    def __init__(self):
        self.protocol = mDNSDatagramProtocol(self)


    # external API
    
    def startListening(self):
        self.protocol.startListening()

    def stopListening(self):
        # XXX
        pass
    
    def getDomains(self):
        """Return list of domains the resolver knows about."""
        
    def subscribe(self, subcriber):
        pass

    def unsubscribe(self, subcriber):
        pass

    def query(self, queries):
        """Do a mDNS query."""


    # internal methods
    
    def messageReceived(self, message, protocol, address = None):
        print "questions", message.queries
        print "answers", message.answers


class mDNSDatagramProtocol(dns.DNSDatagramProtocol):
    """Multicast DNS support."""

    def startListening(self):
        reactor.listenMulticast(5353, self, listenMultiple=True)
        self.transport.joinGroup("224.0.0.251")
        self.transport.setTTL(255)


if __name__ == '__main__':
    d = mDNSResolver()
    d.startListening()
    reactor.run()
