# -*- test-case-name: twisted.test.test_sister -*-

# Sibling Server

from twisted.spread.pb import Service, Perspective, Error
from twisted.spread.flavors import Referenceable
from twisted.spread.refpath import PathReferenceDirectory
from twisted.internet import defer
from twisted.python import log

from random import choice
        
class MotherService(Service, Perspective):
    """A `mother' object, managing many sister-servers.

    I maintain a list of all "sister" servers who are connected, so that all
    servers can connect to each other.  I also negotiate which distributed
    objects are owned by which sister servers, so that if any sister-server
    needs to locate an object it can be made available.
    """

    def __init__(self, sharedSecret, serviceName, application=None):
        Service.__init__(self, serviceName, application)
        Perspective.__init__(self, "mother")
        self.addPerspective(self)
        # Three states: unlocked, pending lock, locked
        self.pendingResources = {}      # path: deferred, host, port
        self.toLoadOnConnect = []       # [deferred, deferred, ...]
        self.lockedResources = {}       # path: host, port
        self.sisters = []             # [(host, port, reference)]
        self.makeIdentity(sharedSecret)
        
    def _cbLoadedResource(self, result, resourceType, resourceName, host, port, sisterPerspective):
        log.msg( 'mother: loaded resource')
        self.lockedResources[(resourceType, resourceName)] = (host, port, sisterPerspective)
        return (result, host, port, sisterPerspective)

    def loadRemoteResource(self, resourceType, resourceName, *args):
        """Request a sister-server to load a resource.

        Return a Deferred which will fire with (data, host, port, sister), that will
        describe where and how a resource can be located.
        """

        if self.lockedResources.has_key( (resourceType, resourceName) ):
            (host,port, sisterPerspective)= self.lockedResources[(resourceType, resourceName)]
            return defer.succeed( (None, host, port, sisterPerspective) )
                                  
        log.msg( 'mother: loading resource (%s)'  % self.sisters)
        if not self.sisters:
            defr = defer.Deferred()
            self.toLoadOnConnect.append((resourceType, resourceName, args, defr))
            return defr

        #TODO: better selection mechanism for sister server
        (host, port, sisterPerspective) = choice(self.sisters)
        
        d = apply( sisterPerspective.callRemote, ("loadResource", resourceType, resourceName) + args )
        d.addCallback(self._cbLoadedResource, resourceType, resourceName, host, port, sisterPerspective)
        return d

    def loadRemoteResourceFor(self, sisterPerspective, resourceType, resourceName, *args):
        """Use to load a remote resource on a specified sister
        service. Dont load it if already loaded on a sister.
        """
        # lookup sister info in sisters
        found = 0
        for host, port, sister in self.sisters:
            if sister == sisterPerspective:
                found = 1
                break

        if not found:
            raise ("Attempt to load resource <%s:%s> for no-nexistent sister" % (resourceType, resourceName) )

        if self.lockedResources.has_key( (resourceType, resourceName) ):
            raise ("resource %s:%s already loaded on a sister" % (resourceName, resourceType) )
        
        d = apply( sisterPerspective.callRemote, ("loadResource", resourceType, resourceName) + args )
        d.addCallback(self._cbLoadedResource, resourceType, resourceName, host, port, sisterPerspective)
        return d
    
    def perspective_unloadResource(self, resourceType, resourceName):
        """This is called by sister services to unload a resource
        """
        log.msg( "mother: unloading %s/%s" %( resourceType, resourceName ) )
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
        for resourceType, resourceName, args, deferred in self.toLoadOnConnect:
            apply(self.loadRemoteResource, (resourceType, resourceName) + args).chainDeferred(deferred)
        self.toLoadOnConnect = []

    def perspective_callDistributed(self, srcResourceType, srcResourceName, destResourceType, destResourceName, methodName, *args, **kw):
        """Call a remote method on a resources that is managed by the system.
        """
        data = self.lockedResources.get( (destResourceType, destResourceName) )
        if not data:
            raise "Unable to find not-loaded resource."
        (host, port, perspective) = data
        log.msg( "Calling distributed method <%s> for %s:%s" % (methodName, destResourceType, destResourceName))
        return perspective.callRemote('callDistributed', srcResourceType, srcResourceName, destResourceType, destResourceName, methodName, args, kw)
        
    def detached(self, client, identity):
        for path, (host, port, clientRef) in self.lockedResources.items():
            if client == clientRef:
                del self.lockedResources[path]
        log.msg( "sister detached: %s" % client)
        return Perspective.detached(self, client, identity)

