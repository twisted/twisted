"""Authorization & authentication in Twisted.
"""

# System Imports
import md5
import random

# Twisted Imports
from twisted.python import defer

class Unauthorized(Exception):
    """An exception that is raised when unauthorized actions are attempted.
    """

class Key:
    """A key to a Perspective linked through an Identity.

    I can 'unlock' a particular service for an Identity, because I represent a
    perspective with that service.  Keys are the way that Perspectives are
    attached to an Identity.
    """
    def __init__(self, service, perspective, identity):
        """(internal) Construct a key.

        This is usually done inside Identity.setKey.  
        """
        self.service = service
        self.identity = identity
        self.perspective = perspective

    def getPerspective(self):
        """Get the perspective that I am a key to.

        This should only be done _after_ authentication!  I retrieve
        identity.application[service][perspective].
        """
        app = self.identity.application
        svc = app.getService(self.service)
        psp = svc.getPerspectiveNamed(self.perspective)
        return psp

class Service:
    """I am a service that internet applications interact with.

    I represent a set of abstractions which users may interact with over a
    specified protocol.

    (See Also: twisted.spread.pb.Service)
    """

    application = None
    
    def __init__(self, serviceName, application=None):
        """Create me, attached to the given application.

        Arguments: application, a twisted.internet.main.Application instance.
        """
        self.serviceName = serviceName
        self.perspectives = {}
        self.setApplication(application)

    def setApplication(self, application):
        assert not self.application, "Application already set!"
        if application:
            self.application = application
            application.addService(self)

    def addPerspective(self, perspective):
        """Add a perspective to this Service.

        perspective's perspectiveName, 
        """
        self.perspectives[perspective.getPerspectiveName()] = perspective
    
    def getPerspectiveNamed(self, name):
        """Return a perspective that represents a user for this service.

        Raises a KeyError if no such user exists.  Override this method to
        provide dynamic instantiation of perspectives.
        """
        return self.perspectives[name]

    def getServiceName(self):
        """The name of this service.
        """
        return self.serviceName


class Perspective:
    """I am an Identity's view onto a service.

    I am the interface through which most 'external' code should interact with
    a service; I represent the actions a user may perform upon a service, and
    the state associated with that user for that service.
    """
    def __init__(self, perspectiveName, service, identityName="Nobody"):
        """Create me.

        I require a name for myself and a reference to the service I
        participate in.  (My identity name will be 'Nobody' by default, which
        will normally not resolve.)
        """
        self.perspectiveName = perspectiveName
        self.service = service
        self.identityName = identityName

    def setIdentityName(self, name):
        self.identityName = name

    def setIdentity(self, identity):
        """Determine which identity I connect to.
        """
        self.setIdentityName(identity.name)

    def getPerspectiveName(self):
        """Return the unique name of this perspective.

        This will return a value such that
        self.service.getPerspectiveNamed(value) is self.
        """
        return self.perspectiveName

    def getService(self):
        """Return a service.
        """
        return self.service

    def getIdentityRequest(self):
        """Request my identity.
        """
        return (self.service.application.authorizer.
                getIdentityRequest(self.identityName))


def respond(challenge, password):
    """Respond to a challenge.
    This is useful for challenge/response authentication.
    """
    m = md5.new()
    m.update(password)
    hashedPassword = m.digest()
    m = md5.new()
    m.update(hashedPassword)
    m.update(challenge)
    doubleHashedPassword = m.digest()
    return doubleHashedPassword


class Identity:
    """An identity, with different methods for verification.
    
    """
    hashedPassword = None

    def __init__(self, name, application):
        """Create an identity.

        I must have a name, and a backreference to the Application that the
        Keys on my keyring make reference to.
        """
        self.name = name
        self.application = application
        self.keyring = {}

    def getKey(self, serviceName):
        """Get a key from my keyring.

        If that key does not exist, raise Unauthorized.  This will return an
        instance of a Key.
        """
        if not self.keyring.has_key(serviceName):
            raise Unauthorized("You have no key for %s." % serviceName)
        return self.keyring[serviceName]

    def addKeyFor(self, perspective):
        """Add a key for the given perspective.
        """
        perspectiveName = perspective.getPerspectiveName()
        serviceName = perspective.service.getServiceName()
        self.setKey(serviceName, perspectiveName)
    
    def setKey(self, serviceName, perspectiveName):
        """Set a key on my keyring.

        This key will give me a token to access to some service in the future.
        """
        self.keyring[serviceName] = Key(serviceName, perspectiveName, self)

    def removeKey(self, serviceName):
        """Remove a key from my keyring.

        If this key is not present, raise Unauthorized.
        """
        if not self.keyring.has_key(serviceName):
            raise Unauthorized("You cannot remove the key %s." % serviceName)
        del self.keyring[serviceName]

    def setPassword(self, plaintext):
        if plaintext is None:
            self.hashedPassword = None
        else:
            self.hashedPassword = md5.new(plaintext).digest()

    def setAlreadyHashedPassword(self, cyphertext):
        """(legacy) Set a password for this identity, already md5 hashed.
        """
        self.hashedPassword = cyphertext

    def challenge(self):
        """I return some random data.

        This is a method rather than a module-level function because it is
        anticipated that we will want to change this to store salted passwords.
        """
        crap = ''
        for x in range(random.randrange(15,25)):
            crap = crap + chr(random.randint(65,90))
        crap = md5.new(crap).digest()
        crap = 'hi'
        return crap

    def verifyPassword(self, challenge, hashedPassword):
        """Verify a challenge/response password.
        """
        md = md5.new()
        md.update(self.hashedPassword)
        md.update(challenge)
        correct = md.digest()
        result = (hashedPassword == correct)
        return result

    def verifyPlainPassword(self, plaintext):
        """Verify plain text password.

        This is insecure, but necessary to support legacy protocols such as
        IRC, POP3, HTTP, etc.
        """
        md = md5.new()
        md.update(plaintext)
        userPass = md.digest()
        return (userPass == self.hashedPassword)



class Authorizer:
    """An interface to a set of identities.
    """
    def addIdentity(self, identity):
        """Create an identity and make a callback when it has been created.
        """
        raise NotImplementedError()

    def getIdentityRequest(self, name):
        """Request an identity, and make the given callback when it's received.

        Override this to provide a method for retrieving identities than the
        hash provided by default.

        Note that this is asynchronous specifically to provide support for
        authenticating users from a database.
        """
        raise NotImplementedError("twisted.internet.passport.Authorizer.requestIdentity")


class DefaultAuthorizer(Authorizer):
    
    """I am an authorizer which requires no external dependencies.

    I am implemented as a hash of Identities.
    """
    def __init__(self):
        """Create a hash of identities.
        """
        self.identities = {}

    def addIdentity(self, identity):
        """Add an identity to me.
        """
        if self.identities.has_key(identity.name):
            raise KeyError("Already have an identity by that name.")
        self.identities[identity.name] = identity

    def getIdentityRequest(self, name):
        """Get a Deferred callback registration object.

        I return a deferred (twisted.python.defer.Deferred) which will be
        called back to when an identity is discovered to be available (or
        errback for unavailable).  It will be returned unarmed, so you must arm
        it yourself.
        """
        req = defer.Deferred()
        if self.identities.has_key(name):
            req.callback(self.identities[name])
        else:
            req.errback("unauthorized")
        return req
