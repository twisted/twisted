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

"""Interface documentation.

API Stability: stable, other than IReactorUDP

Maintainer: U{Itamar Shtull-Trauring<mailto:twisted@itamarst.org>}
"""

from twisted.python.components import Interface


### Reactor Interfaces

class IConnector(Interface):
    """Object used to interface between connections and protocols.

    Each IConnector manages one connection.
    """

    def stopConnecting(self):
        """Stop attempting to connect."""

    def disconnect(self):
        """Disconnect regardless of the connection state.

        If we are connected, disconnect, if we are trying to connect,
        stop trying.
        """

    def connect(self):
        """Try to connect to remote address."""

    def getDestination(self):
        """Return destination this will try to connect to.

        This can be one of:
          TCP -- ('INET', host, port)
          UNIX -- ('UNIX', address)
          SSL -- ('SSL', host, port)
        """


class IReactorTCP(Interface):

    def listenTCP(self, port, factory, backlog=5, interface=''):
        """Connects a given protocol factory to the given numeric TCP/IP port.

       @returns: an object that satisfies the IListeningPort interface

       @raise CannotListenError: as defined in twisted.internet.error, if it
          cannot listen on this port (e.g., it cannot bind to the required port
          number)
        """

    def connectTCP(self, host, port, factory, timeout=30, bindAddress=None):
        """Connect a TCP client.

        @param host: a host name

        @param port: a port number

        @param factory: a twisted.internet.protocol.ClientFactory instance

        @param timeout: number of seconds to wait before assuming the
                        connection has failed.

        @param bindAddress: a (host, port) tuple of local address to bind
                            to, or None.

        @returns:  An object implementing IConnector. This connector will call
           various callbacks on the factory when a connection is made,
           failed, or lost - see ClientFactory docs for details.
        """


class IReactorSSL(Interface):

    def connectSSL(self, host, port, factory, contextFactory, timeout=30, bindAddress=None):
        """Connect a client Protocol to a remote SSL socket.

        Arguments:

          * host: a host name

          * port: a port number

          * factory: a twisted.internet.protocol.ClientFactory instance

          * contextFactory: a twisted.internet.ssl.ContextFactory object.

          * timeout: number of seconds to wait before assuming the connection
            has failed.

          * bindAddress: a (host, port) tuple of local address to bind to, or
            None.

        @returns: an L{IConnector}.
        """

    def listenSSL(self, port, factory, ctxFactory, backlog=5, interface=''):
        """
        Connects a given protocol factory to the given numeric TCP/IP port.
        The connection is a SSL one, using contexts created by the context
        factory.
        """


class IReactorUNIX(Interface):
    """UNIX socket methods."""

    def connectUNIX(self, address, factory, timeout=30):
        """Connect a client protocol to a UNIX socket.

        Arguments:

          * address: a path to a unix socket on the filesystem.

          * factory: a twisted.internet.protocol.ClientFactory instance

          * timeout: number of seconds to wait before assuming the connection
            has failed.

        @returns: an L{IConnector}.
        """

    def listenUNIX(address, factory, backlog=5):
        """Listen on a UNIX socket.

        Arguments:

          * address: a path to a unix socket on the filesystem.

          * factory: a twisted.internet.protocol.Factory instance.

          * backlog: number of connections to allow in backlog.
        """


