# Twisted, the Framework of Your Internet
# Copyright (C) 2001-2002 Matthew W. Lefkowitz
# 
# This library is free software; you can redistribute it and/or
# modify it under the terms of version 2.1 of the GNU Lesser General Public
# License as published by the Free Software Foundation.
# 
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
# 
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
# 

"""Utility methods."""

from twisted.internet import protocol, reactor, defer
from twisted.python import failure
from twisted.names import client

try:
    import cStringIO as StringIO
except ImportError:
    import StringIO


def _callProtocolWithDeferred(protocol, executable, args, env, path, reactor):
    d = defer.Deferred() 
    p = protocol(d)
    reactor.spawnProcess(p, executable, (executable,)+tuple(args), env, path)
    return d


class _BackRelay(protocol.ProcessProtocol):

    def __init__(self, deferred):
        self.deferred = deferred
        self.s = StringIO.StringIO()

    def errReceived(self, text):
        self.deferred.errback(failure.Failure(IOError("got stderr")))
        self.deferred = None
        self.transport.loseConnection()

    def outReceived(self, text):
        self.s.write(text)

    def processEnded(self, reason):
        if self.deferred is not None:
            self.deferred.callback(self.s.getvalue())


def getProcessOutput(executable, args=(), env={}, path='.', reactor=reactor):
    """Spawn a process and return its output as a deferred returning a string.

    @param executable: The file name to run and get the output of - the
                       full path should be used.

    @param args: the command line arguments to pass to the process; a
                 sequence of strings. The first string should *NOT* be the
                 executable's name.

    @param env: the environment variables to pass to the processs; a
                dictionary of strings.

    @param path: the path to run the subprocess in - defaults to the
                 current directory.

    @param reactor: the reactor to use - defaults to the default reactor
    """
    return _callProtocolWithDeferred(_BackRelay, executable, args, env, path,
                                    reactor)


class _ValueGetter(protocol.ProcessProtocol):

    def __init__(self, deferred):
        self.deferred = deferred

    def processEnded(self, reason):
        self.deferred.callback(reason.value.exitCode)


def getProcessValue(executable, args=(), env={}, path='.', reactor=reactor):
    """Spawn a process and return its exit code as a Deferred."""
    return _callProtocolWithDeferred(_ValueGetter, executable, args, env, path,
                                    reactor)


import random
from twisted.internet import error, interfaces

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

    __implements__ = interfaces.IConnector

    stopAfterDNS=0

    def __init__(self, reactor, service, domain, factory,
                 protocol='tcp', connectFuncName='connectTCP',
                 connectFuncArgs=(),
                 connectFuncKwArgs={},
                 ):
        self.reactor = reactor
        self.service = service
        self.domain = domain
        self.factory = factory

        self.protocol = protocol
        self.connectFuncName = connectFuncName
        self.connectFuncArgs = connectFuncArgs
        self.connectFuncKwArgs = connectFuncKwArgs

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
            d.addCallback(self._cbGotServers)
            d.addCallback(lambda x, self=self: self._reallyConnect())
            d.addErrback(self.connectionFailed)
        elif self.connector is None:
            self._reallyConnect()
        else:
            self.connector.connect()

    def _cbGotServers(self, (answers, auth, add)):
        if len(answers)==1 and answers[0].payload.target=='.':
            # decidedly not available
            raise error.DNSLookupError("Service %s not available for domain %s."
                                       % (repr(self.service), repr(self.domain)))

        self.servers = []
        self.orderedServers = []
        for a in answers:
            self.orderedServers.append((a.payload.priority, a.payload.weight,
                                        str(a.payload.target), a.payload.port))

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
        rand = random.randint(0, weightSum)

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
