# -*- test-case-name: twisted.test.test_application -*-

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
"""Backwards compatibility module

This module allows Applications to behave (partially) like old Application
objects, and converts olds Applications to new ones. 

API Stability: unstable

Maintainer: U{Moshe Zadka<mailto:moshez@twistedmatrix.com>}
"""

from twisted.python import components
from twisted.application import internet, service
from twisted.persisted import sob
import warnings, sys


class IOldApplication(components.Interface):

    """A subset of the interface old Application objects had implicitly

    This interface defines a subset of the interface old Application
    objects had, so that new objects can support it for compatibility
    with old code
    """
    def listenWith(self, portType, *args, **kw):
        """Add a service that starts an instance of C{portType} listening.

        @type portType: type which implements C{IListeningPort}
        @param portType: The object given by C{portType(*args, **kw)}
        will be started listening.
        """

    def listenTCP(self, port, factory, backlog=5, interface=''):
        """Add a service that connects a given protocol factory to the port.

        @param port: a port number on which to listen

        @param factory: a twisted.internet.protocol.ServerFactory instance

        @param backlog: size of the listen queue

        @param interface: the hostname to bind to, defaults to '' (all)
        """

    def listenUNIX(self, filename, factory, backlog=5, mode=0666):
        """Add a service that listens on a UNIX socket.

        @param address: a path to a unix socket on the filesystem.

        @param factory: a L{twisted.internet.protocol.Factory} instance.

        @param backlog: number of connections to allow in backlog.

        @param mode: mode to set on the unix socket.
        """

    def listenUDP(self, port, proto, interface='', maxPacketSize=8192):
        """Add a service that connects a given DatagramProtocol to the port.
        """

    def listenSSL(self, port, factory, ctxFactory, backlog=5, interface=''):
        """Add a service that connects a given protocol factory to the port.

        The connection is a SSL one, using contexts created by the context
        factory.

        @param port: a port number on which to listen

        @param factory: a L{twisted.internet.protocol.ServerFactory} instance

        @param contextFactory: a L{twisted.internet.ssl.ContextFactory} instance

        @param backlog: size of the listen queue

        @param interface: the hostname to bind to, defaults to '' (all)
        """

    def connectWith(self, connectorType, *args, **kw):
        """Add a service that starts an instance of C{connectorType} connecting.

        @type connectorType: type which implements C{IConnector}
        @param connectorType: The object given by C{connectorType(*args, **kw)}
        will be started connecting.
        """

    def connectUDP(self, remotehost, remoteport, protocol, localport=0,
                  interface='', maxPacketSize=8192):
        """Add a service that connects a L{ConnectedDatagramProtocol} to a port.
        """

    def connectTCP(self, host, port, factory, timeout=30, bindAddress=None):
        """Add a service that connects a TCP client.

        @param host: a host name

        @param port: a port number

        @param factory: a twisted.internet.protocol.ClientFactory instance

        @param timeout: number of seconds to wait before assuming the
                        connection has failed.

        @param bindAddress: a (host, port) tuple of local address to bind
                            to, or None.
        """

    def connectSSL(self, host, port, factory, ctxFactory, timeout=30,
                   bindAddress=None):
        """Add a service that connects a client Protocol to a remote SSL socket.

        @param host: a host name

        @param port: a port number

        @param factory: a L{twisted.internet.protocol.ClientFactory} instance

        @param contextFactory: a L{twisted.internet.ssl.ClientContextFactory}

        @param timeout: number of seconds to wait before assuming the connection
            has failed

        @param bindAddress: a (host, port) tuple of local address to bind to, or
            C{None}
        """

    def connectUNIX(self, address, factory, timeout=30):
        """Add a service that connects a client protocol to a UNIX socket.

        @param address: a path to a unix socket on the filesystem.

        @param factory: a L{twisted.internet.protocol.ClientFactory} instance

        @param timeout: number of seconds to wait before assuming the connection
            has failed.
        """

    def addService(self, service):
        """Add a service to this collection.
        """

    def getServiceNamed(self, name):
        """Retrieve the named service from this application.

        Raise a KeyError if there is no such service name.
        """

    def removeService(self, service):
        """Remove a service from this collection."""

    def unlistenWith(self, portType, *args, **kw):
        """Maybe remove a listener

        This function is inherently unreliable, and may or may
        not remove a service.
        """

    def unlistenTCP(self, port, interface=''):
        """Maybe remove a listener

        This function is inherently unreliable, and may or may
        not remove a service.
        """

    def unlistenUNIX(self, filename):
        """Maybe remove a listener

        This function is inherently unreliable, and may or may
        not remove a service.
        """

    def unlistenUDP(self, port, interface=''):
        """Maybe remove a listener

        This function is inherently unreliable, and may or may
        not remove a service.
        """

    def unlistenSSL(self, port, interface=''):
        """Maybe remove a listener

        This function is inherently unreliable, and may or may
        not remove a service.
        """


class _NewService:
    """Wrap a twisted.internet.app.ApplicationService in new service API."""

    __implements__ = service.IService,

    running = 0
    
    def __init__(self, service):
        self.service = service
        self.name = service.serviceName

    def setName(self, name):
        raise RuntimeError

    def setServiceParent(self, parent):
        self.service.setServiceParent(parent)

    def disownServiceParent(self):
        self.service.disownServiceParent()

    def startService(self):
        self.running = 1
        self.service.startService()

    def stopService(self):
        self.running = 0
        return self.service.stopService()

    def privilegedStartService(self):
        pass

    def get_name(self):
        return self.service.serviceName

    name = property(get_name)
    del get_name
    
    def __cmp__(self, other):
        return cmp(self.service, other)

    def __hash__(self):
        return hash(self.service)


