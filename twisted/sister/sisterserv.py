# -*- test-case-name: twisted.test.test_sister -*-
import copy

from twisted.spread.pb import Service, Perspective, Error
from twisted.spread.sturdy import PerspectiveConnector
from twisted.spread.flavors import Referenceable
from twisted.spread.refpath import PathReferenceDirectory

from twisted.python import defer, log
from twisted.python.failure import Failure
from twisted.cred.util import challenge

from twisted.cred.authorizer import DefaultAuthorizer
from twisted.cred.identity import Identity

class TicketPerspective(Perspective):
    def __init__(self, name, realPerspective, ticketAuth):
        Perspective.__init__(self, name, name)
        self.realPerspective = realPerspective
        self.ticketAuth = ticketAuth
    def attached(self, reference, identity):
        self.ticketAuth.application.authorizer.removeIdentity(self.identityName)
        return self.realPerspective.attached(reference, identity)

class TicketAuthorizer(DefaultAuthorizer):
    def addTicket(self, realPerspective):
        ticket = challenge()
        ticketPerspective = TicketPerspective(ticket, realPerspective, self)
        self.sisterService.ticketService.addPerspective(ticketPerspective)
        ticketPerspective.makeIdentity(ticket)
        return ticket

True = 1
False = 0


class SisterParentClient(Referenceable):
    def __init__(self, sistersrv):
        self.sistersrv = sistersrv

    def remote_loadResource(self, resourceType, resourceName, generateTicket):
        return self.sistersrv.loadResource(resourceType, resourceName, generateTicket)

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

        (Application's authorizer must be a TicketAuthorizer, otherwise
        login won't work.)
        """
        Service.__init__(self, serviceName, application)
        Perspective.__init__(self, "sister")
        self.ticketService = Service(serviceName + "-ticket", application)
        self.addPerspective(self)
        self.ownedResources = {}
        self.remoteResources = {}
        self.resourceLoaders = {}
        self.localPort = localPort
        self.parentRef = PerspectiveConnector(
            parentHost, parentPort, "parent", sharedSecret, parentService,
            client=(localPort, SisterParentClient(self)))
        self.makeIdentity(sharedSecret)
        self.application.authorizer.sisterService = self

    def startService(self):
        log.msg( 'starting sister, woo')
        self.parentRef.startConnecting()

    def __getstate__(self):
        d = copy.copy(self.__dict__)
        d['ownedResources'] = {}
        d['remoteResources'] = {}
        return d

    # XXX I know what these mean, don't delete them -glyph
    def _cbLocked(self, result, path):
        if result is None:
            obj = apply(func, args, kw)
            self.ownedResources[path] = obj
            return (True, obj)
        else:
            self.remoteResources[path] = result
            return (False, result)

    def _ebLocked(self, error, path):
        log.msg('not locked, panicking')
        raise error

    # OK now on to the real code

    def ownResource(self, resourceObject, resourceType, resourceName):
        log.msg('sister: owning resource %s/%s' % (resourceType, resourceName))
        self.ownedResources[resourceType, resourceName] = resourceObject
        return resourceObject

    def loadResource(self, resourceType, resourceName, generateTicket):
        """Returns a Deferred which may yield a ticket.

        If generateTicket is True, this will yield a ticket, otherwise, it
        yields None.
        """
        log.msg( 'sister: loading resource %s/%s' %(resourceType, resourceName))
        value = self.resourceLoaders[resourceType](resourceName)
        if isinstance(value, defer.Deferred):
            dvalue = value
        else:
            dvalue = defer.succeed(value)
        dvalue.addCallback(self.ownResource, resourceType, resourceName)
        if generateTicket:
            dvalue.addCallback(self.application.authorizer.addTicket)
        return dvalue

    def registerResourceLoader(self, resourceType, resourceLoader):
        """Register a callable object to generate resources.

        The callable object may return Deferreds or synchronous values.
        """
        log.msg( 'sister: registering resource loader %s:%s' % (resourceType, repr(resourceLoader)))
        self.resourceLoaders[resourceType] = resourceLoader
