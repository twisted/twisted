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

"""Coil configuration for twisted.internet.app.Application.

This is used as the root of the config tree.
"""

# Twisted Imports
from twisted.protocols import protocol
from twisted.python import roots, reflect
from twisted.cred import service

# Sibling Imports
import coil

# System Imports
import string


class PortCollection(roots.Homogenous):
    """A collection of Ports; names may only be strings which represent port numbers.
    """
    entityType = protocol.Factory

    def __init__(self, app, ptype):
        self.app = app
        self.mod = reflect.namedModule('twisted.internet.'+ptype)
        self.ptype = ptype
        roots.Homogenous.__init__(self)

    def listStaticEntities(self):
        ret = []
        for port in self.app.ports:
            if isinstance(port, self.mod.Port):
                ret.append((str(port.port), port.factory))
        return ret

    def getStaticEntity(self, name):
        idx = int(name)
        for port in self.app.ports:
            if isinstance(port, self.mod.Port):
                if port.port == idx:
                    return port.factory

    def reallyPutEntity(self, portno, factory):
        getattr(self.app, 'listen'+string.upper(self.ptype))(int(portno), factory)

    def delEntity(self, portno):
        getattr(self.app, 'dontListen'+string.upper(self.ptype))(int(portno))

    def nameConstraint(self, name):
        """Enter a port number.
        """
        try:
            portno = int(name)
        except ValueError:
            raise roots.ConstraintViolation("Not a port number: %s" % repr(name))
        else:
            return 1

    def getEntityType(self):
        return "Protocol Factory"

    def getNameType(self):
        return "Port Number"


class ServiceCollection(roots.Homogenous):
    entityType = service.Service

    def __init__(self, app):
        roots.Homogenous.__init__(self)
        self.app = app

    def listStaticEntities(self):
        return self.app.services.items()

    def getStaticEntity(self, name):
        return self.app.services.get(name)

    def reallyPutEntity(self, name, entity):
        # No need to put the entity!  It will be Constrainedautomatically registered...
        pass


class ApplicationConfig(roots.Locked):
    """The root of the application configuration."""
    
    def __init__(self, app):
        roots.Locked.__init__(self)
        self.app = app
        self._addEntitiesAndLock()

    def _addEntitiesAndLock(self):
        l = roots.Locked()
        self.putEntity('ports', l)
        l.putEntity("tcp", PortCollection(self.app, 'tcp'))
        try:
            l.putEntity("ssl", PortCollection(self.app, 'ssl'))
        except ImportError:
            pass
        l.putEntity("udp", PortCollection(self.app, 'udp'))
        l.lock()
        self.putEntity("services", ServiceCollection(self.app))
        self.lock()


class ServiceConfigurator(coil.Configurator):
    """Superclass for service configurators."""
    
    configurableClass = service.Service


class ProtocolFactoryConfigurator(coil.Configurator):
    """Superclass for protocol factory configurators."""
    
    configurableClass = protocol.Factory


coil.registerConfigurator(ServiceConfigurator, None)
coil.registerConfigurator(ProtocolFactoryConfigurator, None)
