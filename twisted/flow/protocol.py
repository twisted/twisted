# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.

#
# Author: Clark Evans
#

"""
flow.protocol

This allows one to use flow module to create protocols, a protocol is actually
a controller, but it is specialized enough to deserve its own module.
"""

import types
from base import *
from wrap import wrap
from stage import Callback
from twisted.internet import protocol
from twisted.internet.error import ConnectionLost, ConnectionDone

def makeProtocol(controller, baseClass = protocol.Protocol,
                  *callbacks, **kwargs):
    """
    Construct a flow based protocol

    This takes a base protocol class, and a set of callbacks and creates a
    connection flow based on the two.  For example, the following would build a
    simple 'echo' protocol::

        from __future__ import generators
        from twisted.internet import reactor, protocol
        from twisted.flow import flow
        PORT = 8392

        def echoServer(conn):
            yield conn
            for data in conn:
                conn.write(data)
                yield conn

        def echoClient(conn):
            conn.write("hello, world!")
            yield conn
            print "server said: ", conn.next()
            reactor.callLater(0,reactor.stop)

        server = protocol.ServerFactory()
        server.protocol = flow.makeProtocol(echoServer)
        reactor.listenTCP(PORT,server)
        client = protocol.ClientFactory()
        client.protocol = flow.makeProtocol(echoClient)
        reactor.connectTCP("localhost", PORT, client)
        reactor.run()

    Of course, the best part about flow is that you can nest stages.  Therefore
    it is quite easy to make a lineBreaker generator which takes an input
    connection and produces and output connection.  Anyway, the code is almost
    identical as far as the client/server is concerned::

        # this is a filter generator, it consumes from the
        # incoming connection, and yields results to
        # the next stage, the echoServer below
        def lineBreaker(conn, lineEnding = "\\n"):
            lst = []
            yield conn
            for chunk in conn:
               pos = chunk.find(lineEnding)
               if pos > -1:
                   lst.append(chunk[:pos])
                   yield "".join(lst)
                   lst = [chunk[pos+1:]]
               else:
                   lst.append(chunk)
               yield conn
            yield "".join(lst)

        # note that this class is only slightly modified,
        # simply comment out the line breaker line to see
        # how the server behaves without the filter...
        def echoServer(conn):
            lines = flow.wrap(lineBreaker(conn))
            yield lines
            for data in lines:
                conn.write(data)
                yield lines

        # and the only thing that is changed is that we
        # are sending data in strange chunks, and even
        # putting the last chunk on hold for 2 seconds.
        def echoClient(conn):
            conn.write("Good Morning!\\nPlease ")
            yield conn
            print "server said: ", conn.next()
            conn.write("do not disregard ")
            reactor.callLater(2, conn.write, "this.\\n")
            yield conn
            print "server said: ", conn.next()
            reactor.callLater(0,reactor.stop)
    """
    if not callbacks:
        callbacks = ('dataReceived',)
    trap = kwargs.get("trap", tuple())
    class _Protocol(Controller, Callback, baseClass):
        def __init__(self):
            Callback.__init__(self, *trap)
            setattr(self, callbacks[0], self)  
            # TODO: support more than one callback via Concurrent
        def _execute(self, dummy = None):
            cmd = self._controller
            self.write = self.transport.write
            while True:
                instruction = cmd._yield()
                if instruction:
                    if isinstance(instruction, CallLater):
                        instruction.callLater(self._execute)
                        return
                    raise Unsupported(instruction)
                if cmd.stop:
                    self.transport.loseConnection()
                    return
                if cmd.failure:
                    self.transport.loseConnection()
                    cmd.failure.trap()
                    return
                if cmd.results:
                    self.transport.writeSequence(cmd.results)
                    cmd.results = []
        def connectionMade(self):
            if types.ClassType == type(self.controller):
                self._controller = wrap(self.controller(self))
            else:
                self._controller = wrap(self.controller())
            self._execute()
        def connectionLost(self, reason=protocol.connectionDone):
            if isinstance(reason.value, ConnectionDone) or \
               (isinstance(reason.value, ConnectionLost) and \
                self.finishOnConnectionLost):
                self.finish()
            else:
                self.errback(reason)
            self._execute()
    _Protocol.finishOnConnectionLost = kwargs.get("finishOnConnectionLost",True)
    _Protocol.controller = controller
    return _Protocol

def _NotImplController(protocol):
    raise NotImplementedError
Protocol = makeProtocol(_NotImplController) 
Protocol.__doc__ = """ A concrete flow.Protocol for inheritance """

