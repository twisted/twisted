# -*- test-case-name: twisted.test.test_sibling -*-

"""Login service for Twisted.Sibling.
"""

# Standard Imports

# Twisted Imports
from twisted.spread import pb
from twisted.internet import defer
from twisted.python import log
from twisted.enterprise import row

class LoginService(pb.Service):

    """The Sibling Login service.  This service knows how to load
    clients.  The login sequence for a client is:
      - client connects to login service
      - login service loads their identity/perspective
      - mother service remoteloads the identity on the sibling and returns a ticket
      - login service passes ticket down to client
      - player connects to sibling service with ticket
      - player disconnects from login service

    later on:
      - client disconnects from sibling service
      - sibling tells mother to unload the client identity

    This service should run in the same process as a twisted.mother
    service. The mother service handles logins from siblings while this
    LoginService handles logins from clients.

    This service enforces a single simultaneous login per-identity.

    """

    def __init__(self, name, application, motherService):
        self.motherService = motherService
        pb.Service.__init__(self, name, application)

    def getPerspectiveForIdentity(self, name, identity):
        """Fail if the player is already on-line.
        """
        try:
            p = self.getPerspectiveNamed(name)
        except KeyError:
            if self.motherService.lockedResources.has_key(("identity", name)):
                return defer.fail("Client %s is already on-line" % name)

            ## This deferred should yield a perspective instance
            return self.loadLoginPerspective(name, identity).addCallback(self._cbPerspective)

        return defer.fail("Client %s is already on-line" % name)

    def _cbPerspective(self, perspective):
        self.cachePerspective(perspective)
        return perspective

    def loadLoginPerspective(self, name, identity):
        """This must return a deferred that yields a perspective object.
        Within this block, loadIdentityForSibling should be called. This block
        of functionality is broken out like this so that the decision as to
        which sibling to load the perspective on can be deferred, as well as
        the loading of the perspective itself being deferred.

        example::

            def loadLoginPerspective(self, name, identity):
                d1 = defer.Deferred()
                sibling = choice(self.motherService.siblings)
                d2 = self.loadIdentityForSibling(sibling, name, identity)
                d2.addCallback(self._cbTicket, name, d1)
                return d1

            def _cbTicket(self, data, name, d1):
                newPerspective = MyPerspective(name)
                p.setTicket(data)
                d1.callback(newPerspective)

        In the example, the choosing of sibling servers is not asychronous, but
        this framework allows it to be.
        """
        raise pb.Error("Not Implemented")


    def loadIdentityForSibling(self, sibling, name, identity):
        """Utility method for loading the remote identity
        once it is known which sibling the identity should be loaded
        on. Should be called from within the loadLoginPerspective block.

        This returns (ticket, host, port, sibling) which must be used
        by the client to login to the sibling server.

        """
        return self.motherService.loadRemoteResourceFor(sibling, "identity", name, identity.keyring.keys())