class IReactorUDP(Interface):
    """UDP socket methods.

    IMPORTANT: This interface is not stable! It will very likely change
    in the future. Suggestions on how to support UDP in a nice way
    will be much appreciated.
    """
    
    def listenUDP(self, port, factory, interface='', maxPacketSize=8192):
        """Connects a given protocol Factory to the given numeric UDP port.

        @returns: something conforming to IListeningPort.
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

    def spawnProcess(self, processProtocol, executable, args=(), env={}, path=None, uid=None, gid=None, usePTY=0):
        """Spawn a process, with a process protcol.

        @param processProtocol: a ProcessProtocol instance

        @param executable: the file name to spawn - the full path should be
                           used.

        @param args: the command line arguments to pass to the process; a
                     sequence of strings. The first string should be the
                     executable's name.

        @param env: the environment variables to pass to the processs; a
                    dictionary of strings.

        @param path: the path to run the subprocess in - defaults to the
                     current directory.
        
        @param uid: user ID to run the subprocess as. (Only available on
                    POSIX systems.)

        @param gid: group ID to run the subprocess as. (Only available on
                    POSIX systems.)

        @param usePTY: if true, run this process in a psuedo-terminal. 
                       (Not available on all systems.)

        @see: C{twisted.protocols.protocol.ProcessProtocol}
        """

    def getProcessOutput(self, executable, args=(), env={}, path='.'):
        """Spawn a process and return its output as a single string.

        @param executable: The file name to run and get the output of - the
                           full path should be used.

        @param args: the command line arguments to pass to the process; a
                     sequence of strings. The first string should be the
                     executable's name.

        @param env: the environment variables to pass to the processs; a
                    dictionary of strings.

        @param path: the path to run the subprocess in - defaults to the
                     current directory.
        """


class IReactorTime(Interface):
    """Time methods that a Reactor should implement.
    """
    def callLater(self, delay, callable, *args, **kw):
        """Call a function later.

        @type delay:  C{float}
        @param delay: the number of seconds to wait.

        @param callable: the callable object to call later.

        @param args: the arguments to call it with.

        @param kw: they keyword arguments to call it with.

        @returns: An L{IDelayedCall} object that can be used to cancel
                  the scheduled call, by calling its C{cancel()} method.
        """

    def cancelCallLater(self, callID):
        """This method is deprecated.
        
        Cancel a call that would happen later.

        Arguments:

        @param callID: this is an opaque identifier returned from C{callLater}
                       that will be used to cancel a specific call.
	
	@raise ValueError: if the callID is not recognized.
        """


class IDelayedCall(Interface):
    """A scheduled call.

    There are probably other useful methods we can add to this interface,
    suggestions are welcome.
    """

    def cancel(self):
        """Cancel the scheduled call.

        Will raise twisted.internet.error.AlreadyCalled if the call has already
        happened.  Will raise twisted.internet.error.AlreadyCanceled if the
        call has already been cancelled.
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

        It's also useful since you can still run() the event loop again after
        this has been called, unlike stop(), so it's useful for test code
        that uses the reactor.
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

        @param phase: a time to call the event -- either the string 'before',
                      'after', or 'during', describing when to call it
                      relative to the event's execution.

        @param eventType: this is a string describing the type of event.

        @param callable: the object to call before shutdown.

        @param args: the arguments to call it with.

        @param kw: the keyword arguments to call it with.

        @returns: an ID that can be used to remove this call with
                  removeSystemEventTrigger.
        """

    def removeSystemEventTrigger(self, triggerID):
        """Removes a trigger added with addSystemEventTrigger.

        @param triggerID: a value returned from addSystemEventTrigger.
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

        @raise CannotListenError: as defined in C{twisted.internet.error},
                                  if it cannot listen on this port (e.g.,
                                  it is a TCP port and it cannot bind to
                                  the required port number)
        """

    def stopListening(self):
        """Stop listening on this port.
        """

    def getHost(self):
        """Get the host that this port is listening for.

        @returns: a tuple of C{(proto_type, ...)}, where proto_type will be
                  a string such as 'INET', 'SSL', 'UNIX'.  The rest of the
                  tuple will be identifying information about the port.
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
          - Document 'addr' argument -- what format is it in?
          - Is the phrase \"incoming server connection\" correct when Factory
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
        """Write some data to the physical connection, in sequence.

        If possible, make sure that it is all written.  No data will
        ever be lost, although (obviously) the connection may be closed
        before it all gets through.
        """

    def writeSequence(self, data):
        """Write a list of strings to the physical connection.

        If possible, make sure that all of the data is written to
        the socket at once, without first copying it all into a
        single string.
        """

    def loseConnection(self):
        """Close my connection, after writing all pending data.
        """

    def getPeer(self):
        '''Return a tuple of (TYPE, ...).

        This indicates the other end of the connection.  TYPE indicates
        what sort of connection this is: "INET", "UNIX", or something
        else.

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
        """Return if TCP_NODELAY is enabled."""

    def setTcpNoDelay(self, enabled):
        """Enable/disable TCP_NODELAY.

        Enabling TCP_NODELAY turns off Nagle's algorithm."""

    def getHost(self):
        """Returns tuple ('INET', host, port)."""

    def getPeer(self):
        """Returns tuple ('INET', host, port)."""


class ISSLTransport(ITCPTransport):
    """A SSL/TLS based transport."""

    def getPeerCertificate(self):
        """Return an object with the peer's certificate info."""


class IProcessTransport(ITransport):
    """A process transport."""

    def closeStdin(self):
        """Close stdin after all data has been written out."""

    def closeStdout(self):
        """Close stdout."""

    def closeStderr(self):
        """Close stderr."""

    def loseConnection(self):
        """Close stdin, stderr and stdout."""


class IServiceCollection(Interface):
    """An object which provides access to a collection of services."""
    pass
