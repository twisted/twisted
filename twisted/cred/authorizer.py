# -*- test-case-name: twisted.test.test_cred -*-
# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.


"""DEPRECATED.

Container for authorization objects.

Maintainer: U{Glyph Lefkowitz<mailto:glyph@twistedmatrix.com>}

Stability: semi-stable

"""

# System imports
import warnings

# Twisted Imports
from twisted.internet import defer
from twisted.python.reflect import Accessor, qual

# Sibling Imports
from twisted.cred import identity, error


class Authorizer(Accessor):
    """An interface to a set of identities.

    @type identityClass:          L{identity.Identity}
    @cvar identityClass:          The type of Identity that is created
                                  and managed by this authorizer.
    @type serviceCollection:      L{_AbstractServiceCollection<twisted.internet.app._AbstractServiceCollection>}
    @ivar serviceCollection:      The set of services that are using this authorizer.
    """

    def __init__(self, serviceCollection=None):
        warnings.warn("Authorizers are deprecated, switch to portals/realms/etc.",
                      category=DeprecationWarning, stacklevel=2)
        self.serviceCollection = serviceCollection

    def get_application(self):
        warnings.warn("Authorizer.application attribute is deprecated.",
                      category=DeprecationWarning, stacklevel=3)
        return self.serviceCollection

    def setApplication(self, app):
        """Set the application for this authorizer. DEPRECATED.
        """
        warnings.warn("setApplication is deprecated, use setServiceCollection instead.",
                      category=DeprecationWarning, stacklevel=3)
        self.serviceCollection = app

    def setServiceCollection(self, collection):
        """Set the service collection for this authorizer."""
        self.serviceCollection = collection

    identityClass = identity.Identity

    def createIdentity(self, name):
        """Create an identity of an appropriate type for this Authorizer.

        This identity will not be saved!  You must call its .save() method
        before it will be recognized by this authorizer.
        """
        return self.identityClass(name, self)

    def addIdentity(self, identity):
        """Create an identity and make a callback when it has been created.

        @raises error.DuplicateIdentity: There is already an identity by
            this name.
        """
        raise NotImplementedError()

    def removeIdentity(self, identityName):
        raise NotImplementedError()

    def getIdentityRequest(self, name):
        """Get an identity request, make the given callback when it's received.

        Override this to provide a method for retrieving identities than
        the hash provided by default. The method should return a Deferred.

        Note that this is asynchronous specifically to provide support
        for authenticating users from a database.
        """
        raise NotImplementedError("%s.getIdentityRequest"%qual(self.__class__))

    def getServiceNamed(self, name):
        return self.serviceCollection.getServiceNamed(name)


class DefaultAuthorizer(Authorizer):
    """I am an authorizer which requires no external dependencies.

    I am implemented as a hash of Identities.
    """

    def __init__(self, serviceCollection=None):
        """Create a hash of identities.
        """
        Authorizer.__init__(self, serviceCollection)
        self.identities = {}

    def addIdentity(self, identity):
        """Add an identity to me.
        """
        if self.identities.has_key(identity.name):
            #? return defer.fail(error.DuplicateIdentity(identity.name))
            raise error.DuplicateIdentity(identity.name)
        self.identities[identity.name] = identity
        #? return defer.succeed(None)

    def removeIdentity(self, identityName):
        del self.identities[identityName]

    def getIdentityRequest(self, name):
        """Get a Deferred callback registration object.

        I return a L{deferred<twisted.internet.defer.Deferred>} which will
        be called back to when an identity is discovered to be available
        (or errback for unavailable).
        """

        req = defer.Deferred()
        if self.identities.has_key(name):
            req.callback(self.identities[name])
        else:
            req.errback(error.Unauthorized("unauthorized"))
        return req
