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

"""Reactor-based Services

Here are services to run clients, servers and periodic services using
the reactor.

API Stability: unstable

Maintainer: U{Moshe Zadka<mailto:moshez@twistedmatrix.com>}
"""

from twisted.python import log
from twisted.application import service


class _VolatileDataService(service.Service):

    volatile = []

    def __getstate__(self):
        d = service.Service.__getstate__(self)
        for attr in self.volatile:
            if d.has_key(attr):
                del d[attr]
        return d

class _AbstractServer(_VolatileDataService):

    privileged = True
    volatile = ['_port']
    method = None

    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs

    def privilegedStartService(self):
        service.Service.privilegedStartService(self)
        self._port = self._getPort()

    def startService(self):
        service.Service.startService(self)
        if not hasattr(self,'_port'):
            self._port = self._getPort()

    def stopService(self):
        service.Service.stopService(self)
        # TODO: if startup failed, should shutdown skip stopListening?
        # _port won't exist
        d = self._port.stopListening()
        del self._port
        return d

    def _getPort(self):
        from twisted.internet import reactor
        return getattr(reactor, 'listen'+self.method)(*self.args, **self.kwargs)

class _AbstractClient(_VolatileDataService):

    volatile = ['_connection']
    method = None

    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs

    def startService(self):
        service.Service.startService(self)
        self._connection = self._getConnection()

    def stopService(self):
        service.Service.stopService(self)
        #self._connection.disconnect()  #TODO: needs testing

    def _getConnection(self):
        from twisted.internet import reactor
        return getattr(reactor, 'connect'+self.method)(*self.args,
                                                       **self.kwargs)



_doc={
'Client':
"""Connect to %(tran)s

Call reactor.connect%(method)s when the service starts, with the
arguments given to the constructor.
""",
'Server':
"""Serve %(tran)s clients

Call reactor.listen%(method)s when the service starts, with the
arguments given to the constructor. When the service stops,
stop listening. See twisted.internet.interfaces for documentation
on arguments to the reactor method.
""",
}

# TCPServer TCPClient UNIXServer UNIXClient SSLServer SSLClient
# UDPServer UDPClient UNIXDatagramServer UNIXDatagramClient
# MulticastServer MulticastClient
#
# This message brought to you by the Twisted Committee for Better Grepping

import new
for tran in 'Generic TCP UNIX SSL UDP UNIXDatagram Multicast'.split():
    for side in 'Server Client'.split():
        base = globals()['_Abstract'+side]
        method = {'Generic': 'With'}.get(tran, tran)
        doc = _doc[side]%vars()
        klass = new.classobj(tran+side, (base,),
                             {'method': method, '__doc__': doc})
        globals()[tran+side] = klass


class TimerService(_VolatileDataService):

    volatile = ['_call']

    """Service to periodically call a function

    Every C{step} seconds call the given function with the given arguments.
    The service starts the calls when it starts, and cancels them
    when it stops.
    """

    def __init__(self, step, callable, *args, **kwargs):
        self.step = step
        from twisted.internet.task import LoopingCall
        self.loop = LoopingCall(callable, *args, **kwargs)

    def startService(self):
        from twisted.internet import reactor
        service.Service.startService(self)
        self._call = reactor.callLater(self.step, self._startLoop, self.step)

    def _startLoop(self, step):
        self._call = None
        self.loop.start(step).addBoth(self._cleanupLoop).addErrback(log.err)

    def _cleanupLoop(self, result):
        self.loop = None
        return result

    def stopService(self):
        service.Service.stopService(self)
        if self._call is not None:
            _call, self._call = self._call, None
            _call.cancel()
        elif self.loop is not None:
            loop, self.loop = self.loop, None
            loop.stop()


__all__ = (['TimerService']+
           [tran+side
         for tran in 'Generic TCP UNIX SSL UDP UNIXDatagram Multicast'.split()
         for side in 'Server Client'.split()])
