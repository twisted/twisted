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

"""Main `application' configuration and persistence support.

This module is stable.

Maintainer: U{Itamar Shtull-Trauring<mailto:twisted@itamarst.org>}
"""

# System Imports
import os
import string
import socket
import types
import warnings
from cStringIO import StringIO

# Twisted Imports
from twisted.internet import interfaces
from twisted.python import log
from twisted.persisted import styles, marmalade
from twisted.python.runtime import platform
from twisted.cred.authorizer import DefaultAuthorizer
from twisted.python.reflect import Accessor

# Sibling Imports
import main, defer, error

def encrypt(passphrase, data):
    import md5
    from Crypto.Cipher import AES as cipher
    if len(data) % cipher.block_size:
        data = data + (' ' * (cipher.block_size - len(data) % cipher.block_size))
    return cipher.new(md5.new(passphrase).digest()[:16]).encrypt(data)


class _SSLlistener:
    """persistence utility; ignore me
    """
    ctx = None
    fac = None
    def __init__(self, app, port, interface, backlog):
        self.app = app
        self.port = port
        self.interface = interface
        self.backlog = backlog

    def setFactory(self, fac):
        self.fac = fac
        if self.ctx:
            self.listen()

    def setContext(self, ctx):
        self.ctx = ctx
        if self.fac:
            self.listen()

    def listen(self):
        self.app.listenSSL(self.port, self.fac, self.ctx, self.backlog, self.interface)

class _AbstractServiceCollection:
    __implements__ = (interfaces.IServiceCollection, )

    def __init__(self):
        """Create an abstract service collection.
        """
        self.services = {}

    def getServiceNamed(self, serviceName):
        """Retrieve the named service from this application.

        Raise a KeyError if there is no such service name.
        """
        return self.services[serviceName]

    def addService(self, service):
        """Add a service to this collection.
        """
        if self.services.has_key(service.serviceName):
            self.removeService(service)
        self.services[service.serviceName] = service

    def removeService(self, service):
        """Remove a service from this collection."""
        del self.services[service.serviceName]

class ApplicationService(Accessor, styles.Versioned):
    """I am a service you can add to an application.

    I represent some chunk of functionality which may be bound to many or no
    event sources.  By adding an ApplicationService to an L{Application}, it
    will be notified when the Application starts and stops (or removes/shuts
    down the service).  See the L{startService} and L{stopService} calls.

    Since services may want to incorporate certain other elements,
    notably Perspective Broker (remote invocation) accessibility
    and authentication, derivatives of ApplicationService exist
    in L{twisted.cred.service<twisted.cred.service.Service>} and
    L{twisted.spread.pb<twisted.spread.pb.Service>}.  These may be more
    suitable for your service than directly subclassing ApplicationService.
    """

    serviceType = None
    serviceName = None
    serviceParent = None
    serviceRunning = 0
    persistenceVersion = 1

    def __init__(self, serviceName, serviceParent=None, application=None):
        """Create me, attached to the given application.

        Arguments: application, a twisted.internet.app.Application instance.
        """
        if not isinstance(serviceName, types.StringType):
            raise TypeError("%s is not a string." % serviceName)
        self.serviceName = serviceName
        if application:
            warnings.warn("Application keyword argument to Service.__init__ is deprecated; use serviceParent instead.",
                          category=DeprecationWarning, stacklevel=2)
            if serviceParent:
                raise ValueError("Backwards compatible constructor failed to make sense.")
            serviceParent = application
        self.setServiceParent(serviceParent)


    def upgradeToVersion1(self):
        self.serviceParent = self.application
        del self.application

    def setServiceParent(self, serviceParent):
        """Set my parent, which must be a service collection of some kind.
        """
        if serviceParent is None:
            return
        if self.serviceParent and self.serviceParent is not serviceParent:
            raise RuntimeError("Service Parent already set!")
        self.serviceParent = serviceParent
        serviceParent.addService(self)

    def disownServiceParent(self):
        """Have my parent disown me."""
        if self.serviceParent:
            self.serviceParent.removeService(self)
            self.serviceParent = None

    def set_application(self, application):
        warnings.warn("application attribute is deprecated; use serviceParent instead.",
                      category=DeprecationWarning, stacklevel=3)
        if application and not isinstance(application, Application):
            raise TypeError( "%s is not an Application" % application)
        self.setServiceParent(application)

    setApplication = set_application

    def get_application(self):
        a = self.serviceParent
        while (not isinstance(a, Application) and a is not None):
            a = a.serviceParent
        return a

    def startService(self):
        """This call is made as a service starts up.
        """
        log.msg("%s (%s) starting" % (self.__class__, self.serviceName))
        self.serviceRunning = 1
        return None

    def stopService(self):
        """This call is made before shutdown.
        """
        log.msg("%s (%s) stopping" % (self.__class__, self.serviceName))
        self.serviceRunning = 0
        return None

