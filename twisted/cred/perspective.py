
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

from twisted.python import log

class Perspective:
    """I am an Identity's view onto a service.

    I am the interface through which most 'external' code should
    interact with a service; I represent the actions a user may
    perform upon a service, and the state associated with that
    user for that service.
    """

    _service_cached = 0 # Has my service cached me from a loaded store, or do I live in memory usually?

    def __init__(self, perspectiveName, identityName="Nobody"):
        """Create me.

        I require a name for myself and a reference to the service
        I participate in.  (My identity name will be 'Nobody' by
        default, which will normally not resolve.)
        """
        self.perspectiveName = perspectiveName
        self.identityName = identityName

    def setIdentityName(self, name):
        self.identityName = name

    def setIdentity(self, identity):
        """Determine which identity I connect to.
        """
        self.setIdentityName(identity.name)

    def makeIdentity(self, password):
        """Make an identity from this perspective with a password.

        This is a utility method, which can be used in circumstances
        where the distinction between Perspective and Identity is weak,
        such as single-Service servers.
        """
        ident = Identity(self.perspectiveName, self.service.application)
        self.setIdentityName(self.perspectiveName)
        ident.setPassword(password)
        ident.addKeyForPerspective(self)
        self.service.application.authorizer.addIdentity(ident)
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

    def getIdentityRequest(self):
        """Request my identity.
        """
        return (self.service.application.authorizer.
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
        log.msg('attached [%s]' % str(self.__class__))
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
        log.msg('detached [%s]' % str(self.__class__))
        self._attachedCount = self._attachedCount - 1
        if self._attachedCount <= 0:
            self.service.uncachePerspective(self)
            if self._attachedCount < 0:
                log.msg(" (Weird stuff: attached count = %s)" % self._attachedCount)
        else:
            log.msg(" (multiple references attached: %s)" % self._attachedCount)
        return self
