# Twisted, the Framework of Your Internet
# Copyright (C) 2001-2003 Matthew W. Lefkowitz
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
#
"""Service architecture for Twisted

Services are arranged in a hierarchy. At the leafs of the hierarchy,
the services which actually interact with the outside world are started.
Services can be named or anonymous -- usually, they will be named if
there is need to access them through the hierarchy (from a parent or
a sibling).

API Stability: unstable

Maintainer: U{Moshe Zadka<mailto:moshez@twistedmatrix.com>}
"""

import os

from twisted.python import components
from twisted.internet import defer
from twisted.persisted import sob
from twisted.python.runtime import platformType


class IService(components.Interface):

    """
    A service.

    Run start-up and shut-down code at the appropriate times.

    @type name:            C{string}
    @ivar name:            The name of the service (or None)
    @type running:         C{boolean}
    @ivar running:         Whether the service is running.
    """

    def setName(self, name):
        """Set the name of the service.

        @type name: C{str}
        @raise L{RuntimeError}: Raised if the service already has a parent.
        """

    def setServiceParent(self, parent):
        """Set the parent of the service.

        @type name: C{IServiceCollection}
        @raise L{RuntimeError}: Raised if the service already has a parent
        or if the service has a name and the parent already has a child
        by that name.
        """

    def disownServiceParent(self):
        """Remove the parent of the service.

        @rtype: C{Deferred}
        @return: a deferred which is triggered when the service has
        finished shutting down. If shutting down is immediate,
        a value can be returned (usually, None).
        """

    def startService(self):
        """Start the the service."""

    def stopService(self):
        """Stop the the service.

        @rtype: C{Deferred}
        @return: a deferred which is triggered when the service has
        finished shutting down. If shutting down is immediate,
        a value can be returned (usually, None).
        """

    def privilegedStartService(self):
        """Do preparation work for starting the service.

        Here things which should be done before changing directory,
        root or shedding privileges are done."""


class Service:

    """
    Base class for services

    Most services should inherit from this class. It handles the
    book-keeping reponsibilities of starting and stopping, as well
    as not serializing this book-keeping information.
    """

    __implements__ = IService,

    running = 0
    name = None
    parent = None

    def __getstate__(self):
        dict = self.__dict__.copy()
        if dict.has_key("running"):
            del dict['running']
        return dict

    def setName(self, name):
        if self.parent is not None:
            raise RuntimeError("cannot change name when parent exists")
        self.name = name

    def setServiceParent(self, parent):
        if self.parent is not None:
            self.disownServiceParent()
        parent = IServiceCollection(parent, parent)
        self.parent = parent
        self.parent.addService(self)

    def disownServiceParent(self):
        d = self.parent.removeService(self)
        self.parent = None
        return d

    def privilegedStartService(self):
        pass

    def startService(self):
        self.running = 1

    def stopService(self):
        self.running = 0


class IServiceCollection(components.Interface):

    """Collection of services.

    Contain several services, and manage their start-up/shut-down.
    Services can be accessed by name if they have a name, and it
    is always possible to iterate over them.
    """

    def getServiceNamed(self, name):
        """Get the child service with a given name.

        @type name: C{str}
        @rtype: C{IService}
        @raise L{KeyError}: Raised if the service has no child with the
        given name.
        """

    def __iter__(self):
        """Get an iterator over all child services"""

    def addService(self, service):
         """Add a child service.

        @type service: C{IService}
        @raise L{RuntimeError}: Raised if the service has a child with
        the given name.
        """

    def removeService(self, service):
        """Remove a child service.

        @type service: C{IService}
        @raise L{ValueError}: Raised if the given service is not a child.
        @rtype: C{Deferred}
        @return: a deferred which is triggered when the service has
        finished shutting down. If shutting down is immediate,
        a value can be returned (usually, None).
        """


class MultiService(Service):

    """Straightforward Service Container

    Hold a collection of services, and manage them in a simplistic
    way. No service will wait for another, but this object itself
    will not finish shutting down until all of its child services
    will finish.
    """

    __implements__ = Service.__implements__, IServiceCollection

    def __init__(self):
        self.services = []
        self.namedServices = {}
        self.parent = None

    def privilegedStartService(self):
        Service.privilegedStartService(self)
        for service in self:
            service.privilegedStartService()

    def startService(self):
        Service.startService(self)
        for service in self:
            service.startService()

    def stopService(self):
        Service.stopService(self)
        l = []
        services = list(self)
        services.reverse()
        for service in services:
            l.append(defer.maybeDeferred(service.stopService))
        return defer.DeferredList(l)

    def getServiceNamed(self, name):
        return self.namedServices[name]

    def __iter__(self):
        return iter(self.services)

    def addService(self, service):
        if service.name is not None:
            if self.namedServices.has_key(service.name):
                raise RuntimeError("cannot have two services with same name")
            self.namedServices[service.name] = service
        self.services.append(service)
        if self.running:
            # It may be too late for that, but we will do our best
            service.privilegedStartService()
            service.startService()

    def removeService(self, service):
        if service.name:
            del self.namedServices[service.name]
        self.services.remove(service)
        if self.running:
            # Returning this so as not to lose information from the
            # MultiService.stopService deferred.
            return service.stopService()
        else:
            return None


class IProcess(components.Interface):

    """Process running parameters

    Represents parameters for how processes should be run.

    @ivar processName: the name the process should have in ps (or None)
    @type processName: C{str}
    @ivar uid: the user-id the process should run under.
    @type uid: C{int}
    @ivar gid: the group-id the process should run under.
    @type gid: C{int}
    """


class Process:
    """Process running parameters

    Sets up uid/gid in the constructor, and has a default
    of C{None} as C{processName}.
    """
    __implements__ = IProcess,
    processName = None

    def __init__(self, uid=None, gid=None):
        """Set uid and gid.

        By default, uid or gid will be the current user's if run on POSIX,
        or 0 if run on Windows.
        """
        if platformType == "posix":
            if uid is None:
                uid = os.getuid()
            if gid is None:
                gid = os.getgid()
            self.uid = uid
            self.gid = gid
        else:
            self.uid = uid or 0
            self.gid = gid or 0


def Application(name, uid=None, gid=None):
    """Return a compound class.

    Return an object supporting the C{IService}, C{IServiceCollection},
    C{IProcess} and C{sob.IPersistable} interfaces, with the given
    parameters. Always access the return value by explicit casting to
    one of the interfaces.
    """
    ret = components.Componentized()
    for comp in (MultiService(), sob.Persistent(ret, name), Process(uid, gid)):
        ret.addComponent(comp, ignoreClass=1)
    IService(ret).setName(name)
    return ret

def loadApplication(filename, kind, passphrase=None):
    """Load Application from file

    @type filename: C{str}
    @type kind: C{str}
    @type passphrase: C{str}

    Load application from a given file. The serialization format it
    was saved in should be given as C{kind}, and is one of 'pickle', 'source',
    'xml' or 'python'. If C{passphrase} is given, the application was encrypted
    with the given passphrase.
    """
    if kind == 'python':
        application = sob.loadValueFromFile(filename, 'application', passphrase)
    else:
        application = sob.load(filename, kind, passphrase)
    if IService(application, None) is None:
        from twisted.application import compat
        application = compat.convert(application)
    return application

__all__ = ['IService', 'Service', 'IServiceCollection', 'MultiService',
           'IProcess', 'Process', 'Application', 'loadApplication']
