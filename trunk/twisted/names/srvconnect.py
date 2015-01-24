# -*- test-case-name: twisted.names.test.test_srvconnect -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

from functools import reduce

from zope.interface import implements

from twisted.internet import error, interfaces
from twisted.names import client, dns
from twisted.names.error import DNSNameError
from twisted.python.compat import unicode


class _SRVConnector_ClientFactoryWrapper:
    def __init__(self, connector, wrappedFactory):
        self.__connector = connector
        self.__wrappedFactory = wrappedFactory

    def startedConnecting(self, connector):
        self.__wrappedFactory.startedConnecting(self.__connector)

    def clientConnectionFailed(self, connector, reason):
        self.__connector.connectionFailed(reason)

    def clientConnectionLost(self, connector, reason):
        self.__connector.connectionLost(reason)

    def __getattr__(self, key):
        return getattr(self.__wrappedFactory, key)



class SRVConnector:
    """A connector that looks up DNS SRV records. See RFC2782."""

    implements(interfaces.IConnector)

    stopAfterDNS=0

    def __init__(self, reactor, service, domain, factory,
                 protocol='tcp', connectFuncName='connectTCP',
                 connectFuncArgs=(),
                 connectFuncKwArgs={},
                 defaultPort=None,
                 ):
        """
        @param domain: The domain to connect to.  If passed as a unicode
            string, it will be encoded using C{idna} encoding.
        @type domain: L{bytes} or L{unicode}
        @param defaultPort: Optional default port number to be used when SRV
            lookup fails and the service name is unknown. This should be the
            port number associated with the service name as defined by the IANA
            registry.
        @type defaultPort: C{int}
        """
        self.reactor = reactor
        self.service = service
        if isinstance(domain, unicode):
            domain = domain.encode('idna')
        self.domain = domain
        self.factory = factory

        self.protocol = protocol
        self.connectFuncName = connectFuncName
        self.connectFuncArgs = connectFuncArgs
        self.connectFuncKwArgs = connectFuncKwArgs
        self._defaultPort = defaultPort

        self.connector = None
        self.servers = None
        self.orderedServers = None # list of servers already used in this round

    def connect(self):
        """Start connection to remote server."""
        self.factory.doStart()
        self.factory.startedConnecting(self)

        if not self.servers:
            if self.domain is None:
                self.connectionFailed(error.DNSLookupError("Domain is not defined."))
                return
            d = client.lookupService('_%s._%s.%s' % (self.service,
                                                     self.protocol,
                                                     self.domain))
            d.addCallbacks(self._cbGotServers, self._ebGotServers)
            d.addCallback(lambda x, self=self: self._reallyConnect())
            if self._defaultPort:
                d.addErrback(self._ebServiceUnknown)
            d.addErrback(self.connectionFailed)
        elif self.connector is None:
            self._reallyConnect()
        else:
            self.connector.connect()

    def _ebGotServers(self, failure):
        failure.trap(DNSNameError)

        # Some DNS servers reply with NXDOMAIN when in fact there are
        # just no SRV records for that domain. Act as if we just got an
        # empty response and use fallback.

        self.servers = []
        self.orderedServers = []

    def _cbGotServers(self, (answers, auth, add)):
        if len(answers) == 1 and answers[0].type == dns.SRV \
                             and answers[0].payload \
                             and answers[0].payload.target == dns.Name('.'):
            # decidedly not available
            raise error.DNSLookupError("Service %s not available for domain %s."
                                       % (repr(self.service), repr(self.domain)))

        self.servers = []
        self.orderedServers = []
        for a in answers:
            if a.type != dns.SRV or not a.payload:
                continue

            self.orderedServers.append((a.payload.priority, a.payload.weight,
                                        str(a.payload.target), a.payload.port))

    def _ebServiceUnknown(self, failure):
        """
        Connect to the default port when the service name is unknown.

        If no SRV records were found, the service name will be passed as the
        port. If resolving the name fails with
        L{error.ServiceNameUnknownError}, a final attempt is done using the
        default port.
        """
        failure.trap(error.ServiceNameUnknownError)
        self.servers = [(0, 0, self.domain, self._defaultPort)]
        self.orderedServers = []
        self.connect()

    def _serverCmp(self, a, b):
        if a[0]!=b[0]:
            return cmp(a[0], b[0])
        else:
            return cmp(a[1], b[1])

    def pickServer(self):
        assert self.servers is not None
        assert self.orderedServers is not None

        if not self.servers and not self.orderedServers:
            # no SRV record, fall back..
            return self.domain, self.service

        if not self.servers and self.orderedServers:
            # start new round
            self.servers = self.orderedServers
            self.orderedServers = []

        assert self.servers

        self.servers.sort(self._serverCmp)
        minPriority=self.servers[0][0]

        weightIndex = zip(xrange(len(self.servers)), [x[1] for x in self.servers
                                                      if x[0]==minPriority])
        weightSum = reduce(lambda x, y: (None, x[1]+y[1]), weightIndex, (None, 0))[1]

        for index, weight in weightIndex:
            weightSum -= weight
            if weightSum <= 0:
                chosen = self.servers[index]
                del self.servers[index]
                self.orderedServers.append(chosen)

                p, w, host, port = chosen
                return host, port

        raise RuntimeError, 'Impossible %s pickServer result.' % self.__class__.__name__

    def _reallyConnect(self):
        if self.stopAfterDNS:
            self.stopAfterDNS=0
            return

        self.host, self.port = self.pickServer()
        assert self.host is not None, 'Must have a host to connect to.'
        assert self.port is not None, 'Must have a port to connect to.'

        connectFunc = getattr(self.reactor, self.connectFuncName)
        self.connector=connectFunc(
            self.host, self.port,
            _SRVConnector_ClientFactoryWrapper(self, self.factory),
            *self.connectFuncArgs, **self.connectFuncKwArgs)

    def stopConnecting(self):
        """Stop attempting to connect."""
        if self.connector:
            self.connector.stopConnecting()
        else:
            self.stopAfterDNS=1

    def disconnect(self):
        """Disconnect whatever our are state is."""
        if self.connector is not None:
            self.connector.disconnect()
        else:
            self.stopConnecting()

    def getDestination(self):
        assert self.connector
        return self.connector.getDestination()

    def connectionFailed(self, reason):
        self.factory.clientConnectionFailed(self, reason)
        self.factory.doStop()

    def connectionLost(self, reason):
        self.factory.clientConnectionLost(self, reason)
        self.factory.doStop()

