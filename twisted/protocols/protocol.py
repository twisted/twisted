
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

from twisted.python import log

class Factory:
    """This is a factory which produces protocols.

    This interface only requires that you implement one method; buildProtocol.
    By default, this will create a protocol of the class given in
    self.protocol.
    """
    protocol = None

    def startFactory(self):
        """This will be called before I begin listening on a Port.

        This can be used to perform 'unserialization' tasks that
        are best put off until things are actually running, such
        as connecting to a database, opening files, etcetera.

        It will be called both after an application has been unserialized and
        before all the ports begin accepting connections.
        """

    def stopFactory(self):
        """This will be called before I stop listening on a Port.

        This can be used to perform 'shutdown' tasks such as disconnecting
        database connections, closing files, etc.

        It will be called before an application shuts down.
        """

    def buildProtocol(self, connection):
        """Create an instance of a subclass of Protocol.

        The returned instance will handle input on an incoming server
        connection, and an attribute "factory" pointing to the creating
        factory. If None is returned, the connection is assumed to have
        been refused, and the Port will close the connection.
        
        Override this method to alter how Protocol instances get created.
        """
        p = self.protocol()
        p.factory = self
        return p


class ClientFactory(Factory):
    """Subclass this to indicate that your protocol.Factory is only usable for clients.
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
    server = None

    def makeConnection(self, transport, server = None):
        """Make a connection to a transport and a server.

        This sets the 'transport' (and 'server'; the jury is still out as to
        whether this will remain) attributes of this Protocol, and calls the
        connectionMade() callback.
        """
        self.connected = 1
        self.transport = transport
        self.server = server
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

    def connectionLost(self):
        """Called when the connection is shut down.

        Clear any circular references here, and any external references
        to this Protocol.  The connection has been closed.
        """

    def connectionFailed(self):
        """Called when a connection cannot be made.

        This will only be called on client protocols; this message tells
        the protocol that the expected connection can not be made.
        """
        log.msg( 'Connection Failed!' )


class Transport:
    """I am a transport for bytes.

    I represent (and wrap) the physical connection and synchronicity
    of the framework which is talking to the network.  I make no
    representations about whether calls to me will happen immediately
    or require returning to a control loop, or whether they will happen
    in the same or another thread.  Consider methods of this class
    (aside from getPeer) to be 'thrown over the wall', to happen at some
    indeterminate time.
    """

    disconnecting = 0

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


class FileWrapper(Transport):
    """A wrapper around a file-like object to make it behave as a Transport.
    """
    def __init__(self, file):
        self.file = file

    def write(self, data):
        self.file.write(data)

    def loseConnection(self):
        try:
            self.file.close()
        except (IOError, OSError):
            self.handleException()

    def getPeer(self):
        return 'file', self.file.name

    def handleException(self):
        pass
