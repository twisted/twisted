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

"""Interface documentation."""

from twisted.python.components import Interface

### Reactor Interfaces

class IReactorTCP(Interface):
    def listenTCP(self, port, factory, backlog=5, interface=''):
        """
        Connects a given protocol factory to the given numeric TCP/IP port.
        """

    def clientTCP(self, host, port, protocol, timeout=30):
        """Connect a TCP client.

        Arguments:

          * host: a host name

          * port: a port number

          * protocol: a twisted.internet.protocol.Protocol instance

          * timeout: amount of time to wait before assuming the connection has
            failed.
        """

class IReactorSSL(Interface):
    def clientSSL(self, host, port, protocol, contextFactory, timeout=30,):
        """Connect a client Protocol to a remote SSL socket.
        """

    def listenSSL(self, port, factory, ctxFactory, backlog=5, interface=''):
        """
        Connects a given protocol factory to the given numeric TCP/IP port.
        The connection is a SSL one, using contexts created by the context
        factory.
        """


class IReactorUNIX(Interface):
    """UNIX socket methods.
    """
    def clientUNIX(address, protocol, timeout=30):
        """Connect a client Protocol to a UNIX socket.
        """

    def listenUNIX(address, factory, backlog=5):
        """Listen on a UNIX socket.
        """


class IReactorUDP(Interface):
    """UDP socket methods.
    """
    def listenUDP(self, port, factory, interface='', maxPacketSize=8192):
        """Connects a given protocol Factory to the given numeric UDP port.

        Returns: something conforming to IListeningPort.
        """

##     I can't remember what I was thinking when I did this.  On the off chance
##     that someone else remembers, I'll leave it here, but I think it's going
##     away.
##     
##     def clientUDP(self, remotehost, remoteport, localport, protocol,
##                   interface='', maxPacketSize=8192):
##         """Connects a Protocol instance to a UDP client port.
##         """

## XXX TODO: expose udp.Port.createConnection more formally

class IReactorProcess(Interface):
    def spawnProcess(self, processProtocol, executable, args=(), env={}):
        """Spawn a process, with a process protcol.

        Arguments:

          * processProtocol: a ProcessProtocol instance

          * executable: the file name to spawn

          * args: the command line arguments to pass to the process; a sequence
            of strings.

          * env: the environment variables to pass to the processs; a
            dictionary of strings.

        See also:

          twisted.protocols.protocol.ProcessProtocol
        """

class IReactorTime(Interface):
    """Time methods that a Reactor should implement.
    """
    def callLater(self, delay, callable, *args, **kw):
        """Call a function later.

        Arguments:

          * delay: the number of seconds to wait.

          * callable: the callable object to call later.

          * *args: the arguments to call it with.

          * **kw: they keyword arguments to call it with.

        Returns:

          An ID that can be used to cancel the call, using cancelCallLater.
        """

    def cancelCallLater(self, callID):
        """Cancel a call that would happen later.

        Arguments:

          * callID: this is an opaque identifier returned from callLater that
            wil be used to cancel a specific call.
        """

class IReactorCore(Interface):
    """Core methods that a Reactor must implement.
    """

    def run(self):
        """Run the main loop until stop() is called.
        """

    def stop(self):
        """Stop the main loop by firing a 'shutdown' System Event.
        """

    def crash(self):
        """Stop the main loop *immediately*, without firing any system events.

        This is named as it is because this is an extremely "rude" thing to do;
        it is possible to lose data and put your system in an inconsistent
        state by calling this.  However, it is necessary, as sometimes a system
        can become wedged in a pre-shutdown call.
        """

    def iterate(self, delay=0):
        """Run the main loop's I/O polling function for a period of time.

        This is most useful in applications where the UI is being drawn "as
        fast as possible", such as games.
        """

    def callFromThread(self, callable, *args, **kw):
        """Call a function from within another thread.

        This should wake up the main thread (where run() is executing) and run
        the given function.

        I hope it is obvious from this description that this method must be
        thread safe.  (If you want to call a method in the next mainloop
        iteration, but you're in the same thread, use callLater with a delay of
        0.)
        """

    def fireSystemEvent(self, eventType):
        """Fire a system-wide event.

        System-wide events are things like 'startup', 'shutdown', and
        'persist'.
        """

    def addSystemEventTrigger(self, phase, eventType, callable, *args, **kw):
        """Add a function to be called when a system event occurs.

        Each "system event" in Twisted, such as 'startup', 'shutdown', and
        'persist', has 3 phases: 'before', 'during', and 'after' (in that
        order, of course).  These events will be fired internally by the
        Reactor.

        An implementor of this interface must only implement those events
        described here.

        Callbacks registered for the "before" phase may return either None or a
        Deferred.  The "during" phase will not execute until all of the
        Deferreds from the "before" phase have fired.

        Once the "during" phase is running, all of the remaining triggers must
        execute; their return values must be ignored.

        Arguments:

          * phase: a time to call the event -- either the string 'before',
            'after', or 'during', describing when to call it relative to the
            event's execution.

          * eventType: this is a string describing the type of event.  It 

          * callable: the object to call before shutdown.

          * *args: the arguments to call it with.

          * **kw: the keyword arguments to call it with.

        Returns:

          an ID that can be used to remove this call with
          removeSystemEventTrigger.
        """

    def removeSystemEventTrigger(self, triggerID):
        """Removes a trigger added with addSystemEventTrigger.

        Arguments:

          * triggerID: a value returned from addSystemEventTrigger.
        """

