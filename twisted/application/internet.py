# -*- test-case-name: twisted.application.test.test_internet,twisted.test.test_application,twisted.test.test_cooperator -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Reactor-based Services

Here are services to run clients, servers and periodic services using
the reactor.

If you want to run a server service, L{StreamServerEndpointService} defines a
service that can wrap an arbitrary L{IStreamServerEndpoint
<twisted.internet.interfaces.IStreamServerEndpoint>}
as an L{IService}. See also L{twisted.application.strports.service} for
constructing one of these directly from a descriptive string.

Additionally, this module (dynamically) defines various Service subclasses that
let you represent clients and servers in a Service hierarchy.  Endpoints APIs
should be preferred for stream server services, but since those APIs do not yet
exist for clients or datagram services, many of these are still useful.

They are as follows::

  TCPServer, TCPClient,
  UNIXServer, UNIXClient,
  SSLServer, SSLClient,
  UDPServer,
  UNIXDatagramServer, UNIXDatagramClient,
  MulticastServer

These classes take arbitrary arguments in their constructors and pass
them straight on to their respective reactor.listenXXX or
reactor.connectXXX calls.

For example, the following service starts a web server on port 8080:
C{TCPServer(8080, server.Site(r))}.  See the documentation for the
reactor.listen/connect* methods for more information.
"""

from twisted.python import log
from twisted.application import service
from twisted.internet import task

from twisted.internet.defer import CancelledError


def _maybeGlobalReactor(maybeReactor):
    """
    @return: the argument, or the global reactor if the argument is C{None}.
    """
    if maybeReactor is None:
        from twisted.internet import reactor
        return reactor
    else:
        return maybeReactor


class _VolatileDataService(service.Service):

    volatile = []

    def __getstate__(self):
        d = service.Service.__getstate__(self)
        for attr in self.volatile:
            if attr in d:
                del d[attr]
        return d



class _AbstractServer(_VolatileDataService):
    """
    @cvar volatile: list of attribute to remove from pickling.
    @type volatile: C{list}

    @ivar method: the type of method to call on the reactor, one of B{TCP},
        B{UDP}, B{SSL} or B{UNIX}.
    @type method: C{str}

    @ivar reactor: the current running reactor.
    @type reactor: a provider of C{IReactorTCP}, C{IReactorUDP},
        C{IReactorSSL} or C{IReactorUnix}.

    @ivar _port: instance of port set when the service is started.
    @type _port: a provider of L{twisted.internet.interfaces.IListeningPort}.
    """

    volatile = ['_port']
    method = None
    reactor = None

    _port = None

    def __init__(self, *args, **kwargs):
        self.args = args
        if 'reactor' in kwargs:
            self.reactor = kwargs.pop("reactor")
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
        """
        Wrapper around the appropriate listen method of the reactor.

        @return: the port object returned by the listen method.
        @rtype: an object providing
            L{twisted.internet.interfaces.IListeningPort}.
        """
        return getattr(_maybeGlobalReactor(self.reactor),
                       'listen%s' % (self.method,))(*self.args, **self.kwargs)



class _AbstractClient(_VolatileDataService):
    """
    @cvar volatile: list of attribute to remove from pickling.
    @type volatile: C{list}

    @ivar method: the type of method to call on the reactor, one of B{TCP},
        B{UDP}, B{SSL} or B{UNIX}.
    @type method: C{str}

    @ivar reactor: the current running reactor.
    @type reactor: a provider of C{IReactorTCP}, C{IReactorUDP},
        C{IReactorSSL} or C{IReactorUnix}.

    @ivar _connection: instance of connection set when the service is started.
    @type _connection: a provider of L{twisted.internet.interfaces.IConnector}.
    """
    volatile = ['_connection']
    method = None
    reactor = None

    _connection = None

    def __init__(self, *args, **kwargs):
        self.args = args
        if 'reactor' in kwargs:
            self.reactor = kwargs.pop("reactor")
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
        """
        Wrapper around the appropriate connect method of the reactor.

        @return: the port object returned by the connect method.
        @rtype: an object providing L{twisted.internet.interfaces.IConnector}.
        """
        return getattr(_maybeGlobalReactor(self.reactor),
                       'connect%s' % (self.method,))(*self.args, **self.kwargs)



_doc={
'Client':
"""Connect to %(tran)s

Call reactor.connect%(tran)s when the service starts, with the
arguments given to the constructor.
""",
'Server':
"""Serve %(tran)s clients

