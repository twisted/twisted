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
from twisted.internet.interfaces import IConnector, IProtocolFactory
from twisted.python import log, roots, reflect, components
from twisted.cred import service

# Sibling Imports
import coil

# System Imports
import string


class PortCollection(coil.ConfigCollection):
    """A collection of Ports; names may only be strings which represent port numbers.
    """

    entityType = IProtocolFactory

    def __init__(self, app, ptype):
        self.app = app
        self.mod = reflect.namedModule('twisted.internet.'+ptype)
        self.ptype = ptype
        coil.ConfigCollection.__init__(self)

    def listStaticEntities(self):
        ret = []
        for port in getattr(self.app, '%sPorts' % self.ptype):
            ret.append((str(port[0]), port[1]))
        return ret

    def getStaticEntity(self, name):
        idx = int(name)
        for port in getattr(self.app, '%sPorts' % self.ptype):
            if port[0] == idx:
                return port[1]
        raise KeyError, "No such entity %s" % (name,)

    def reallyPutEntity(self, portno, factory):
        getattr(self.app, 'listen'+string.upper(self.ptype))(int(portno), factory)

    def delEntity(self, portno):
        getattr(self.app, 'dontListen'+string.upper(self.ptype))(int(portno))

    def nameConstraint(self, name):
        """Enter a port number.
        """
        try:
            int(name)
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


class ConnectorCollection(coil.ConfigCollection):
    # XXX this class is broken right now
    entityType = IConnector

    def __init__(self, app):
        coil.ConfigCollection.__init__(self)
        self.app = app

    def getStaticEntity(self, name):
        return self.app.connectors[self._getIndexFromName(name)]

    def reallyPutEntity(self, name, connector):
        """Adds a Connector to the Application.
        """
        host, port = self._getHostPortFromName(name)
        if not connector.host:
            connector.host = host
        if not connector.portno:
            connector.portno = port

        self.app.addConnector(connector)

    def delEntity(self, name):
        del self.app.connectors[self._getIndexFromName(name)]

    def getEntityType(self):
        return "Connector"

    def nameConstraint(self, name):
        try:
            name = string.split(name, ',', 1)[0]
            host, port = string.split(name, ':')
        except:
            raise roots.ConstraintViolation("Name %s is not a string "
                                            "in \"host:port\" format."
                                            % (repr(name),))
        else:
            return 1

    def _getHostPortFromName(self, name):
        hostport = string.split(name,',')[0]
        host, port = string.split(hostport,':')
        try:
            port = int(port)
        except ValueError:
            pass
        return (host, port)

    def _getIndexFromName(self, name):
        if ',' not in name:
            try:
                i = int(name)
            except ValueError:
                raise ValueError, \
                      "\"%s\" does not have a list index" % (name,)
        else:
            name_hostport, i = string.split(name,',')
            i = int(i)

        # Sanity check
        if name_hostport:
            connector = self.app.connectors[i]
            got_hostport = "%s:%s" % (connector.host, connector.portno)
            if name_hostport != got_hostport:
                log.msg("Warning: host:port for connector %d (%s) does "
                        "not match given string %s" %
                        (i, got_hostport, name_hostport))

        return i

    def __str__(self):
        return "Collection of Connectors in %s" % (str(self.app),)

    def __repr__(self):
        return "<%s at 0x%x in app '%s'>" % (self.__class__, id(self),
                                             self.app.name)


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
        except (ImportError, AttributeError):
            pass
        l.putEntity("udp", PortCollection(self.app, 'udp'))
        l.lock()
        self.putEntity("services", ServiceCollection(self.app))
        # self.putEntity("connectors", ConnectorCollection(self.app))
        self.lock()
