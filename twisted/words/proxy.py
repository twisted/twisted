# -*- test-case-name: twisted.words.test.test_proxy -*-

"""
AMP <-> Anything chat proxy

@author: L{Jean-Paul Calderone<exarkun@divmod.com>}
@author: L{Chrisopher Armstrong<radix@twistedmatrix.com>}

@stability: unstable
"""

__metaclass__ = type

from zope.interface import implements, Interface, Attribute

from twisted.internet import reactor
from twisted.internet.defer import Deferred, succeed
from twisted.internet.protocol import ClientCreator
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



class ConnectionCache(object):
    """
    CACHING THING
    """

    def __init__(self, reactor):
        self._connections = {}
        self._inprogress = {} # {cachekey: connector}
        self.reactor = reactor


    def _getConnectionFromCache(self, host, port, protocolClass):
        return self._connections.get((host, port, protocolClass))


    def _addConnectionToCache(self, host, port, protocolClass, connection):
        self._connections[host, port, protocolClass] = connection


    def _connectServer(self, host, port, protocolClass):
        cc = ClientCreator(self.reactor, protocolClass)
        return cc.connectTCP(host, port)


    def _broadcast(self, proto, deferred):
        deferred.callback(proto)
        return proto


    def _relocate(self, proto, host, port, protocolClass):
        del self._inprogress[host, port]
        self._addConnectionToCache(host, port, protocolClass, proto)
        return proto


    def getConnection(self, host, port, protocolClass):
        connection = self._getConnectionFromCache(host, port, protocolClass)
        if connection is not None:
            return succeed(connection)
        if (host, port) in self._inprogress:
            d = Deferred()
            self._inprogress[host, port].addCallback(self._broadcast, d)
            return d
        d = self._connectServer(host, port, protocolClass)
        d.addCallback(self._relocate, host, port, protocolClass)
        self._inprogress[host, port] = d
        return d



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
