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
from twisted.python import log, defer
from twisted.persisted import styles, marmalade
from twisted.python.runtime import platform
from twisted.cred.authorizer import DefaultAuthorizer

# Sibling Imports
import main

class Application(log.Logger, styles.Versioned, marmalade.DOMJellyable):
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
        self.tcpPorts = []              # check
        self.udpPorts = []
        self.sslPorts = []
        # a list of (tcp, ssl, udp) Connectors
        self.connectors = []            # check
        # a list of twisted.python.delay.Delayeds
        self.delayeds = []              # check
        # a list of twisted.internet.cred.service.Services
        self.services = {}              # check
        # a cred authorizer
        self.authorizer = authorizer or authorizer_ or DefaultAuthorizer() # check
        self.authorizer.setApplication(self)
        if platform.getType() == "posix":
            self.uid = uid or os.getuid()
            self.gid = gid or os.getgid()


    jellyDOMVersion = 1

    def jellyToDOM_1(self, jellier, node):
        if hasattr(self, 'uid'):
            node.setAttribute("uid", str(self.uid))
            node.setAttribute("gid", str(self.gid))
        node.setAttribute("name", self.name)
        tcpnode = jellier.document.createElement("tcp")
        node.appendChild(tcpnode)
        svcnode = jellier.document.createElement("services")
        node.appendChild(svcnode)
        delaynode = jellier.document.createElement("delayeds")
        node.appendChild(delaynode)
        authnode = jellier.document.createElement("authorizer")
        node.appendChild(authnode)
        for svc in self.services.values():
            svcnode.appendChild(jellier.jellyToNode(svc))
        for port, factory, backlog, interface in self.tcpPorts:
            n = jellier.jellyToNode(factory)
            n.setAttribute("parent:listen", str(port))
            if backlog != 5:
                n.setAttribute("parent:backlog", str(backlog))
            if interface != '':
                n.setAttribute("parent:interface", str(interface))
            tcpnode.appendChild(n)
        for connector in self.connectors:
            n = jellier.jellyToNode(connector.factory)
            n.setAttribute("parent:connect", "%s:%d" % (connector.host, str(connector.portno)))
            if connector.timeout != 30:
                n.setAttribute("parent:timeout", connector.timeout)
            tcpnode.appendChild(n)
        for delayed in self.delayeds:
            n = jellier.jellyToNode(delayed)
            delaynode.appendChild(n)
        authnode.appendChild(jellier.jellyToNode(self.authorizer))

    def _cbConnectTCP(self, factory, hostname, portno, timeout):
        self.connectTCP(hostname, portno, factory, timeout)

    def _cbListenTCP(self, factory, portno, backlog, interface):
        self.listenTCP(portno, factory, backlog, interface)


    def unjellyFromDOM_1(self, unjellier, node):
        from xml.dom.minidom import Element
        if node.hasAttribute("uid"):
            self.uid = int(node.getAttribute("uid"))
            self.gid = int(node.getAttribute("gid"))
        self.name = node.getAttribute("name")
        self.udpPorts = []
        self.sslPorts = []
        self.asXML = 1
        for subnode in node.childNodes:
            if isinstance(subnode, Element):
                if subnode.tagName == 'tcp':
                    self.tcpPorts = []
                    self.connectors = []
                    for facnode in subnode.childNodes:
                        if isinstance(facnode, Element):
                            if facnode.hasAttribute("parent:connect"):
                                s = facnode.getAttribute("parent:connect")
                                hostname, portno = string.split(s, ":")
                                portno = int(portno)
                                s = facnode.getAttribute("parent:timeout") or 0
                                timeout = int(s)
                                unjellier.unjellyLater(facnode).addCallback(self._cbConnectTCP, hostname, portno, timeout).arm()
                            elif facnode.hasAttribute("parent:listen"):
                                portno = int(facnode.getAttribute("parent:listen"))
                                interface = facnode.getAttribute("parent:interface") or ''
                                backlog = int(facnode.getAttribute("parent:backlog") or 5)
                                unjellier.unjellyLater(facnode).addCallback(self._cbListenTCP, portno, backlog, interface).arm()
                            else:
                                raise ValueError("Couldn't determine type of TCP node.")
                elif subnode.tagName == 'services':
                    self.services = {}
                    for svcnode in subnode.childNodes:
                        if isinstance(svcnode, Element):
                            unjellier.unjellyLater(svcnode).addCallback(self.addService).arm()
                elif subnode.tagName == 'authorizer':
                    authnode = marmalade.getValueElement(subnode)
                    unjellier.unjellyAttribute(self, "authorizer", authnode)
                elif subnode.tagName == 'delayeds':
                    self.delayeds = []
                    for delnode in subnode.childNodes:
                        if isinstance(delnode, Element):
                            unjellier.unjellyLater(delnode).addCallback(self.addDelayed).arm()

    persistenceVersion = 7

    def upgradeToVersion7(self):
        print 'upgrading 7'
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
                print 'upgrade of %s not implemented, sorry' % port.__class__
        del self.ports

    def upgradeToVersion6(self):
        del self.resolver

    def upgradeToVersion5(self):
        if hasattr(self, "entities"):
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
        self.resolver = main.DummyResolver()

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
        # XXX TODO remove existing service first
        self.services[service.serviceName] = service

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
        self.tcpPorts.append((port, factory, backlog, interface))
        if self.running:
            from twisted.internet import reactor
            reactor.listenTCP(port, factory, backlog, interface)

    def dontListenTCP(self, portno):
        raise 'temporarily not implemented'

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
        raise 'temporarily unimplemented'

    def connectTCP(self, host, port, factory, timeout=30):
        """Connect a given client protocol factory to a specific TCP server.

        If the client gets disconnected, a new instance will be created
        and will attempt to reconnect. If you only want a single connection,
        use twisted.internet.reactor's clientTCP() method instead.
        """
        from twisted.internet import tcp
        self.addConnector(tcp.Connector(host, port, factory, timeout))

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


    asXML = 0

    def save(self, tag=None, filename=None):
        """Save a pickle of this application to a file in the current directory.
        """
        if self.asXML:
            from twisted.persisted.marmalade import jellyToXML
            dumpFunc = jellyToXML
            ext = "tax"
        else:
            from cPickle import dump
            def dumpFunc(obj, file, _dump=dump):
                _dump(obj, file, 1)
            ext = "tap"
        if filename:
            finalname = filename
            filename = finalname + "-2"
        else:
            if tag:
                filename = "%s-%s-2.%s" % (self.name, tag, ext)
                finalname = "%s-%s.%s" % (self.name, tag, ext)
            else:
                filename = "%s-2.%s" % (self.name, ext)
                finalname = "%s.%s" % (self.name, ext)
        log.msg("Saving "+self.name+" application to "+finalname+"...")
        f = open(filename, 'wb')
        dumpFunc(self, f)
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


    def run(self, save=1, installSignalHandlers=1):
        """run(save=1, installSignalHandlers=1)
        Run this application, running the main loop if necessary.
        If 'save' is true, then when this Application is shut down, it
        will be persisted to a pickle.
        'installSignalHandlers' is passed through to main.run(), the
        function that starts the mainloop.
        """
        from twisted.internet import reactor

        if not self.running:
            log.logOwner.own(self)
            for delayed in self.delayeds:
                main.addDelayed(delayed)
            self._save = save
            main.callBeforeShutdown(self._beforeShutDown)
            main.callAfterShutdown(self._afterShutDown)
            for port, factory, backlog, interface in self.tcpPorts:
                try:
                    reactor.listenTCP(port, factory, backlog, interface)
                except socket.error, msg:
                    log.msg('error on TCP port %s: %s' % (port, msg))
                    return
            for port, factory, interface, maxPacketSize in self.udpPorts:
                try:
                    reactor.listenUDP(port, factory, interface, maxPacketSize)
                except socket.error, msg:
                    log.msg('error on UDP port %s: %s' % (port, msg))
                    return
            for connector in self.connectors:
                connector.startConnecting()
            for service in self.services.values():
                service.startService()
            self.running = 1
            log.logOwner.disown(self)
        if not main.running:
            log.logOwner.own(self)
            self.setUID()
            global theApplication
            theApplication = self
            main.run(installSignalHandlers=installSignalHandlers)
            log.logOwner.disown(self)

#
# These are dummy classes for backwards-compatibility!
#

class PortCollection: pass

class ServiceCollection: pass
