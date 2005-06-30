# -*- test-case-name: twisted.test.test_application -*-

# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.

#

"""Reactor-based Services

Here are services to run clients, servers and periodic services using
the reactor.

This module (dynamically) defines various Service subclasses that let
you represent clients and servers in a Service hierarchy.

They are as follows::

  TCPServer, TCPClient,
  UNIXServer, UNIXClient,
  SSLServer, SSLClient,
  UDPServer, UDPClient,
  UNIXDatagramServer, UNIXDatagramClient,
  MulticastServer

These classes take arbitrary arguments in their constructors and pass
them straight on to their respective reactor.listenXXX or
reactor.connectXXX calls.

For example, the following service starts a web server on port 8080:
TCPServer(8080, server.Site(r)).  See the documentation for the
reactor.listen/connect* methods for more information.

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

    _port = None

    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs

    def privilegedStartService(self):
        service.Service.privilegedStartService(self)
        self._port = self._getPort()

    def startService(self):
        service.Service.startService(self)
        if self._port is None:
            self._port = self._getPort()

    def stopService(self):
        service.Service.stopService(self)
        # TODO: if startup failed, should shutdown skip stopListening?
        # _port won't exist
        if self._port is not None:
            d = self._port.stopListening()
            del self._port
            return d

    def _getPort(self):
        from twisted.internet import reactor
        return getattr(reactor, 'listen'+self.method)(*self.args, **self.kwargs)

class _AbstractClient(_VolatileDataService):

    volatile = ['_connection']
    method = None

    _connection = None

    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs

    def startService(self):
        service.Service.startService(self)
        self._connection = self._getConnection()

    def stopService(self):
        service.Service.stopService(self)
        if self._connection is not None:
            self._connection.disconnect()
            del self._connection

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

import new
for tran in 'Generic TCP UNIX SSL UDP UNIXDatagram Multicast'.split():
    for side in 'Server Client'.split():
        if tran == "Multicast" and side == "Client":
            continue
        base = globals()['_Abstract'+side]
        method = {'Generic': 'With'}.get(tran, tran)
        doc = _doc[side]%vars()
        klass = new.classobj(tran+side, (base,),
                             {'method': method, '__doc__': doc})
        globals()[tran+side] = klass


class TimerService(_VolatileDataService):

    """Service to periodically call a function

    Every C{step} seconds call the given function with the given arguments.
    The service starts the calls when it starts, and cancels them
    when it stops.
    """

    volatile = ['_loop']

    def __init__(self, step, callable, *args, **kwargs):
        self.step = step
        self.call = (callable, args, kwargs)

    def startService(self):
        service.Service.startService(self)
        from twisted.internet.task import LoopingCall
        callable, args, kwargs = self.call
        # we have to make a new LoopingCall each time we're started, because
        # an active LoopingCall remains active when serialized. If
        # LoopingCall were a _VolatileDataService, we wouldn't need to do
        # this.
        self._loop = LoopingCall(callable, *args, **kwargs)
        self._loop.start(self.step, now=True).addErrback(self._failed)

    def _failed(self, why):
        # make a note that the LoopingCall is no longer looping, so we don't
        # try to shut it down a second time in stopService. I think this
        # should be in LoopingCall. -warner
        self._loop.running = False
        log.err(why)

    def stopService(self):
        if self._loop.running:
            self._loop.stop()
        return service.Service.stopService(self)


__all__ = (['TimerService']+
           [tran+side
         for tran in 'Generic TCP UNIX SSL UDP UNIXDatagram Multicast'.split()
         for side in 'Server Client'.split()])