class MultiService(_AbstractServiceCollection, ApplicationService):
    """I am a collection of multiple services.

    I am useful if you have a large number of services and need to categorize
    them, or you need to write a protocol that can access multiple services
    through one factory, such as a protocol that maps services to virtual
    hosts, like POP3.
    """

    def __init__(self, serviceName, serviceParent=None):
        _AbstractServiceCollection.__init__(self)
        ApplicationService.__init__(self, serviceName, serviceParent)

    def startService(self):
        ApplicationService.startService(self)
        for svc in self.services.values():
            svc.startService()

    def stopService(self):
        ApplicationService.stopService(self)
        for svc in self.services.values():
            svc.stopService()

    def addService(self, service):
        _AbstractServiceCollection.addService(self, service)
        if self.serviceRunning:
            service.startService()

    def removeService(self, service):
        if service.serviceRunning:
            service.stopService()
        _AbstractServiceCollection.removeService(self, service)


class Application(log.Logger, styles.Versioned,
                  Accessor, _AbstractServiceCollection):
    """I am the `root object' in a Twisted process.

    I represent a set of persistent, potentially interconnected listening TCP
    ports, delayed event schedulers, and service.Services.
    """

    running = 0
    def __init__(self, name, uid=None, gid=None, authorizer=None, authorizer_=None):
        """Initialize me.

        If uid and gid arguments are not provided, this application will
        default to having the uid and gid of the user and group who created it.

        @param name: a name

        @param uid: (optional) a POSIX user-id.  Only used on POSIX systems.

        @param gid: (optional) a POSIX group-id.  Only used on POSIX systems.
        """
        _AbstractServiceCollection.__init__(self)
        self.name = name
        # a list of (tcp, ssl, udp) Ports
        self.tcpPorts = []              # check
        self.udpPorts = []
        self.sslPorts = []
        self._listenerDict = {}
        # a list of (tcp, ssl, udp) Connectors
        self.tcpConnectors = []
        self.sslConnectors = []
        self.unixConnectors = []
        # a list of twisted.python.delay.Delayeds
        self.delayeds = []              # check
        # a list of twisted.internet.cred.service.Services
        self.services = {}              # check
        # a cred authorizer
        a = authorizer or authorizer_
        if a:
            self._authorizer = a
            self._authorizer.setApplication(self)
        if platform.getType() == "posix":
            self.uid = uid or os.getuid()
            self.gid = gid or os.getgid()

    persistenceVersion = 10

    _authorizer = None

    def get_authorizer(self):
        warnings.warn("Application.authorizer attribute is deprecated, use Service.authorizer instead",
                      category=DeprecationWarning, stacklevel=3)
        if not self._authorizer:
            self._authorizer = DefaultAuthorizer()
            self._authorizer.setApplication(self)
        return self._authorizer

    def upgradeToVersion9(self):
        self._authorizer = self.authorizer
        del self.authorizer
        self.tcpConnectors = self.connectors
        del self.connectors
        self.sslConnectors = []
        self.unixConnectors = []


    def upgradeToVersion8(self):
        self.persistStyle = "pickle"
        if hasattr(self, 'asXML'):
            if self.asXML:
                self.persistStyle = "xml"
            del self.asXML

    def upgradeToVersion7(self):
        self.tcpPorts = []
        self.udpPorts = []
        self.sslPorts = []
        from twisted.internet import tcp, udp
        for port in self.ports:
            if isinstance(port, tcp.Port):
                self.tcpPorts.append(
                    (port.port, port.factory,
                     port.backlog, port.interface))
            elif isinstance(port, udp.Port):
                self.udpPorts.append(
                    port.port, port.factory,
                    port.interface, port.maxPacketSize)
            else:
                log.msg('upgrade of %s not implemented, sorry' % port.__class__)
        del self.ports

    def upgradeToVersion6(self):
        del self.resolver

    def upgradeToVersion5(self):
        if hasattr(self, "entities"):
            del self.entities

    def upgradeToVersion4(self):
        """Version 4 Persistence Upgrade
        """

    def upgradeToVersion3(self):
        """Version 3 Persistence Upgrade
        """
        #roots.Locked.__init__(self)
        #self._addEntitiesAndLock()
        pass

    def upgradeToVersion2(self):
        """Version 2 Persistence Upgrade
        """
        self.resolver = main.DummyResolver()

    def upgradeToVersion1(self):
        """Version 1 Persistence Upgrade
        """
        log.msg("Upgrading %s Application." % repr(self.name))
        self.authorizer = DefaultAuthorizer()
        self.services = {}

    def __repr__(self):
        return "<%s app>" % repr(self.name)

    def __getstate__(self):
        dict = styles.Versioned.__getstate__(self)
        if dict.has_key("running"):
            del dict['running']
        if dict.has_key("_boundPorts"):
            del dict['_boundPorts']
        if dict.has_key("_listenerDict"):
            del dict['_listenerDict']
        return dict

    def listenTCP(self, port, factory, backlog=5, interface=''):
        """
        Connects a given protocol factory to the given numeric TCP/IP port.
        """
        self.tcpPorts.append((port, factory, backlog, interface))
        if self.running:
            from twisted.internet import reactor
            reactor.listenTCP(port, factory, backlog, interface)

    def unlistenTCP(self, port, interface=''):
        toRemove = []
        for t in self.tcpPorts:
            port_, factory_, backlog_, interface_ = t
            if port == port_ and interface == interface_:
                toRemove.append(t)
        for t in toRemove:
            self.tcpPorts.remove(t)
        if self._listenerDict.has_key((port_, interface_)):
            self._listenerDict[port_,interface_].stopListening()

    def listenUDP(self, port, factory, interface='', maxPacketSize=8192):
        """
        Connects a given protocol factory to the given numeric UDP port.
        """
        from twisted.internet import reactor
        self.udpPorts.append((port, factory, interface, maxPacketSize))
        if self.running:
            reactor.listenUDP(port, factory, interface, maxPacketSize)

    def dontListenUDP(self, portno):
        raise 'temporarily not implemented'

    def listenSSL(self, port, factory, ctxFactory, backlog=5, interface=''):
        """
        Connects a given protocol factory to the given numeric TCP/IP port.
        The connection is a SSL one, using contexts created by the context
        factory.
        """
        from twisted.internet import reactor
        self.sslPorts.append((port, factory, ctxFactory, backlog, interface))
        if self.running:
            reactor.listenSSL(port, factory, ctxFactory, backlog, interface)

    def connectTCP(self, host, port, factory, timeout=30, bindAddress=None):
        """Connect a given client protocol factory to a specific TCP server."""
        from twisted.internet import reactor
        self.tcpConnectors.append((host, port, factory, timeout, bindAddress))
        if self.running:
            reactor.connectTCP(host, port, factory, timeout, bindAddress)

    def connectSSL(self, host, port, factory, ctxFactory, timeout=30, bindAddress=None):
        """Connect a given client protocol factory to a specific SSL server."""
        from twisted.internet import reactor
        self.sslConnectors.append((host, port, factory, ctxFactory, timeout, bindAddress))
        if self.running:
            reactor.connectSSL(host, port, factory, ctxFactory, timeout, bindAddress)

    def connectUNIX(self, address, factory, timeout=30):
        """Connect a given client protocol factory to a specific UNIX socket."""
        from twisted.internet import reactor
        self.unixConnectors.append((address, factory, timeout))
        if self.running:
            reactor.connectUNIX(address, factory, timeout)

    def addDelayed(self, delayed):
        """
        Adds an object implementing delay.IDelayed for execution in my event loop.

        The timeout for select() will be calculated based on the sum of
        all Delayed instances attached to me, using their 'timeout'
        method.  In this manner, delayed instances should have their
        various callbacks called approximately when they're supposed to
        be (based on when they were registered).

        This is not hard realtime by any means; depending on server
        load, the callbacks may be called in more or less time.
        However, 'simulation time' for each Delayed instance will be
        monotonically increased on a regular basis.

        See the documentation for twisted.python.delay.Delayed and IDelayed
        for details.
        """
        self.delayeds.append(delayed)
        if main.running and self.running:
            main.addDelayed(delayed)

    def removeDelayed(self, delayed):
        """
        Remove a Delayed previously added to the main event loop with addDelayed.
        """
        self.delayeds.remove(delayed)
        if main.running and self.running:
            main.removeDelayed(delayed)

    def setUID(self):
        """Retrieve persistent uid/gid pair (if possible) and set the current process's uid/gid
        """
        if hasattr(os, 'getgid'):
            if not os.getgid():
                os.setgid(self.gid)
                os.setuid(self.uid)
                log.msg('set uid/gid %s/%s' % (self.uid, self.gid))



    persistStyle = "pickle"

    def save(self, tag=None, filename=None, passphrase=None):
        """Save a pickle of this application to a file in the current directory.
        """
        if self.persistStyle == "xml":
            from twisted.persisted.marmalade import jellyToXML
            dumpFunc = jellyToXML
            ext = "tax"
        elif self.persistStyle == "aot":
            from twisted.persisted.aot import jellyToSource
            dumpFunc = jellyToSource
            ext = "tas"
        else:
            from cPickle import dump
            def dumpFunc(obj, file, _dump=dump):
                _dump(obj, file, 1)
            ext = "tap"
        if filename:
            finalname = filename
            filename = finalname + "-2"
        else:
            if passphrase:
                ext = 'e' + ext
            if tag:
                filename = "%s-%s-2.%s" % (self.name, tag, ext)
                finalname = "%s-%s.%s" % (self.name, tag, ext)
            else:
                filename = "%s-2.%s" % (self.name, ext)
                finalname = "%s.%s" % (self.name, ext)
        log.msg("Saving "+self.name+" application to "+finalname+"...")

        if passphrase is None:
            f = open(filename, 'wb')
            dumpFunc(self, f)
            f.flush()
            f.close()
        else:
            f = StringIO()
            dumpFunc(self, f)
            s = encrypt(passphrase, f.getvalue())
            f = open(filename, 'wb')
            f.write(s)
            f.flush()
            f.close()

        if platform.getType() == "win32":
            if os.path.isfile(finalname):
                os.remove(finalname)
        os.rename(filename, finalname)
        log.msg("Saved.")

    def logPrefix(self):
        """A log prefix which describes me.
        """
        return "*%s*" % self.name

    def _beforeShutDown(self):
        l = []
        for service in self.services.values():
            try:
                d = service.stopService()
                if isinstance(d, defer.Deferred):
                    l.append(d)
            except:
                log.deferr()
        if l:
            return defer.DeferredList(l)


    def _afterShutDown(self):
        if self._save:
            self.save("shutdown")

    _boundPorts = 0
    def bindPorts(self):
        from twisted.internet import reactor
        self._listenerDict= {}
        self._boundPorts = 1
        if not self.running:
            log.logOwner.own(self)
            for delayed in self.delayeds:
                main.addDelayed(delayed)
            for port, factory, backlog, interface in self.tcpPorts:
                try:
                    self._listenerDict[port, interface] = reactor.listenTCP(port, factory, backlog, interface)
                except error.CannotListenError, msg:
                    log.msg('error on TCP port %s: %s' % (port, msg))
                    return
            for port, factory, interface, maxPacketSize in self.udpPorts:
                try:
                    reactor.listenUDP(port, factory, interface, maxPacketSize)
                except error.CannotListenError, msg:
                    log.msg('error on UDP port %s: %s' % (port, msg))
                    return
            for port, factory, ctxFactory, backlog, interface in self.sslPorts:
                try:
                    reactor.listenSSL(port, factory, ctxFactory, backlog, interface)
                except error.CannotListenError, msg:
                    log.msg('error on SSL port %s: %s' % (port, msg))
                    return
            for host, port, factory, ctxFactory, timeout, bindAddress in self.sslConnectors:
                reactor.connectSSL(host, port, factory, ctxFactory, timeout, bindAddress)
            for host, port, factory, timeout, bindAddress in self.tcpConnectors:
                reactor.connectTCP(host, port, factory, timeout, bindAddress)
            for address, factory, timeout in self.unixConnectors:
                reactor.connectUNIX(address, factory, timeout)

            for service in self.services.values():
                service.startService()
            self.running = 1
            log.logOwner.disown(self)

    def run(self, save=1, installSignalHandlers=1):
        """run(save=1, installSignalHandlers=1)
        Run this application, running the main loop if necessary.
        If 'save' is true, then when this Application is shut down, it
        will be persisted to a pickle.
        'installSignalHandlers' is passed through to main.run(), the
        function that starts the mainloop.
        """
        if not self._boundPorts:
            self.bindPorts()
        self._save = save
        main.callBeforeShutdown(self._beforeShutDown)
        main.callAfterShutdown(self._afterShutDown)
        if not main.running:
            log.logOwner.own(self)
            global theApplication
            theApplication = self
            main.run(installSignalHandlers=installSignalHandlers)
            log.logOwner.disown(self)

#
# These are dummy classes for backwards-compatibility!
#

class PortCollection: pass

class ServiceCollection: pass


__all__ = ["ApplicationService", "MultiService", "Application"]