class IListeningPort(Interface):
    """A listening port.
    """

    def startListening(self):
        """Start listening on this port.
        """

    def stopListening(self):
        """Stop listening on this port.
        """

    def getHost(self):
        """Get the host that this port is listening for.

        Returns:

          a tuple of (proto_type, ...), where proto_type will be a string such
          as 'INET', 'SSL', 'UNIX'.  The rest of the tuple will be identifying
          information about the port.
        """

class IConsumer(Interface):
    """A consumer consumes data from a producer."""
    
    def registerProducer(self, producer, streaming):
        """Register to receive data from a producer.

        This sets self to be a consumer for a producer.  When this object
        runs out of data on a write() call, it will ask the producer
        to resumeProducing(). A producer should implement the IProducer
        interface.
        """
        raise NotImplementedError

    def unregisterProducer(self):
        """Stop consuming data from a producer, without disconnecting.
        """
        raise NotImplementedError

    def write(self, data):
        """The producer will write data by calling this method."""
        raise NotImplementedError


class IProducer(Interface):
    """A producer produces data for a consumer.
    
    If this is a streaming producer, it will only be
    asked to resume producing if it has been previously asked to pause.
    Also, if this is a streaming producer, it will ask the producer to
    pause when the buffer has reached a certain size.

    In other words, a streaming producer is expected to produce (write to
    this consumer) data in the main IO thread of some process as the result
    of a read operation, whereas a non-streaming producer is expected to
    produce data each time resumeProducing() is called.
    
    If this is a non-streaming producer, resumeProducing will be called
    immediately, to start the flow of data.  Otherwise it is assumed that
    the producer starts out life unpaused.
    """
    
    def resumeProducing(self):
        """Resume producing data.
        
        This tells a producer to re-add itself to the main loop and produce
        more data for its consumer.
        """
        raise NotImplementedError

    def pauseProducing(self):
        """Pause producing data.
        
        Tells a producer that it has produced too much data to process for
        the time being, and to stop until resumeProducing() is called.
        """
        raise NotImplementedError

    def stopProducing(self):
        """Stop producing data.
        
        This tells a producer that its consumer has died, so it must stop
        producing data for good.
        """
        raise NotImplementedError


class IConnector:
    """Connect this to that and make it stick."""

    transportFactory = None
    protocol = None
    factory = None

    def __init__(self, host, portno, protocolFactory, timeout=30):
        raise NotImplementedError

    def connectionFailed(self):
        raise NotImplementedError

    def connectionLost(self):
        raise NotImplementedError

    def startConnecting(self):
        raise NotImplementedError

    def getProtocol(self):
        """Get the current protocol instance."""
        raise NotImplementedError



class ISelectable(Interface):
    """An object that can be registered with the networking event loop.
    
    Selectables more or less correspond to object that can be passed to select().
    This is platform dependant, and not totally accurate, since the main event loop
    may not be using select().
    
    Selectables may be registered as readable by passing them to t.i.main.addReader(),
    and they may be registered as writable by passing them to t.i.main.addWriter().
    
    In general, selectables are expected to inherit from twisted.python.log.Logger.
    """
    
    def doWrite(self):
        """Called when data is available for writing.
        
        This will only be called if this object has been registered as a writer in
        the event loop.
        """
        raise NotImplementedError
    
    def doRead(self):
        """Called when data is available for reading.
        
        This will only be called if this object has been registered as a reader in
        the event loop.
        """
        raise NotImplementedError
    
    def fileno(self):
        """Return a file descriptor number for select().

        This method must return an integer, the object's file descriptor.
        """
        raise NotImplementedError
    
    def connectionLost(self):
        """Called if an error has occured or the object's connection was closed.
        
        This may be called even if the connection was never opened in the first place.
        """
        raise NotImplementedError


__all__ = ["IProducer", "ISelectable", "IConsumer"]
