

import copy

from twisted.spread.pb import Service, Perspective, Error
from twisted.spread.sturdy import PerspectiveConnector
from twisted.spread.flavors import Referenceable
from twisted.spread.refpath import PathReferenceDirectory

from twisted.python import defer
from twisted.python.failure import Failure

True = 1
False = 0


class SisterParentClient(Referenceable):
    def __init__(self, sistersrv):
        self.sistersrv = sistersrv

    def remote_loadResource(self, path):
        return self.sistersrv.loadResource(path)

class SisterService(Service, Perspective):
    """A `parent' object, managing many sister-servers.

    I maintain a list of all "sister" servers who are connected, so that all
    servers can connect to each other.  I also negotiate which distributed
    objects are owned by which sister servers, so that if any sister-server
    needs to locate an object it can be made available.
    """

    def __init__(self, parentHost, parentPort, parentService, localPort,
                 sharedSecret, serviceName="twisted.sister", application=None):
        """Initialize me.
        """
        Service.__init__(self, serviceName, application)
        Perspective.__init__(self, "sister")
        self.addPerspective(self)
        self.ownedResources = {}
        self.remoteResources = {}
        self.localPort = localPort
        self.parentRef = PerspectiveConnector(
            parentHost, parentPort, "parent", sharedSecret, parentService,
            client=(localPort, SisterParentClient(self)))
        self.makeIdentity(sharedSecret)

    def startService(self):
        print 'starting sister, woo'
        self.parentRef.callRemote("boink")

    def __getstate__(self):
        d = copy.copy(self.__dict__)
        d['ownedResources'] = {}
        d['remoteResources'] = {}
        return d

    def _cbLocked(self, result, path):
        if result is None:
            obj = apply(func, args, kw)
            self.ownedResources[path] = obj
            return (True, obj)
        else:
            self.remoteResources[path] = result
            return (False, result)

    def _ebLocked(self, error, path):
        print 'not locked, panicking'
        raise error

    def loadResource(self, path):
        """Load a resource on a path.

        If the server sends you this message, it means that as soon as this
        method completes (successfully), you must be ready to handle messages
        being sent to that resource.

        (Keep in mind that you do not need to run this method atomically; all
        remote methods may be postponed by returning a Deferred.)
        """
        if self.ownedResources.has_key(path):
            return self.ownedResources[path]
        else:
            resource = self.resourceLoaders[path[0]].load(path)
            self.ownedResources[path] = resource
            return resource

    def perspective_callPath(self, path, name, *args, **kw):
        if self.ownedResources.has_key(path):
            method = getattr(self.ownedResources[path], 'remote_'+name)
            return apply(method, args, kw)
        else:
            raise Error("I do not own this resource: %s" % repr(path))

    def registerResourceLoader(self, resourcePath, resourceLoader):
        """
        By convention, calls to loadResource 
        """
        self.resourceLoaders[resourcePath] = resourceLoader

    def lockResource(self, path):
        """Attempt to lock a resource.

        Arguments:

          * path: a tuple of strings, describing the path to the resource on my
            parent server.  For example, for a twisted.words chatroom of the
            name "foobar", this path would be ('twisted.words', 'groups',
            'foobar').  For a user of the name "joe", this path would be
            ('twisted.words', 'users', 'joe').

        Attempt to lock a resource accessible via a given path on my parent
        server, for some local activity.  This is useful in services which
        require 'ownership' of stateful objects with behavior that must be
        processed.

        Returns:

            A deferred which will fire when the resource has either been locked
            or determined to be locked on another server.  The result of this
            deferred will be a 2-tuple.  The first element of the tuple will be
            true if the resource was in fact locked, and the second element
            will be the local instance created by loadResource.

            If the resource was locked by another server, then the first
            element of the tuple will be false, and the second element will be
            a descriptor tuple of (host, portno) describing where we can go
            looking for said resource.

        """
        if self.ownedResources.has_key(path):
            return defer.succeed((True, self.ownedResources[path]))
        elif self.remoteResources.has_key(path):
            return defer.succeed((False, self.remoteResources[path]))
        else:
            return self.parentRef.callRemote(
                "lockResource", self.localPort, path
                ).addCallbacks(
                self._cbLocked, self._ebLocked,
                callbackArgs=(path,),errbackArgs=(path,))
