
# Sibling Server

from twisted.spread.pb import Service, Perspective, Error
from twisted.spread.flavors import Referenceable
from twisted.spread.refpath import PathReferenceDirectory


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
        self.lockedResources = {}       # path: host, port
        self.daughters = []             # [(host, port, reference)]
        self.makeIdentity(sharedSecret)

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
            print ("%s didn't accept %s and %s" % (method, args, kw))
            raise
        return broker.serialize(state, self.perspective)

    def brokerAttached(self, cli, ident, broker):
        print 'beep', self.daughters
        port, ref = cli
        host = broker.transport.getPeer()[1]
        self.daughters.append((host, port, ref))
        print 'sister attached', (host, port, ref)
        return self

    def brokerDetached(self, cli, ident, broker):
        port, ref = cli
        host = broker.transport.getPeer()[1]
        self.daughters.remove((host, port, ref))
        for path, (lhost, lport) in self.lockedResources.items():
            if (host, port) == (lhost, lport):
                # XXX do i need some kind of notification here?
                del self.lockedResources[path]
        print 'sister detached', (host, port, ref)
        return self

    def perspective_lockResource(self, broker, port, path):
        """Lock a resource.

        First, I attempt to locate the resource.  If I locate it, I will return
        its location in the form of a 3-tuple: (host, port, path).  A remote
        reference representing that resource may then be retrieved by doing::

            from twisted.spread import pb, refpath
            pb.connect(host, port, 'sister', secret,
                       'twisted.sister').addCallback(
                       refpath.RemotePathReference, path)


        If I do not locate the resource's location immediately, I will ask a
        low-load server to own the object, and then return the location where I
        sent it.

        """

        host = broker.transport.getPeer()[1]      # getPeer is ('INET', host, port)
        # (keep in mind that the 'port' in getPeer is not the port number I
        # want; it's the port that the client has allocated)
        if self.lockedResources.has_key(path):
            return self.lockedResources[path]
        elif self.pendingResources.has_key(path):
            d = defer.Deferred()
            self.pendingResources[path][0].chainDeferred(d)
            # this contortion is necessary because each deferred returned from
            # a remote method is armed and thus cannot have further callbacks
            # added (e.g. be returned again)
            return d
        else:
            # try to locate a sister server who can host this resource
            for dhost, dport, dref in self.daughters:
                if host == dhost and port == dport:
                    d = defer.Deferred()
                    self.pendingResources[path] = d, host, port
                    return dref.callRemote("loadResource", path
                                           ).addCallbacks(
                        self._cbLoaded,
                        self._ebLoaded,
                        callbackArgs=(path,),
                        errbackArgs=(path,)
                        )
            else:
                raise Error("Unable to locate requesting client...")


    def _cbLoaded(self, ignored, path):
        d, host, port = self.pendingResources[path]
        del self.pendingResources[path]
        self.lockedResources[path] = (host, port)
        d.armAndCallback((host, port))
    def _ebLoaded(self, error, path):
        d, host, port = self.pendingResources[path]
        del self.pendingResources[path]
        d.armAndErrback(error)

