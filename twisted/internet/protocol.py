
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

"""Primary interfaces for the twisted protocols collection.

Start here if you are looking to write a new protocol implementation for
Twisted Python.  The Protocol class contains some introductory material.
"""

# Twisted Imports
from twisted.python import log, failure
from twisted.internet import interfaces, error


class Factory:
    """This is a factory which produces protocols.

    By default, buildProtocol will create a protocol of the class given in
    self.protocol.
    """

    __implements__ = (interfaces.IProtocolFactory,)

    # put a subclass of Protocol here:
    protocol = None

    numPorts = 0

    def doStart(self):
        """Make sure startFactory is called."""
        if not self.numPorts:
            log.msg("Starting factory %s" % self)
            self.startFactory()
        self.numPorts = self.numPorts + 1

    def doStop(self):
        """Make sure stopFactory is called."""
        assert self.numPorts > 0
        self.numPorts = self.numPorts - 1
        if not self.numPorts:
            log.msg("Stopping factory %s" % self)
            self.stopFactory()
    
    def startFactory(self):
        """This will be called before I begin listening on a Port or Connector.

        It will only be called once, even if the factory is connected
        to multiple ports.
        
        This can be used to perform 'unserialization' tasks that
        are best put off until things are actually running, such
        as connecting to a database, opening files, etcetera.
        """

    def stopFactory(self):
        """This will be called before I stop listening on all Ports/Connectors.

        This can be used to perform 'shutdown' tasks such as disconnecting
        database connections, closing files, etc.

        It will be called, for example, before an application shuts down,
        if it was connected to a port.
        """

    def buildProtocol(self, addr):
        """Create an instance of a subclass of Protocol.

        The returned instance will handle input on an incoming server
        connection, and an attribute \"factory\" pointing to the creating
        factory.

        Override this method to alter how Protocol instances get created.
        """
        p = self.protocol()
        p.factory = self
        return p


class ClientFactory(Factory):
    """A Protocol factory for clients.

    This can be used together with the various connectXXX methods in
    reactors and Applications.
    """

    def startedConnecting(self, connector):
        """Called when a connection has been started.

        Arguments:
           - connector: a Connector object.

        You can call connector.stopConnecting() to stop the connection attempt.
        """

    def clientConnectionFailed(self, connector, reason):
        """Called when a connection has failed.

        It may be useful to call connector.connect() - this will reconnect.

        reason is a Failure object.
        """

    def clientConnectionLost(self, connector, reason):
        """Called when a connection is lost.

        It may be useful to call connector.connect() - this will reconnect.

        reason is a Failure object.
        """
        

class ServerFactory(Factory):
    """Subclass this to indicate that your protocol.Factory is only usable for servers.
    """

class Protocol:
    """This is the abstract superclass of all protocols.

    If you are going to write a new protocol for Twisted, start here.  The
    docstrings of this class explain how you can get started.  Any protocol
    implementation, either client or server, should be a subclass of me.

    My API is quite simple.  Implement dataReceived(data) to handle both
    event-based and synchronous input; output can be sent through the
    'transport' attribute, which is to be an instance of a
    twisted.protocols.protocol.Transport.

    Some subclasses exist already to help you write common types of protocols:
    see the twisted.protocols.basic module for a few of them.
    """

    connected = 0
    transport = None

    def makeConnection(self, transport):
        """Make a connection to a transport and a server.

        This sets the 'transport' attribute of this Protocol, and calls the
        connectionMade() callback.
        """
        self.connected = 1
        self.transport = transport
        self.connectionMade()

    def connectionMade(self):
        """Called when a connection is made.

        This may be considered the initializer of the protocol, because
        it is called when the connection is completed.  For clients,
        this is called once the connection to the server has been
        established; for servers, this is called after an accept() call
        stops blocking and a socket has been received.  If you need to
        send any greeting or initial message, do it here.
        """

    def dataReceived(self, data):
        """Called whenever data is received.

        'data' will be a string of indeterminate length.  Please keep in
        mind that you will probably need to buffer some data, as partial
        protocol messages may be received!  Use this method to translate
        to a higher-level message.  Usually, some callback will be made
        upon the receipt of each complete protocol message.

        I recommend that unit tests for protocols call through to this
        method with differing chunk sizes, down to one byte at a time.
        """

    def connectionLost(self, reason=failure.Failure(error.ConnectionDone())):
        """Called when the connection is shut down.

        Clear any circular references here, and any external references
        to this Protocol.  The connection has been closed.

        reason is a Failure object.
        """

    def connectionFailed(self):
        """(Deprecated)

        This used to be called when the connection was not properly
        established.
        """
        import warnings
        warnings.warn("connectionFailed is deprecated.  See new Client API",
                      category=DeprecationWarning, stacklevel=2)



class ProcessProtocol(Protocol):
    """Processes have some additional methods besides receiving data.

    data* and connection* methods from Protocol are used for stdout, but stderr
    and process signals are supported below.
    """
    def errReceived(self, data):
        """Some data was received from stderr.
        """

    def errConnectionLost(self):
        """This will be called when stderr is closed.
        """

    def connectionLost(self):
        """Called when stdout is shut down."""

    def processEnded(self):
        """This will be called when the subprocess is finished.
        """


class FileWrapper:
    """A wrapper around a file-like object to make it behave as a Transport.
    """

    __implements__ = interfaces.ITransport
    
    closed = 0
    disconnecting = 0
    producer = None
    streamingProducer = 0
    
    def __init__(self, file):
        self.file = file

    def write(self, data):
        try:
            self.file.write(data)
        except:
            self.handleException()
        # self._checkProducer()

    def _checkProducer(self):
        # Cheating; this is called at "idle" times to allow producers to be
        # found and dealt with
        if self.producer:
            self.producer.resumeProducing()

    def registerProducer(self, producer, streaming):
        """From abstract.FileDescriptor
        """
        self.producer = producer
        self.streamingProducer = streaming
        if not streaming:
            producer.resumeProducing()

    def unregisterProducer(self):
        self.producer = None

    def stopConsuming(self):
        self.unregisterProducer()
        self.loseConnection()

    def writeSequence(self, iovec):
        self.write("".join(iovec))

    def loseConnection(self):
        self.closed = 1
        try:
            self.file.close()
        except (IOError, OSError):
            self.handleException()

    def getPeer(self):
        return 'file', 'file'

    def getHost(self):
        return 'file'

    def handleException(self):
        pass