Call reactor.listen%(tran)s when the service starts, with the
arguments given to the constructor. When the service stops,
stop listening. See twisted.internet.interfaces for documentation
on arguments to the reactor method.
""",
}

import types
for tran in 'TCP UNIX SSL UDP UNIXDatagram Multicast'.split():
    for side in 'Server Client'.split():
        if tran == "Multicast" and side == "Client":
            continue
        if tran == "UDP" and side == "Client":
            continue
        base = globals()['_Abstract'+side]
        doc = _doc[side] % vars()
        klass = types.ClassType(tran+side, (base,),
                                {'method': tran, '__doc__': doc})
        globals()[tran+side] = klass



class TimerService(_VolatileDataService):
    """
    Service to periodically call a function

    Every C{step} seconds call the given function with the given arguments.
    The service starts the calls when it starts, and cancels them
    when it stops.

    @ivar clock: Source of time. This defaults to L{None} which is
        causes L{twisted.internet.reactor} to be used.
        Feel free to set this to something else, but it probably ought to be
        set *before* calling L{startService}.
    @type clock: L{IReactorTime<twisted.internet.interfaces.IReactorTime>}

    @ivar call: Function and arguments to call periodically.
    @type call: L{tuple} of C{(callable, args, kwargs)}
    """

    volatile = ['_loop', '_loopFinished']

    def __init__(self, step, callable, *args, **kwargs):
        """
        @param step: The number of seconds between calls.
        @type step: L{float}

        @param callable: Function to call
        @type callable: L{callable}

        @param args: Positional arguments to pass to function
        @param kwargs: Keyword arguments to pass to function
        """
        self.step = step
        self.call = (callable, args, kwargs)
        self.clock = None

    def startService(self):
        service.Service.startService(self)
        callable, args, kwargs = self.call
        # we have to make a new LoopingCall each time we're started, because
        # an active LoopingCall remains active when serialized. If
        # LoopingCall were a _VolatileDataService, we wouldn't need to do
        # this.
        self._loop = task.LoopingCall(callable, *args, **kwargs)
        self._loop.clock = _maybeGlobalReactor(self.clock)
        self._loopFinished = self._loop.start(self.step, now=True)
        self._loopFinished.addErrback(self._failed)

    def _failed(self, why):
        # make a note that the LoopingCall is no longer looping, so we don't
        # try to shut it down a second time in stopService. I think this
        # should be in LoopingCall. -warner
        self._loop.running = False
        log.err(why)

    def stopService(self):
        """
        Stop the service.

        @rtype: L{Deferred<defer.Deferred>}
        @return: a L{Deferred<defer.Deferred>} which is fired when the
            currently running call (if any) is finished.
        """
        if self._loop.running:
            self._loop.stop()
        self._loopFinished.addCallback(lambda _:
                service.Service.stopService(self))
        return self._loopFinished



class CooperatorService(service.Service):
    """
    Simple L{service.IService} which starts and stops a L{twisted.internet.task.Cooperator}.
    """
    def __init__(self):
        self.coop = task.Cooperator(started=False)


    def coiterate(self, iterator):
        return self.coop.coiterate(iterator)


    def startService(self):
        self.coop.start()


    def stopService(self):
        self.coop.stop()



class StreamServerEndpointService(service.Service, object):
    """
    A L{StreamServerEndpointService} is an L{IService} which runs a server on a
    listening port described by an L{IStreamServerEndpoint
    <twisted.internet.interfaces.IStreamServerEndpoint>}.

    @ivar factory: A server factory which will be used to listen on the
        endpoint.

    @ivar endpoint: An L{IStreamServerEndpoint
        <twisted.internet.interfaces.IStreamServerEndpoint>} provider
        which will be used to listen when the service starts.

    @ivar _waitingForPort: a Deferred, if C{listen} has yet been invoked on the
        endpoint, otherwise None.

    @ivar _raiseSynchronously: Defines error-handling behavior for the case
        where C{listen(...)} raises an exception before C{startService} or
        C{privilegedStartService} have completed.

    @type _raiseSynchronously: C{bool}

    @since: 10.2
    """

    _raiseSynchronously = None

    def __init__(self, endpoint, factory):
        self.endpoint = endpoint
        self.factory = factory
        self._waitingForPort = None


    def privilegedStartService(self):
        """
        Start listening on the endpoint.
        """
        service.Service.privilegedStartService(self)
        self._waitingForPort = self.endpoint.listen(self.factory)
        raisedNow = []
        def handleIt(err):
            if self._raiseSynchronously:
                raisedNow.append(err)
            elif not err.check(CancelledError):
                log.err(err)
        self._waitingForPort.addErrback(handleIt)
        if raisedNow:
            raisedNow[0].raiseException()


    def startService(self):
        """
        Start listening on the endpoint, unless L{privilegedStartService} got
        around to it already.
        """
        service.Service.startService(self)
        if self._waitingForPort is None:
            self.privilegedStartService()


    def stopService(self):
        """
        Stop listening on the port if it is already listening, otherwise,
        cancel the attempt to listen.

        @return: a L{Deferred<twisted.internet.defer.Deferred>} which fires
            with C{None} when the port has stopped listening.
        """
        self._waitingForPort.cancel()
        def stopIt(port):
            if port is not None:
                return port.stopListening()
        d = self._waitingForPort.addCallback(stopIt)
        def stop(passthrough):
            self.running = False
            return passthrough
        d.addBoth(stop)
        return d



__all__ = (['TimerService', 'CooperatorService', 'MulticastServer',
            'StreamServerEndpointService', 'UDPServer'] +
           [tran+side
            for tran in 'TCP UNIX SSL UNIXDatagram'.split()
            for side in 'Server Client'.split()])
