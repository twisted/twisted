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
from twisted.python import log, roots, reflect
from twisted.persisted import styles
from twisted.python.runtime import platform

# Sibling Imports
import passport

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


class ServiceCollection(roots.Homogenous):
    entityType = passport.Service

    def __init__(self, app):
        roots.Homogenous.__init__(self)
        self.app = app

    def listStaticEntities(self):
        return self.app.services.items()

    def getStaticEntity(self, name):
        return self.app.services.get(name)

    def reallyPutEntity(self, name, entity):
        # No need to put the entity!  It will be automatically registered...
        pass


class Application(log.Logger, styles.Versioned, roots.Locked):
    """I am the `root object' in a Twisted process.

    I represent a set of persistent, potentially interconnected listening TCP
    ports, delayed event schedulers, and passport.Services.
    """

    running = 0
    def __init__(self, name, uid=None, gid=None, authorizer=None):
        """Initialize me.

        Arguments:

          * name: a name

          * uid: (optional) a POSIX user-id.  Only used on POSIX systems.

          * gid: (optional) a POSIX group-id.  Only used on POSIX systems.

          * authorizer: a twisted.internet.passport.Authorizer.

        If uid and gid arguments are not provided, this application will
        default to having the uid and gid of the user and group who created it.
        """
        roots.Constrained.__init__(self)
        
        self.name = name
        # a list of (tcp, ssl, udp) Ports
        self.ports = []
        # a list of twisted.python.delay.Delayeds
        self.delayeds = []
        # a list of twisted.internet.passport.Services
        self.services = {}
        # a passport authorizer
        self.authorizer = authorizer or passport.DefaultAuthorizer()
        if platform.getType() == "posix":
            self.uid = uid or os.getuid()
            self.gid = gid or os.getgid()
        self.resolver = main.resolver
        self._addEntitiesAndLock()

    def _addEntitiesAndLock(self):
        l = roots.Locked()
        self.putEntity('ports', l)
        l.putEntity("tcp", PortCollection(self, 'tcp'))
        try:
            l.putEntity("ssl", PortCollection(self, 'ssl'))
        except ImportError:
            pass
        l.putEntity("udp", PortCollection(self, 'udp'))
        l.lock()
        self.putEntity("services", ServiceCollection(self))
        self.lock()
        

    persistenceVersion = 3

    def upgradeToVersion3(self):
        """Version 3 Persistence Upgrade
        """
        roots.Locked.__init__(self)
        self._addEntitiesAndLock()

    def upgradeToVersion2(self):
        """Version 2 Persistence Upgrade
        """
        self.resolver = DummyResolver()

    def upgradeToVersion1(self):
        """Version 1 Persistence Upgrade
        """
        log.msg("Upgrading %s Application." % repr(self.name))
        self.authorizer = passport.DefaultAuthorizer()
        self.services = {}

    def getServiceNamed(self, serviceName):
        """Retrieve the named service from this application.

        Raise a KeyError if there is no such service name.
        """
        return self.services[serviceName]

    def addService(self, service):
        """Add a service to this application.
        """
        self.services[service.serviceName] = service

    def __repr__(self):
        return "<%s app>" % self.name

    def __getstate__(self):
        dict = styles.Versioned.__getstate__(self)
        if dict.has_key("running"):
            del dict['running']
        return dict

    def listenTCP(self, port, factory, backlog=5):
        """
        Connects a given protocol factory to the given numeric TCP/IP port.
        """
        from twisted.internet import tcp
        self.addPort(tcp.Port(port, factory, backlog))

    def dontListenTCP(self, portno):
        for p in self.ports[:]:
            if p.port == portno:
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

    def listenSSL(self, port, factory, ctxFactory, backlog=5):
        """
        Connects a given protocol factory to the given numeric TCP/IP port.
        The connection is a SSL one, using contexts created by the context
        factory.
        """
        from twisted.internet import ssl
        self.addPort(ssl.Port(port, factory, ctxFactory, backlog))

    def addPort(self, port):
        """
        Adds a listening port (an instance of a twisted.internet.tcp.Port) to
        this Application, to be bound when it's running.
        """
        self.ports.append(port)
        if self.running:
            port.startListening()

    def addDelayed(self, delayed):
        """
        Adds a twisted.python.delay.Delayed object for execution in my event loop.

        The timeout for select() will be calculated based on the sum of
        all Delayed instances attached to me, using their 'ticktime'
        attribute.  In this manner, delayed instances should have their
        various callbacks called approximately when they're supposed to
        be (based on when they were registered).

        This is not hard realtime by any means; depending on server
        load, the callbacks may be called in more or less time.
        However, 'simulation time' for each Delayed instance will be
        monotonically increased on a regular basis.

        See the documentation for twisted.python.delay.Delayed for
        details.
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

    def save(self, tag=None):
        """Save a pickle of this application to a file in the current directory.
        """
        from cPickle import dump
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
        return self.name+" application"

    def run(self, save=1):
        """Run this application, running the main loop if necessary.
        """
        global resolver
        if not self.running:
            log.logOwner.own(self)
            for delayed in self.delayeds:
                main.addDelayed(delayed)
            if save:
                main.addShutdown(self.shutDownSave)
            for port in self.ports:
                try:
                    port.startListening()
                except socket.error:
                    print 'port %s already bound' % port.port
                    return
            for port in self.ports:
                port.factory.startFactory()
            resolver = self.resolver
            self.running = 1
            log.logOwner.disown(self)
        if not main.running:
            log.logOwner.own(self)
            self.setUID()
            global theApplication
            theApplication = self
            main.run()
            log.logOwner.disown(self)

# sibling import
import main
