
# Twisted, the Framework of Your Internet
# Copyright (C) 2001 Matthew W. Lefkowitz
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of version 2.1 of the GNU Lesser General Public
# License as published by the Free Software Foundation.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

"""DEPRECATED.

Base authentication mechanisms for Twisted.

Maintainer: U{Glyph Lefkowitz<mailto:glyph@twistedmatrix.com>}

Stability: semi-stable

Future Plans: There needs to be more pluggable support for different, disparate
authentication mechanisms being supported by the same Identity as long as it
supports the appropriate persistent data-storage fields.  This will likely be
accomplished with Adapters and possibly Componentized, although it may just be
the addition of more methods in the base Identity.

"""

# System Imports
import md5, types, sys, warnings

# Twisted Imports
from twisted.python import failure
from twisted.internet import defer

# Sibling Imports
from util import respond
from util import challenge
from error import Unauthorized, KeyNotFound


class Identity:
    """An identity, with different methods for verification.

    An identity represents a user's permissions with a particular
    application.  It is a username, a password, and a collection of
    Perspective/Service name pairs, each of which is a perspective
    that this identity is allowed to access.
    """
    hashedPassword = None

    def __init__(self, name, authorizer):
        """Create an identity.

        I must have a name, and a backreference to the Application that the
        Keys on my keyring make reference to.
        """
        warnings.warn("Identities are deprecated, switch to credentialcheckers etc.",
                      category=DeprecationWarning, stacklevel=2)
        if not isinstance(name, types.StringType):
            raise TypeError
        from twisted.internet import app
        if isinstance(authorizer, app.Application):
            authorizer = authorizer.authorizer
        self.name = name
        self.authorizer = authorizer
        self.keyring = {}

    def upgradeToVersion2(self):
        self.authorizer = self.application.authorizer
        del self.application

    def addKeyForPerspective(self, perspective):
        """Add a key for the given perspective.
        """
        perspectiveName = perspective.getPerspectiveName()
        serviceName = perspective.service.getServiceName()
        self.addKeyByString(serviceName, perspectiveName)

    def addKeyByString(self, serviceName, perspectiveName):
        """Put a key on my keyring.

        This key will give me a token to access to some service in the
        future.
        """
        self.keyring[(serviceName, perspectiveName)] = 1

    def requestPerspectiveForService(self, serviceName):
        """Get the first available perspective for a given service.
        """
        keys = self.keyring.keys()
        keys.sort()
        for serviceN, perspectiveN in keys:
            if serviceN == serviceName:
                return self.requestPerspectiveForKey(serviceName, perspectiveN)
        return defer.fail("No such perspective.")

    def requestPerspectiveForKey(self, serviceName, perspectiveName):
        """Get a perspective request (a Deferred) for the given key.

        If this identity does not have access to the given C{(serviceName,
        perspectiveName)} pair, I will raise L{KeyNotFound<error.KeyNotFound>}.
        """
        try:
            check = self.keyring[(serviceName, perspectiveName)]
        except KeyError:
            e = KeyNotFound(serviceName, perspectiveName)
            return defer.fail(failure.Failure(e, KeyNotFound,
                                              sys.exc_info()[2]))
        return self.authorizer.getServiceNamed(serviceName).getPerspectiveForIdentity(perspectiveName, self)

    def getAllKeys(self):
        """Returns a list of all services and perspectives this identity can connect to.

        This returns a sequence of keys.
        """
        return self.keyring.keys()

    def removeKey(self, serviceName, perspectiveName):
        """Remove a key from my keyring.

        If this key is not present, raise KeyError.
        """
        del self.keyring[(serviceName, perspectiveName)]

    def save(self):
        """Persist this Identity to the authorizer.
        """
        return self.authorizer.addIdentity(self)

    ### Authentication Mechanisms

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

        This is a method in addition to the module-level function
        because it is anticipated that we will want to change this
        to store salted passwords.
        """
        return challenge()

    def verifyPassword(self, challenge, hashedPassword):
        """Verify a challenge/response password.
        """
        req = defer.Deferred()
        if self.hashedPassword is None:
            # no password was set, so we can't log in
            req.errback(Unauthorized("account is disabled"))
            return req
        md = md5.new()
        md.update(self.hashedPassword)
        md.update(challenge)
        correct = md.digest()
        if hashedPassword == correct:
            req.callback("password verified")
        else:
            req.errback(Unauthorized("incorrect password"))
        return req

    def verifyPlainPassword(self, plaintext):
        """Verify plain text password.

        This is insecure, but necessary to support legacy protocols such
        as IRC, POP3, HTTP, etc.
        """
        req = defer.Deferred()
        if self.hashedPassword is None:
            # no password was set, so we can't log in
            req.errback(Unauthorized("account is disabled"))
            return req
        md = md5.new()
        md.update(plaintext)
        userPass = md.digest()
        if userPass == self.hashedPassword:
            req.callback("password verified")
        else:
            req.errback(Unauthorized("incorrect password"))
        return req

    def __repr__(self):
        return "<%s %r at 0x%x>" % (self.__class__, self.name, id(self))


    # TODO: service discovery through listing of self.keyring.
