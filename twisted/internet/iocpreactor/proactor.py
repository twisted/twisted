# Twisted, the Framework of Your Internet
# Copyright (C) 2004 Matthew W. Lefkowitz
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

from twisted.internet import defer, base, main
from twisted.internet.interfaces import IReactorTCP, IReactorUDP, IReactorArbitrary
from twisted.python import threadable, log
from zope.interface import implements

import tcp, udp
from _iocp import iocpcore

class Proactor(iocpcore, base.ReactorBase):
    # TODO: IReactorArbitrary, IReactorUDP, IReactorMulticast,
    # IReactorSSL (or leave it until exarkun finishes TLS)
    # IReactorProcess, IReactorCore (cleanup)
    implements(IReactorTCP, IReactorUDP, IReactorArbitrary)
    handles = None
    iocp = None

    def __init__(self):
        iocpcore.__init__(self)
        base.ReactorBase.__init__(self)
#        self.completables = {}

    def startRunning(self):
        threadable.registerAsIOThread()
        self.fireSystemEvent('startup')
        self.running = 1

    def run(self):
        self.startRunning()
        self.mainLoop()

    def mainLoop(self):
        while self.running:
            try:
                while self.running:
                    # Advance simulation time in delayed event
                    # processors.
                    self.runUntilCurrent()
                    t2 = self.timeout()
                    t = self.running and t2
                    self.doIteration(t)
            except KeyboardInterrupt:
                self.stop()
            except:
                log.msg("Unexpected error in main loop.")
                log.deferr()
            else:
                log.msg('Main loop terminated.')

    def removeAll(self):
        return []

    def installWaker(self):
        pass

    def wakeUp(self):
        def ignore(ret, bytes, arg):
            pass
        if not threadable.isInIOThread():
            self.issuePostQueuedCompletionStatus(ignore, None)
            
    def listenTCP(self, port, factory, backlog=50, interface=''):
        p = tcp.Port((interface, port), factory, backlog)
        p.startListening()
        return p

    def connectTCP(self, host, port, factory, timeout=30, bindAddress=None):
        c = tcp.Connector((host, port), factory, timeout, bindAddress)
        c.connect()
        return c

    def listenUDP(self, port, protocol, interface='', maxPacketSize=8192):
        p = udp.Port((interface, port), protocol, maxPacketSize)
        p.startListening()
        return p

    def connectUDPblah(self, remotehost, remoteport, protocol, localport=0,
                  interface='', maxPacketSize=8192):
        p = udp.ConnectedPort((remotehost, remoteport), (interface, localport), protocol, maxPacketSize)
        p.startListening()
        return p

    def listenWith(self, portType, *args, **kw):
        p = portType(*args, **kw)
        p.startListening()
        return p

    def connectWith(self, connectorType, *args, **kw):
        c = connectorType(*args, **kw)
        c.connect()
        return c

def install():
    from twisted.python import threadable
    p = Proactor()
    threadable.init()
    main.installReactor(p)

