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
Twisted Cred Service
"""

# Twisted Imports
from twisted.python import log, components
from twisted.internet import defer, app

# Sibling Imports
from perspective import Perspective

# System Imports
import types
import warnings

class IService(components.Interface):
    """An authorized service for internet applications.
    """


class Service(app.ApplicationService):
    """I am a service that internet applications interact with.

    I represent a set of abstractions which users may interact with over a
    specified protocol.

    (See Also: twisted.spread.pb.Service)
    """

    __implements__ = IService

    # ugh, load order
    perspectiveClass = Perspective

    serviceType = None
    serviceName = None

    def __init__(self, serviceName, serviceParent=None, authorizer=None, application=None):
        """Create me, attached to the given application.

        Arguments: application, a twisted.internet.app.Application instance.
        """
        self.perspectives = {}
        if application:
            if serviceParent:
                raise Exception(
                    "'serviceParent' supercedes the 'application' argument"
                    " -- you may not supply both.  ('application' accepted"
                    "for backwards compatibility only.)")
            else:
                sp = application
        else:
            sp = serviceParent
        if not authorizer:
            if isinstance(sp, app.Application):
                warnings.warn("You have to pass an authorizer separately from an application now.",
                              category=DeprecationWarning, stacklevel=2)
                authorizer = sp.authorizer
        self.authorizer = authorizer
        app.ApplicationService.__init__(self, serviceName, serviceParent, application)

    def cachePerspective(self, perspective):
        """Cache a perspective loaded from an external data source.

        Perspectives that were 'loaded' from memory will not be uncached.
        """
        if self.perspectives.has_key(perspective.perspectiveName):
            return
        self.perspectives[perspective.perspectiveName] = perspective
        perspective._service_cached = 1

    def uncachePerspective(self, perspective):
        """Uncache a perspective loaded from an external data source.

        Perspectives that were 'loaded' from memory will not be uncached.
        """
        if self.perspectives.has_key(perspective.perspectiveName):
            if perspective._service_cached:
                del self.perspectives[perspective.perspectiveName]

    def createPerspective(self, name):
        """Create a perspective from self.perspectiveClass and add it to this service.
        """
        p = self.perspectiveClass(name)
        self.perspectives[name] = p
        p.setService(self)
        return p

    def addPerspective(self, perspective):
        """Add a perspective to this Service.
        """
        if not isinstance(perspective, Perspective):
            raise TypeError
        perspective.setService(self)
        self.perspectives[perspective.getPerspectiveName()] = perspective

    def getPerspectiveNamed(self, name):
        """Return a perspective that represents a user for this service. (DEPRECATED)

        Raises a KeyError if no such user exists.  Override this method to
        provide dynamic instantiation of perspectives.  It is only deprecated
        to call this method directly, not to override it; when you need to get
        a Perspective, call getPerspectiveRequest.
        """
        return self.perspectives[name]

    def loadPerspective(self, name):
        """Load a perspective from an external data-source.

        If no such data-source exists, return None.  Implement this if you want
        to load your perspectives from somewhere else (e.g. LDAP or a
        database).  It is not recommended to call this directly, since
        getPerspectiveRequest provides management of caching perspectives.
        """
        return defer.fail("No such perspective %s" % name)

    def getPerspectiveForIdentity(self, name, identity):
        """A hook to use if the identity is required when getting the perspective.
        """
        return self.getPerspectiveRequest(name)

    def getPerspectiveRequest(self, name):
        """Return a Deferred which is a request for a perspective on this service.
        """
        try:
            p = self.getPerspectiveNamed(name)
        except KeyError:
            return self.loadPerspective(name)
        else:
            return defer.succeed(p)

    def getServiceName(self):
        """The name of this service.
        """
        return self.serviceName or self.getServiceType()

    def getServiceType(self):
        """Get a string describing the type of this service.
        """
        return self.serviceType or str(self.__class__)
