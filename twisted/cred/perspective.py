# -*- test-case-name: twisted.test.test_cred -*-
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

"""
This module is for domain-specific representations of users.

Stability: semi-stable

Future Plans: Errors may be changed to unify reporting in twisted.cred.

"""

from twisted.python import log, reflect, components
from twisted.cred import identity
import types

class IPerspective(components.Interface):
    def setIdentityName(self, name):
        """"""
    
    def setIdentity(self, identity):
        """"""
    
    def makeIdentity(self, password):
        """"""
    
    def getPerspectiveName(self):
        """"""
    
    def getService(self):
        """"""
    
    def setService(self, service):
        """"""
    
    def getIdentityRequest(self):
        """"""
    
    def attached(self, reference, identity):
        """"""
    
    def detached(self, reference, identity):
        """"""
    
    def setCached(self):
        """"""
    
    def isCached(self):
        """"""

class Perspective:
    """I am an Identity's view onto a service.

    I am the interface through which most 'external' code should
    interact with a service; I represent the actions a user may
    perform upon a service, and the state associated with that
    user for that service.
    """
    
    __implements__ = IPerspective,

    _service_cached = 0 # Has my service cached me from a loaded store, or do I live in memory usually?

    def __init__(self, perspectiveName, identityName="Nobody"):
        """Create me.

        I require a name for myself and a reference to the service
        I participate in.  (My identity name will be 'Nobody' by
        default, which will normally not resolve.)
        """
        if not isinstance(perspectiveName, types.StringType):
            raise TypeError("Expected string, got %s."% perspectiveName)
        if not isinstance(identityName, types.StringType):
            raise TypeError("Expected string, got %s."% identityName)
        self.perspectiveName = perspectiveName
        self.identityName = identityName

    def setIdentityName(self, name):
        if not isinstance(name, types.StringType):
            raise TypeError
        self.identityName = name

    def setIdentity(self, ident):
        """Determine which identity I connect to.
        """
        if not isinstance(ident, identity.Identity):
            raise TypeError
        self.setIdentityName(ident.name)

    def makeIdentity(self, password):
        """Make an identity from this perspective with a password.

        This is a utility method, which can be used in circumstances
        where the distinction between Perspective and Identity is weak,
        such as single-Service servers.
        """
        if not isinstance(password, types.StringType):
            raise TypeError
        ident = self.service.authorizer.createIdentity(self.perspectiveName)
        # ident = identity.Identity(self.perspectiveName, self.service.application)
        self.setIdentity(ident)
        ident.setPassword(password)
        ident.addKeyForPerspective(self)
        ident.save()
        return ident

    def getPerspectiveName(self):
        """Return the unique name of this perspective.

        This will return a value such that
        self.service.getPerspectiveNamed(value) is self.

        (XXX: That's assuming I have been addPerspective'd to my service.)
        """
        return self.perspectiveName

    def getService(self):
        """Return a service.
        """
        return self.service

    def setService(self, service):
        """Change what service I am a part of.
        """
        self.service = service
    
    def setCached(self):
        self._service_cached = 1
    
    def isCached(self):
        return self._service_cached

    def getIdentityRequest(self):
        """Request my identity.
        """
        return (self.service.authorizer.
                getIdentityRequest(self.identityName))

    _attachedCount = 0

    def attached(self, reference, identity):
        """Called when a remote reference is 'attached' to me.

        After being authorized, a remote actor can attach to me
        through its identity.  This call will be made when that
        happens, and the return value of this method will be used
        as the _actual_ perspective to which I am attached.

        Note that the symmetric call, detached, will be made on
        whatever this method returns, _not_ on me.  Therefore,
        by default I return 'self'.
        """
        log.msg('attached [%s]' % reflect.qual(self.__class__))
        self._attachedCount = self._attachedCount + 1
        if self._attachedCount == 1:
            self.service.cachePerspective(self)
        else:
            log.msg(" (multiple references attached: %s)" % self._attachedCount)
        return self

    def detached(self, reference, identity):
        """Called when a broker is 'detached' from me.

        See 'attached'.

        When a remote actor disconnects (or times out, for example,
        with HTTP), this is called in order to indicate that the
        reference associated with that peer is no longer attached to
        this perspective.
        """
        log.msg('detached [%s]' % reflect.qual(self.__class__))
        self._attachedCount = self._attachedCount - 1
        if self._attachedCount <= 0:
            self.service.uncachePerspective(self)
            if self._attachedCount < 0:
                log.msg(" (Weird stuff: attached count = %s)" % self._attachedCount)
        else:
            log.msg(" (multiple references attached: %s)" % self._attachedCount)
        return self
