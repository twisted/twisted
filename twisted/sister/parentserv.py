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
        self.sisters = []             # [(host, port, reference)]
        self.makeIdentity(sharedSecret)
        
    def _cbLoadedResource(self, ticket, resourceType, resourceName, host, port, sisterPerspective):
        log.msg( 'parent: loaded resource')
        self.lockedResources[(resourceType, resourceName)] = (host, port, sisterPerspective)
        return (ticket, host, port, sisterPerspective)

    def loadRemoteResource(self, resourceType, resourceName, generateTicket):
        """Request a sister-server to load a resource.

        NOTE: caching of ticket resources could be an issue... do we cache tickets??
        
        Return a Deferred which will fire with (ticket, host, port), that will
        describe where and how a resource can be located.
        """

        if self.lockedResources.has_key( (resourceType, resourceName) ):
            (host,port, sisterPerspective)= self.lockedResources[(resourceType, resourceName)]
            return defer.succeed( (None, host, port, sisterPerspective) )
                                  
        log.msg( 'parent: loading resource (%s)'  % self.sisters)
        if not self.sisters:
            defr = defer.Deferred()
            self.toLoadOnConnect.append((resourceType, resourceName, generateTicket, defr))
            return defr

        #TODO: better selection mechanism for sister server
        (host, port, sisterPerspective) = choice(self.sisters)
        
        return sisterPerspective.callRemote("loadResource", resourceType, resourceName, generateTicket
                                              ).addCallback(
            self._cbLoadedResource, resourceType, resourceName, host, port, sisterPerspective)

    def loadRemoteResourceFor(self, sisterPerspective, resourceType, resourceName, generateTicket):
        """Use to load a remote resource on a specified sister
        service. Dont load it if already loaded on a sister.
        """
        # lookup sister info in sisters
        found = 0
        host = None
        port = None
        sister = None
        for dhost, dport, dref in self.sisters:
            if dref == sisterPerspective:
                host = dhost
                port = dport
                sister = dref
                found = 1
                break

        if not found:
            raise ("Attempt to load resource for no-existent sister")

        if self.lockedResources.has_key( (resourceType, resourceName) ):
            raise ("resource %s:%s already loaded on a sister" % (resourceName, resourceType) )
        
        return sisterPerspective.callRemote("loadResource", resourceType, resourceName, generateTicket
                                              ).addCallback(
            self._cbLoadedResource, resourceType, resourceName, host, port, sisterPerspective)
        
    def perspective_unloadResource(self, resourceType, resourceName):
        """This is called by sister services to unload a resource
        """
        log.msg( "parent: unloading %s/%s" %( resourceType, resourceName ) )
        data = self.lockedResources.get( (resourceType, resourceName) )
        if not data:
            raise "Unable to unload not-loaded resource."
        (host, port, perspective) = data
        del self.lockedResources[ (resourceType, resourceName) ]

    def perspective_publishIP(self, host, port, clientRef):
        """called by sister to set the host and port to publish for clients.
        """
        log.msg( "sister attached: %s:%s" % (host, port ) )
        self.sisters.append((host, port,clientRef) )
        for resourceType, resourceName, generateTicket, deferred in self.toLoadOnConnect:
            self.loadRemoteResource(resourceType, resourceName, generateTicket).chainDeferred(deferred)
        self.toLoadOnConnect = []
            

    def detached(self, client, identity):
        for path, (host, port, clientRef) in self.lockedResources.items():
            if client == clientRef:
                del self.lockedResources[path]
        log.msg( "sister detached: %s" % client)
        return Perspective.detached(self, client, identity)
        
    def _cbLoaded(self, ignored, path):
        d, host, port = self.pendingResources[path]
        del self.pendingResources[path]
        self.lockedResources[path] = (host, port)
        d.callback((host, port))
        
    def _ebLoaded(self, error, path):
        d, host, port = self.pendingResources[path]
        del self.pendingResources[path]
        d.errback(error)

