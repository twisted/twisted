# -*- test-case-name: twisted.test.test_sister -*-

# Sibling Server

from twisted.spread.pb import Service, Perspective, Error
from twisted.spread.flavors import Referenceable
from twisted.spread.refpath import PathReferenceDirectory
from twisted.internet import defer
from twisted.python import log

from random import choice

class ParentService(Service, Perspective):
    """A `parent' object, managing many sister-servers.

    I maintain a list of all "sister" servers who are connected, so that all
    servers can connect to each other.  I also negotiate which distributed
    objects are owned by which sister servers, so that if any sister-server
    needs to locate an object it can be made available.
    """

    def __init__(self, sharedSecret, serviceName, application=None):
        Service.__init__(self, serviceName, application)
        Perspective.__init__(self, "parent")
        self.addPerspective(self)
        # Three states: unlocked, pending lock, locked
        self.pendingResources = {}      # path: deferred, host, port
        self.toLoadOnConnect = []       # [deferred, deferred, ...]
        self.lockedResources = {}       # path: host, port
        self.daughters = []             # [(host, port, reference)]
        self.makeIdentity(sharedSecret)

    def _cbLoadedResource(self, ticket, resourceType, resourceName, host, port):
        log.msg( 'parent: loaded resource')
        self.lockedResources[(resourceType, resourceName)] = (host, port)
        return ticket

    def loadRemoteResource(self, resourceType, resourceName, generateTicket):
        """Request a sister-server to load a resource.

        Return a Deferred which will fire with (host, port, ticket), that will
        describe where and how a resource can be located.
        """
        # dead-simple positive path case; need more checking for if it's
        # already locked, etc
        log.msg( 'parent: loading resource' )
        if not self.daughters:
            defr = defer.Deferred()
            self.toLoadOnConnect.append((resourceType, resourceName, generateTicket, defr))
            return defr
        (host, port, daughterPerspective) = choice(self.daughters)
        return daughterPerspective.callRemote("loadResource", resourceType, resourceName, generateTicket
                                              ).addCallback(
            self._cbLoadedResource, resourceType, resourceName, host, port)

    def perspectiveMessageReceived(self, broker, message, args, kw):
        """A remote message has been received.  Dispatch it appropriately.

        XXX FIXME this is a temporary workaround because there is no way in the
        framework to allow passing the broker as an argument to a perspective_
        method.
        """
        args = broker.unserialize(args)
        kw = broker.unserialize(kw)
        method = getattr(self, "perspective_%s" % message)
        try:
            state = apply(method, (broker,)+args, kw)
        except TypeError:
            log.msg ("%s didn't accept %s and %s" % (method, args, kw))
            raise
        return broker.serialize(state, self.perspective)

    def brokerAttached(self, cli, ident, broker):
        log.msg( 'parent: daughter attached %s' % repr(self.daughters))
        port, ref = cli
        host = broker.transport.getPeer()[1]
        self.daughters.append((host, port, ref))
        toLoad = self.toLoadOnConnect
        self.toLoadOnConnect = []
        for resourceType, resourceName, generateTicket, deferred in toLoad:
            self.loadRemoteResource(resourceType, resourceName, generateTicket).chainDeferred(deferred)
        log.msg('sister attached: %s:%s %r' % (host, port, ref))
        return self

    def brokerDetached(self, cli, ident, broker):
        port, ref = cli
        host = broker.transport.getPeer()[1]
        self.daughters.remove((host, port, ref))
        for path, (lhost, lport) in self.lockedResources.items():
            if (host, port) == (lhost, lport):
                # XXX do i need some kind of notification here?
                del self.lockedResources[path]
        log.msg( 'sister detached %s:%s %r' % (host, port, ref))
        return self

    def _cbLoaded(self, ignored, path):
        d, host, port = self.pendingResources[path]
        del self.pendingResources[path]
        self.lockedResources[path] = (host, port)
        d.callback((host, port))
    def _ebLoaded(self, error, path):
        d, host, port = self.pendingResources[path]
        del self.pendingResources[path]
        d.errback(error)

