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
"""

# System Imports
import os
import string
import socket

# Twisted Imports
from twisted.protocols import protocol
from twisted.python import log
from twisted.persisted import styles
from twisted.python.runtime import platform
from twisted.cred.authorizer import DefaultAuthorizer


class Application(log.Logger, styles.Versioned):
    """I am the `root object' in a Twisted process.

    I represent a set of persistent, potentially interconnected listening TCP
    ports, delayed event schedulers, and service.Services.
    """

    running = 0
    def __init__(self, name, uid=None, gid=None, authorizer=None, authorizer_=None):
        """Initialize me.

        Arguments:

          * name: a name

          * uid: (optional) a POSIX user-id.  Only used on POSIX systems.

          * gid: (optional) a POSIX group-id.  Only used on POSIX systems.

          * authorizer: a twisted.cred.authorizer.Authorizer.

        If uid and gid arguments are not provided, this application will
        default to having the uid and gid of the user and group who created it.
        """
        self.name = name
        # a list of (tcp, ssl, udp) Ports
        self.ports = []
        # a list of (tcp, ssl, udp) Connectors
        self.connectors = []
        # a list of twisted.python.delay.Delayeds
        self.delayeds = []
        # a list of twisted.internet.cred.service.Services
        self.services = {}
        # a cred authorizer
        self.authorizer = authorizer or authorizer_ or DefaultAuthorizer()
        self.authorizer.setApplication(self)
        if platform.getType() == "posix":
            self.uid = uid or os.getuid()
            self.gid = gid or os.getgid()
        self.resolver = main.resolver


    persistenceVersion = 5

    def upgradeToVersion5(self):
        del self.entities

    def upgradeToVersion4(self):
        """Version 4 Persistence Upgrade
        """
        self.connectors = []

    def upgradeToVersion3(self):
        """Version 3 Persistence Upgrade
        """
        #roots.Locked.__init__(self)
        #self._addEntitiesAndLock()
        pass

    def upgradeToVersion2(self):
        """Version 2 Persistence Upgrade
        """
        self.resolver = DummyResolver()

    def upgradeToVersion1(self):
        """Version 1 Persistence Upgrade
        """
        log.msg("Upgrading %s Application." % repr(self.name))
        self.authorizer = DefaultAuthorizer()
        self.services = {}

    def getServiceNamed(self, serviceName):
        """Retrieve the named service from this application.

        Raise a KeyError if there is no such service name.
        """
        return self.services[serviceName]

    def addService(self, service):
        """Add a service to this application.
        """
        if self.services.has_key(service.serviceName):
            if main.running:
                main.removeCallBeforeShutdown(self.services[service.serviceName].stopService)
        self.services[service.serviceName] = service
        if main.running:
            main.callBeforeShutdown(service.stopService)

    def __repr__(self):
        return "<%s app>" % repr(self.name)

    def __getstate__(self):
        dict = styles.Versioned.__getstate__(self)
        if dict.has_key("running"):
            del dict['running']
        return dict

    def listenTCP(self, port, factory, backlog=5, interface=''):
        """
        Connects a given protocol factory to the given numeric TCP/IP port.
        """
        from twisted.internet import tcp
        self.addPort(tcp.Port(port, factory, backlog, interface))

    def dontListenTCP(self, portno):
        from twisted.internet import tcp
        for p in self.ports[:]:
            if p.port == portno and isinstance(p, tcp.Port):
                p.loseConnection()
                self.ports.remove(p)

    def dontListenUDP(self, portno):
        from twisted.internet import udp
        for p in self.ports[:]:
            if p.port == portno and isinstance(p, udp.Port):
                p.loseConnection()
                self.ports.remove(p)
    
    # deprecated name for backward compat.
    listenOn = listenTCP

    def listenUDP(self, port, factory, interface='', maxPacketSize=8192):
        """
        Connects a given protocol factory to the given numeric TCP/IP port.
        """
        from twisted.internet import udp
        self.addPort(udp.Port(port, factory, interface, maxPacketSize))

    def listenSSL(self, port, factory, ctxFactory, backlog=5, interface=''):
        """
        Connects a given protocol factory to the given numeric TCP/IP port.
        The connection is a SSL one, using contexts created by the context
        factory.
        """
        from twisted.internet import ssl
        self.addPort(ssl.Port(port, factory, ctxFactory, backlog, interface))

    def addPort(self, port):
        """
        Adds a listening port (an instance of a twisted.internet.tcp.Port) to
        this Application, to be bound when it's running.
        """
        self.ports.append(port)
        if self.running:
            port.startListening()

    def connectTCP(self, host, port, factory):
        """Connect a given client protocol factory to a specific TCP server."""
        from twisted.internet import tcp
        self.addConnector(tcp.Connector(host, port, factory))

    def connectSSL(self, host, port, factory, ctxFactory=None):
        """Connect a given client protocol factory to a specific SSL server."""
        from twisted.internet import ssl
        c = ssl.Connector(host, port, factory)
        if ctxFactory:
            c.contextFactory = ctxFactory
        self.addConnector(c)

    def addConnector(self, connector):
        """Add a connector to this Application."""
        self.connectors.append(connector)
        if self.running:
            connector.startConnecting()

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

    def shutDownSave(self):
        """Persist a pickle, then stop all protocol factories.

        The pickle will be named \"%(self.name)s-shutdown.tap\".  First, all
        currently active factories will have thier stopFactory method called.
        """
        self.save("shutdown")
        for port in self.ports:
            port.factory.stopFactory()

    def save(self, tag=None, filename=None):
        """Save a pickle of this application to a file in the current directory.
        """
        from cPickle import dump
        if filename:
            finalname = filename
            filename = finalname + "-2"
        else:
            if tag:
                filename = self.name+'-'+tag+'-2.tap'
                finalname = self.name+'-'+tag+'.tap'
            else:
                filename = self.name+"-2.tap"
                finalname = self.name+".tap"
        log.msg("Saving "+self.name+" application to "+finalname+"...")
        f = open(filename, 'wb')
        dump(self, f, 1)
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

    def run(self, save=1, installSignalHandlers=1):
        """run(save=1, installSignalHandlers=1)
        Run this application, running the main loop if necessary.
        If 'save' is true, then when this Application is shut down, it
        will be persisted to a pickle.
        'installSignalHandlers' is passed through to main.run(), the
        function that starts the mainloop.
        """
        global resolver
        if not self.running:
            log.logOwner.own(self)
            for delayed in self.delayeds:
                main.addDelayed(delayed)
            for service in self.services.values():
                main.callBeforeShutdown(service.stopService)
            if save:
                main.callAfterShutdown(self.shutDownSave)
            for port in self.ports:
                try:
                    port.startListening()
                except socket.error, msg:
                    log.msg('error on port %s: %s' % (port.port, msg))
                    return
            for connector in self.connectors:
                connector.startConnecting()
            for port in self.ports:
                port.factory.startFactory()
            for service in self.services.values():
                service.startService()
            resolver = self.resolver
            self.running = 1
            log.logOwner.disown(self)
        if not main.running:
            log.logOwner.own(self)
            self.setUID()
            global theApplication
            theApplication = self
            main.run(installSignalHandlers=installSignalHandlers)
            log.logOwner.disown(self)

# sibling import
import main

#
# These are dummy classes for backwards-compatibility!
#

class PortCollection: pass

class ServiceCollection: pass
