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
        """Connects a given protocol factory to the given numeric TCP/IP port.
        """

    def clientTCP(self, host, port, protocol, timeout=30):
        """Connect a TCP client.

        Arguments:

          * host: a host name

          * port: a port number

          * protocol: a twisted.internet.protocol.Protocol instance

          * timeout: number of seconds to wait before assuming the connection
            has failed.
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

    def spawnProcess(self, processProtocol, executable, args=(), env={}, path=None, uid=None, gid=None):
        """Spawn a process, with a process protcol.

        Arguments:

          * processProtocol: a ProcessProtocol instance

          * executable: the file name to spawn - the full path should be used.

          * args: the command line arguments to pass to the process; a sequence
            of strings. The first string should be the executable's name.

          * env: the environment variables to pass to the processs; a
            dictionary of strings.

          * path: the path to run the subprocess in - defaults to the current directory.

          * uid: user ID to run the subprocess as.

          * gid: group ID to run the subprocess as.

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
	
	Will raise ValueError if the callID is not recognized.
        """


class IReactorThreads(Interface):
    """Dispatch methods to be run in threads.

    Internally, this should use a thread pool and dispatch methods to them.
    """

    def callInThread(self, callable, *args, **kwargs):
        """Run the callable object in a separate thread.
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

    def suggestThreadPoolSize(self, size):
        """Suggest the size of the thread pool.
        """


class IReactorCore(Interface):
    """Core methods that a Reactor must implement.
    """

    def resolve(self, name, type=1, timeout=10):
        """Return a Deferred that will resolve a hostname.
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


class IReactorFDSet(Interface):
    """Implement me to be able to use FileDescriptor type resources.

    This assumes that your main-loop uses UNIX-style numeric file descriptors
    (or at least similarly opaque IDs returned from a .fileno() method)
    """

    def addReader(self, reader):
        """addReader(IReadDescriptor) -> None
        """

    def addWriter(self, writer):
        """addWriter(IWriteDescriptor) -> None
        """

    def removeReader(self, reader):
        """removeReader(IReadDescriptor) -> None
        """

    def removeWriter(self, writer):
        """removeWriter(IWriteDescriptor) -> None
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


class IFileDescriptor(Interface):
    """A file descriptor.
    """

    def fileno(self):
        """fileno() -> int

        Returns: the platform-specified representation of a file-descriptor
        number.
        """

class IReadDescriptor(IFileDescriptor):

    def doRead(self):
        """Some data is available for reading on your descriptor.
        """


class IWriteDescriptor(IFileDescriptor):

    def doWrite(self):
        """Some data is available for reading on your descriptor.
        """


class IReadWriteDescriptor(IReadDescriptor, IWriteDescriptor):
    """I am a FileDescriptor that can both read and write.
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

    def unregisterProducer(self):
        """Stop consuming data from a producer, without disconnecting.
        """

    def write(self, data):
        """The producer will write data by calling this method."""


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

    def pauseProducing(self):
        """Pause producing data.

        Tells a producer that it has produced too much data to process for
        the time being, and to stop until resumeProducing() is called.
        """

    def stopProducing(self):
        """Stop producing data.

        This tells a producer that its consumer has died, so it must stop
        producing data for good.
        """


class IConnector(Interface):
    """Connect this to that and make it stick."""

    def getProtocol(self):
        """Get the current protocol instance."""


class IProtocolFactory(Interface):
    """Interface for protocol factories.
    """

    def buildProtocol(self, addr):
        """Return an object implementing IProtocol, or None.

        This method will be called when a connection has been established
        to addr.
        
        If None is returned, the connection is assumed to have been refused,
        and the Port will close the connection.
        
        TODO:
         * Document 'addr' argument -- what format is it in?
         * Is the phrase \"incoming server connection\" correct when Factory
           is a ClientFactory?
        """

    def doStart(self):
        """Called every time this is connected to a Port or Connector."""

    def doStop(self):
        """Called every time this is unconnected from a Port or Connector."""


class ITransport(Interface):
    """I am a transport for bytes.

    I represent (and wrap) the physical connection and synchronicity
    of the framework which is talking to the network.  I make no
    representations about whether calls to me will happen immediately
    or require returning to a control loop, or whether they will happen
    in the same or another thread.  Consider methods of this class
    (aside from getPeer) to be 'thrown over the wall', to happen at some
    indeterminate time.
    """

    def write(self, data):
        '''Write some data to the physical connection, in sequence.

        If possible, make sure that it is all written.  No data will
        ever be lost, although (obviously) the connection may be closed
        before it all gets through.
        '''

    def loseConnection(self):
        """Close my connection, after writing all pending data.
        """

    def getPeer(self):
        '''Return a tuple of (TYPE, ...).

        This indicates the other end of the connection.  TYPE indicates
        what sort of connection this is: "INET", "UNIX", or something
        else.  "INET" tuples have 2 additional elements; hostname and
        port.

        Treat this method with caution.  It is the unfortunate
        result of the CGI and Jabber standards, but should not
        be considered reliable for the usual host of reasons;
        port forwarding, proxying, firewalls, IP masquerading,
        etcetera.
        '''

    def getHost(self):
        """
        Similar to getPeer, but returns a tuple describing this side of the
        connection.
        """


class ITCPTransport(ITransport):
    """A TCP based transport."""

    def getTcpNoDelay(self):
        """Return if TCP_NODELAY (Nagle's algorithm) is enabled."""

    def setTcpNoDelay(self, enabled):
        """Enable/disable TCP_NODELAY (Nagle's algorithm)."""


class ISSLTransport(ITCPTransport):
    """A SSL/TLS based transport."""

    def getPeerCertificate(self):
        """Return an object with the peer's certificate info."""
