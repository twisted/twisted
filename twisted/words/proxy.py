# -*- test-case-name: twisted.words.test.test_proxy -*-

"""
AMP <-> Anything chat proxy

@author: L{Jean-Paul Calderone<exarkun@divmod.com>}
@author: L{Chrisopher Armstrong<radix@twistedmatrix.com>}

@stability: unstable
"""

__metaclass__ = type

from zope.interface import implements, Interface, Attribute

from twisted.python.failure import Failure

from twisted.internet import reactor
from twisted.internet.defer import Deferred, succeed, AlreadyCalledError
from twisted.internet.protocol import ClientFactory
from twisted.internet.ssl import Certificate
from twisted.internet.interfaces import ICertificate

from twisted.protocols.amp import AMP, Command


class IProxyUser(Interface):
    avatarId = Attribute("UNIQUE!  STRING")



class CertificateChecker:
    credentialInterfaces = (ICertificate,)

    def requestAvatarId(self, credentials):
        """
        SSL sucks.

        By this point, the client certificate has already been verified; if
        it's got here, just return an avatar ID.
        """
        return credentials.digest()



class _CachedProtocolFactory(ClientFactory):
    """
    A factory for use with ConnectionCache. Don't use it.
    """
    def __init__(self, cache, host, port, protocolClass):
        self.cache = cache
        self.protocolClass = protocolClass
        self.host = host
        self.port = port
        self.ckey = self.host, self.port, self.protocolClass
        self.connectionEvent = _PendingEvent()
        self.cache._connections[self.ckey] = self


    def buildProtocol(self, addr):
        protocol = self.protocolClass()
        self.connectionEvent.callback(protocol)
        return protocol


    def clientConnectionLost(self, connector, reason):
        del self.cache._connections[self.ckey]


    def clientConnectionFailed(self, connector, reason):
        self.clientConnectionLost(connector, reason)
        self.connectionEvent.errback(reason)



class ConnectionCache(object):
    """
    CACHING THING
    """

    def __init__(self, reactor):
        self._connections = {}  # map (host, port, protocolClass) to _CachedProtocolFactory
        self.reactor = reactor

    def getConnection(self, host, port, protocolClass):
        ckey = (host, port, protocolClass)
        fac = self._connections.get(ckey)
        if fac is None:
            fac = _CachedProtocolFactory(self, host, port, protocolClass)
            self.reactor.connectTCP(host, port, fac)
        return fac.connectionEvent.deferred()


class _PendingEvent(object):
    """
    A utility for generating aDeferreds which will all be fired or
    errbacked with the same result or failure.
    """
    _result = object()

    def __init__(self):
        """
        Create a pending event.
        """
        self.listeners = []

    def deferred(self):
        """
        Generate and track a new Deferred which represents my
        resolution and return it.

        @return: a Deferred.
        """
        d = Deferred()
        if self._result is not _PendingEvent._result:
            return succeed(self._result)
        self.listeners.append(d)
        return d

    def callback(self, result):
        """ 
        Fire each of the deferreds generated with my L{deferred}
        method.

        @param result: Anything.

        @raise: AlreadyCalledError if I have already been callbacked
        or errbacked.
        """
        l = self.listeners
        if l is None:
            raise AlreadyCalledError()
        self.listeners = None
        self._result = result
        for d in l:
            d.callback(result)

    def errback(self, result=None):
        """ 
        Errback each of the deferreds generated with my L{deferred}
        method.

        @param result: An optional failure object; if unspecified (or
        None), generate a failure from the current exception
        information and use it.

        @raise: AlreadyCalledError if I have already been callbacked
        or errbacked.
        """
        if result is None:
            result = Failure()
        l = self.listeners
        if l is None:
            raise AlreadyCalledError()
        self.listeners = None
        self._result = result
        for d in l:
            d.errback(result)


class ProxyUser:
    implements(IProxyUser)

    def __init__(self, avatarId, reactor):
        self.avatarId = avatarId
        self.reactor = reactor
        self.ircServers = []
        self._ircConnections = {}


    def addIRCServer(self,
                     name,
                     hostname, portNumber,
                     nickname, password,
                     username, realname):
        """
        Register an IRC server so channels can be joined later.

        @param name: The name to give this IRC server, to be used to identify
        this server for later joining.
        """
        self.ircServers.append({
                'name': name,
                'hostname': hostname,
                'portNumber': portNumber,
                'nickname': nickname,
                'password': password,
                'username': username,
                'realname': realname})


    def getIRCServers(self):
        return self.ircServers





class ProxyRealm:
    def requestAvatar(self, avatarId, mind, iface):
        # FIXME: Parameterize reactor.
        return iface, ProxyUser(avatarId, reactor), lambda: None



class AssociateAvatar(Command):
    """
    Mandatory command.  Invoke it.
    """


class ProxyServer(AMP):
    """
    The secret to using this protocol is::

      * Issue StartTLS
      * Issue AssociateAvatar
      * Party
    """
    avatar = None

    def __init__(self, portal):
        self.portal = portal


    # XXX Fixme: Life sucks.  Commit suicide.
    def associateAvatar(self):
        d = self.portal.login(Certificate.peerFromTransport(self.transport), None, IProxyUser)
        def loggedIn((interface, avatar, logout)):
            self.avatar = avatar
            self.logout = logout
            return {}
        d.addCallback(loggedIn)
        return d
    AssociateAvatar.responder(associateAvatar)
