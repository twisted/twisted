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
from twisted.python import roots, reflect, components
from twisted.cred import service

# Sibling Imports
import coil

# System Imports
import string


class PortCollection(coil.ConfigCollection):
    """A collection of Ports; names may only be strings which represent port numbers.
    """
    
    entityType = protocol.IFactory

    def __init__(self, app, ptype):
        self.app = app
        self.mod = reflect.namedModule('twisted.internet.'+ptype)
        self.ptype = ptype
        coil.ConfigCollection.__init__(self)

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


class ServiceCollection(coil.ConfigCollection):
    """A collection of Service objects."""
    
    entityType = service.IService

    def __init__(self, app):
        coil.ConfigCollection.__init__(self)
        self.app = app

    def listStaticEntities(self):
        return self.app.services.items()

    def getStaticEntity(self, name):
        return self.app.services.get(name)

    def reallyPutEntity(self, name, entity):
        # No need to put the entity!  It will be automatically
        # registered by the Service's constructor...
        pass
    
    def delEntity(self, name):
        del self.app.services[name]

    def getEntityType(self):
        return "Service"


class ApplicationConfig(coil.StaticCollection):
    """The root of the application configuration."""
    
    def __init__(self, app):
        coil.StaticCollection.__init__(self)
        self.app = app
        self._addEntitiesAndLock()

    def _addEntitiesAndLock(self):
        l = coil.StaticCollection()
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