class _ServiceNetwork:

    __implements__ = IOldApplication,

    def __init__(self, app):
        self.app = service.IServiceCollection(app)

    def listenWith(self, portType, *args, **kw):
        s = internet.GenericServer(portType, *args, **kw)
        s.privileged = 1
        s.setServiceParent(self.app)

    def listenTCP(self, port, factory, backlog=5, interface=''):
        s = internet.TCPServer(port, factory, backlog, interface)
        s.privileged = 1
        s.setServiceParent(self.app)

    def listenUNIX(self, filename, factory, backlog=5, mode=0666):
        s = internet.UNIXServer(filename, factory, backlog, mode)
        s.privileged = 1
        s.setServiceParent(self.app)

    def listenUDP(self, port, proto, interface='', maxPacketSize=8192):
        s = internet.UDPServer(port, proto, interface, maxPacketSize)
        s.privileged = 1
        s.setServiceParent(self.app)

    def listenSSL(self, port, factory, ctxFactory, backlog=5, interface=''):
        s = internet.SSLServer(port, factory, ctxFactory, backlog, interface)
        s.privileged = 1
        s.setServiceParent(self.app)

    def connectWith(self, connectorType, *args, **kw):
        s = internet.GenericClient(connectorType,  *args, **kw)
        s.setServiceParent(self.app)

    def connectUDP(self, remotehost, remoteport, protocol, localport=0,
                  interface='', maxPacketSize=8192):
        s = internet.UDPClient(remotehost, remoteport, protocol, localport,
                               interface, maxPacketSize)
        s.setServiceParent(self.app)

    def connectTCP(self, host, port, factory, timeout=30, bindAddress=None):
        s = internet.TCPClient(host, port, factory, timeout, bindAddress)
        s.setServiceParent(self.app)

    def connectSSL(self, host, port, factory, ctxFactory, timeout=30,
                   bindAddress=None):
        s = internet.SSLClient(host, port, factory, ctxFactory, timeout,
                               bindAddress)
        s.setServiceParent(self.app)

    def connectUNIX(self, address, factory, timeout=30):
        s = internet.UNIXClient(address, factory, timeout)
        s.setServiceParent(self.app)

    def addService(self, service):
        if 'twisted.internet.app' in sys.modules:
            from twisted.internet import app as oldapp
            if isinstance(service, oldapp.ApplicationService):
                service = _NewService(service)
        self.app.addService(service)

    def removeService(self, service):
        if 'twisted.internet.app' in sys.modules:
            from twisted.internet import app as oldapp
            if isinstance(service, oldapp.ApplicationService):
                service = _NewService(service)
        self.app.removeService(service)

    def getServiceNamed(self, name):
        result = self.app.getServiceNamed(name)
        if isinstance(result, _NewService):
            result = result.service
        return result

    def unlistenWith(self, portType, *args, **kw):
        warnings.warn("unlisten* does not work anymore. Name services "
                      "that you want to be able to remove",
                      category=RuntimeWarning)

    def unlistenTCP(self, port, interface=''):
        warnings.warn("unlisten* does not work anymore. Name services "
                      "that you want to be able to remove",
                      category=RuntimeWarning)

    def unlistenUNIX(self, filename):
        warnings.warn("unlisten* does not work anymore. Name services "
                      "that you want to be able to remove",
                      category=RuntimeWarning)

    def unlistenUDP(self, port, interface=''):
        warnings.warn("unlisten* does not work anymore. Name services "
                      "that you want to be able to remove",
                      category=RuntimeWarning)

    def unlistenSSL(self, port, interface=''):
        warnings.warn("unlisten* does not work anymore. Name services "
                      "that you want to be able to remove",
                      category=RuntimeWarning)


components.registerAdapter(_ServiceNetwork,
                           service.IServiceCollection, IOldApplication)


_mapping = []
for tran in 'tcp unix udp ssl'.split():
    _mapping.append((tran+'Ports', getattr(internet, tran.upper()+'Server')))
    _mapping.append((tran+'Connectors',getattr(internet,tran.upper()+'Client')))

def convert(oldApp):
    '''Convert an C{i.app.Application} to a C{application.service.Application}

    @type oldApp: C{twisted.internet.app.Application}
    @rtype C{twisted.application.service.Application}

    This function might damage oldApp beyond repair: services
    that other parts might be depending on might be missing.
    It is not safe to use oldApp after it has been converted.
    In case this behaviour is not desirable, pass a deep copy
    of the old application
    '''
    ret = service.Application(oldApp.name, getattr(oldApp, "uid", None), getattr(oldApp, "gid", None))
    c = service.IServiceCollection(ret)
    service.IProcess(ret).processName = oldApp.processName
    for (pList, klass) in [(oldApp.extraPorts, internet.GenericServer),
                           (oldApp.extraConnectors, internet.GenericClient),]:
        for (portType, args, kw) in pList:
            klass(portType, *args, **kw).setServiceParent(c)
    for (name, klass) in _mapping:
        for args in getattr(oldApp, name):
            klass(*args).setServiceParent(c)
    for s in c:
        if hasattr(s, 'privileged'):
            s.privileged = 1
    for s in oldApp.services.values():
        if not components.implements(s, service.IService):
            s.serviceParent = None
            s = _NewService(s)
            s.setServiceParent(IOldApplication(c))
        else:
            s.serviceParent = None
            s.setServiceParent(c)
    return ret


__all__ = ['IOldApplication', 'convert']
