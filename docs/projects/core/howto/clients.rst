
:LastChangedDate: $LastChangedDate$
:LastChangedRevision: $LastChangedRevision$
:LastChangedBy: $LastChangedBy$

Writing Clients
===============

Overview
--------
Twisted is a framework designed to be very flexible, and let you write
powerful clients. The cost of this flexibility is a few layers in the way
to writing your client. This document covers creating clients that can be
used for TCP, SSL and Unix sockets. UDP is covered :doc:`in a different document <udp>` .

At the base, the place where you actually implement the protocol parsing
and handling, is the ``Protocol`` class. This class will usually be
descended
from :api:`twisted.internet.protocol.Protocol <twisted.internet.protocol.Protocol>` . Most
protocol handlers inherit either from this class or from one of its
convenience children. An instance of the protocol class will be instantiated
when you connect to the server and will go away when the connection is
finished.  This means that persistent configuration is not saved in the
``Protocol`` .

The persistent configuration is kept in a ``Factory`` class,
which usually inherits from :api:`twisted.internet.protocol.Factory <twisted.internet.protocol.Factory>`
(or :api:`twisted.internet.protocol.ClientFactory <twisted.internet.protocol.ClientFactory>` : see below).
The default factory class just instantiates the ``Protocol`` and then sets the protocol's ``factory`` attribute to point to itself (the factory).
This lets the ``Protocol`` access, and possibly modify, the persistent configuration.

Protocol
--------
As mentioned above, this and auxiliary classes and functions are where
most of the code is. A Twisted protocol handles data in an asynchronous
manner. This means that the protocol never waits for an event, but rather
responds to events as they arrive from the network.

Here is a simple example:

.. code-block:: python

    from twisted.internet.protocol import Protocol
    from sys import stdout

    class Echo(Protocol):
        def dataReceived(self, data):
            stdout.write(data)

This is one of the simplest protocols.  It just writes whatever it reads
from the connection to standard output. There are many events it does not
respond to. Here is an example of a ``Protocol`` responding to
another event:

.. code-block:: python

    from twisted.internet.protocol import Protocol

    class WelcomeMessage(Protocol):
        def connectionMade(self):
            self.transport.write("Hello server, I am the client!\r\n")
            self.transport.loseConnection()

This protocol connects to the server, sends it a welcome message, and
then terminates the connection.

The :api:`twisted.internet.protocol.BaseProtocol.connectionMade <connectionMade>` event is
usually where set up of the ``Protocol`` object happens, as well as
any initial greetings (as in the
``WelcomeMessage`` protocol above). Any tearing down of
``Protocol`` -specific objects is done in :api:`twisted.internet.protocol.Protocol.connectionLost <connectionLost>` .

Simple, single-use clients
--------------------------
In many cases, the protocol only needs to connect to the server once,
and the code just wants to get a connected instance of the protocol. In
those cases :api:`twisted.internet.endpoints <twisted.internet.endpoints>` provides
the appropriate API, and in particular :api:`twisted.internet.endpoints.connectProtocol <connectProtocol>` which takes a
protocol instance rather than a factory.

.. code-block:: python

    from twisted.internet import reactor
    from twisted.internet.protocol import Protocol
    from twisted.internet.endpoints import TCP4ClientEndpoint, connectProtocol

    class Greeter(Protocol):
        def sendMessage(self, msg):
            self.transport.write("MESSAGE %s\n" % msg)

    def gotProtocol(p):
        p.sendMessage("Hello")
        reactor.callLater(1, p.sendMessage, "This is sent in a second")
        reactor.callLater(2, p.transport.loseConnection)

    point = TCP4ClientEndpoint(reactor, "localhost", 1234)
    d = connectProtocol(point, Greeter())
    d.addCallback(gotProtocol)
    reactor.run()

Regardless of the type of client endpoint, the way to set up a new
connection is simply pass it to :api:`twisted.internet.endpoints.connectProtocol <connectProtocol>` along with a
protocol instance.  This means it's easy to change the mechanism you're
using to connect, without changing the rest of your program.  For example,
to run the greeter example over SSL, the only change required is to
instantiate an
:api:`twisted.internet.endpoints.SSL4ClientEndpoint <SSL4ClientEndpoint>` instead of a
``TCP4ClientEndpoint`` .  To take advantage of this, functions and
methods which initiates a new connection should generally accept an
endpoint as an argument and let the caller construct it, rather than taking
arguments like 'host' and 'port' and constructing its own.

For more information on different ways you can make outgoing connections
to different types of endpoints, as well as parsing strings into endpoints,
see :doc:`the documentation for the endpoints API <endpoints>` .

You may come across code using :api:`twisted.internet.protocol.ClientCreator <ClientCreator>` , an older API which is not as flexible as
the endpoint API.  Rather than calling ``connect`` on an endpoint,
such code will look like this:

.. code-block:: python

    from twisted.internet.protocol import ClientCreator

    ...

    creator = ClientCreator(reactor, Greeter)
    d = creator.connectTCP("localhost", 1234)
    d.addCallback(gotProtocol)
    reactor.run()

In general, the endpoint API should be preferred in new code, as it lets
the caller select the method of connecting.

ClientFactory
-------------
Still, there's plenty of code out there that uses lower-level APIs, and
a few features (such as automatic reconnection) have not been
re-implemented with endpoints yet, so in some cases they may be more
convenient to use.

To use the lower-level connection APIs, you will need to call one of the *reactor.connect** methods directly.
For these cases, you need a :api:`twisted.internet.protocol.ClientFactory <ClientFactory>` .
The ``ClientFactory`` is in charge of creating the ``Protocol`` and also receives events relating to the connection state.
This allows it to do things like reconnect in the event of a connection error.
Here is an example of a simple ``ClientFactory`` that uses the ``Echo`` protocol (above) and also prints what state the connection is in.

.. code-block:: python

    from twisted.internet.protocol import Protocol, ClientFactory
    from sys import stdout

    class Echo(Protocol):
        def dataReceived(self, data):
            stdout.write(data)

    class EchoClientFactory(ClientFactory):
        def startedConnecting(self, connector):
            print 'Started to connect.'

        def buildProtocol(self, addr):
            print 'Connected.'
            return Echo()

        def clientConnectionLost(self, connector, reason):
            print 'Lost connection.  Reason:', reason

        def clientConnectionFailed(self, connector, reason):
            print 'Connection failed. Reason:', reason

To connect this ``EchoClientFactory`` to a server, you could use
this code:

.. code-block:: python

    from twisted.internet import reactor
    reactor.connectTCP(host, port, EchoClientFactory())
    reactor.run()

Note that :api:`twisted.internet.protocol.ClientFactory.clientConnectionFailed <clientConnectionFailed>` is called when a connection could not be established,
and that :api:`twisted.internet.protocol.ClientFactory.clientConnectionLost <clientConnectionLost>` is called when a connection was made and then disconnected.

Reactor Client APIs
~~~~~~~~~~~~~~~~~~~

connectTCP
''''''''''

:api:`twisted.internet.interfaces.IReactorTCP.connectTCP <IReactorTCP.connectTCP>` provides support for IPv4 and IPv6 TCP clients.
The ``host`` argument it accepts can be either a hostname or an IP address literal.
In the case of a hostname, the reactor will automatically resolve the name to an IP address before attempting the connection.
This means that for a hostname with multiple address records, reconnection attempts may not always go to the same server (see below).
It also means that there is name resolution overhead for each connection attempt.
If you are creating many short-lived connections (typically around hundreds or thousands per second) then you may want to resolve the hostname to an address first and then pass the address to ``connectTCP`` instead.

Reconnection
~~~~~~~~~~~~
Often, the connection of a client will be lost unintentionally due to
network problems. One way to reconnect after a disconnection would be to
call ``connector.connect()`` when the connection is lost:

.. code-block:: python

    from twisted.internet.protocol import ClientFactory

    class EchoClientFactory(ClientFactory):
        def clientConnectionLost(self, connector, reason):
            connector.connect()

The connector passed as the first argument is the interface between a
connection and a protocol. When the connection fails and the factory
receives the ``clientConnectionLost`` event, the factory can
call ``connector.connect()`` to start the connection over again
from scratch.

However, most programs that want this functionality should
implement :api:`twisted.internet.protocol.ReconnectingClientFactory <ReconnectingClientFactory>` instead,
which tries to reconnect if a connection is lost or fails and which
exponentially delays repeated reconnect attempts.

Here is the ``Echo`` protocol implemented with
a ``ReconnectingClientFactory`` :

.. code-block:: python

    from twisted.internet.protocol import Protocol, ReconnectingClientFactory
    from sys import stdout

    class Echo(Protocol):
        def dataReceived(self, data):
            stdout.write(data)

    class EchoClientFactory(ReconnectingClientFactory):
        def startedConnecting(self, connector):
            print 'Started to connect.'

        def buildProtocol(self, addr):
            print 'Connected.'
            print 'Resetting reconnection delay'
            self.resetDelay()
            return Echo()

        def clientConnectionLost(self, connector, reason):
            print 'Lost connection.  Reason:', reason
            ReconnectingClientFactory.clientConnectionLost(self, connector, reason)

        def clientConnectionFailed(self, connector, reason):
            print 'Connection failed. Reason:', reason
            ReconnectingClientFactory.clientConnectionFailed(self, connector,
                                                             reason)

A Higher-Level Example: ircLogBot
---------------------------------

Overview of ircLogBot
~~~~~~~~~~~~~~~~~~~~~
The clients so far have been fairly simple.
A more complicated example comes with Twisted Words in the ``doc/words/examples`` directory.

:download:`ircLogBot.py <../../words/examples/ircLogBot.py>`

.. literalinclude:: ../../words/examples/ircLogBot.py

``ircLogBot.py`` connects to an IRC server, joins a channel, and
logs all traffic on it to a file. It demonstrates some of the
connection-level logic of reconnecting on a lost connection, as well as
storing persistent data in the ``Factory`` .

Persistent Data in the Factory
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Since the ``Protocol`` instance is recreated each time the
connection is made, the client needs some way to keep track of data that
should be persisted. In the case of the logging bot, it needs to know which
channel it is logging, and where to log it.

.. code-block:: python

    from twisted.words.protocols import irc
    from twisted.internet import protocol

    class LogBot(irc.IRCClient):

        def connectionMade(self):
            irc.IRCClient.connectionMade(self)
            self.logger = MessageLogger(open(self.factory.filename, "a"))
            self.logger.log("[connected at %s]" %
                            time.asctime(time.localtime(time.time())))

        def signedOn(self):
            self.join(self.factory.channel)


    class LogBotFactory(protocol.ClientFactory):

        def __init__(self, channel, filename):
            self.channel = channel
            self.filename = filename

        def buildProtocol(self, addr):
            p = LogBot()
            p.factory = self
            return p

When the protocol is created, it gets a reference to the factory as
``self.factory`` . It can then access attributes of the factory in
its logic. In the case of ``LogBot`` , it opens the file and
connects to the channel stored in the factory.

Factories have a default implementation of ``buildProtocol``.
It does the same thing the example above does using the ``protocol`` attribute of the factory to create the protocol instance.
In the example above, the factory could be rewritten to look like this:

.. code-block:: python

    class LogBotFactory(protocol.ClientFactory):
        protocol = LogBot

        def __init__(self, channel, filename):
            self.channel = channel
            self.filename = filename

Further Reading
---------------
The :api:`twisted.internet.protocol.Protocol <Protocol>` class used throughout this document is a base implementation of :api:`twisted.internet.interfaces.IProtocol <IProtocol>` used in most Twisted applications for convenience.
To learn about the complete ``IProtocol`` interface, see the API documentation for :api:`twisted.internet.interfaces.IProtocol <IProtocol>` .

The ``transport`` attribute used in some examples in this
document provides the :api:`twisted.internet.interfaces.ITCPTransport <ITCPTransport>` interface. To learn
about the complete interface, see the API documentation
for :api:`twisted.internet.interfaces.ITCPTransport <ITCPTransport>` .

Interface classes are a way of specifying what methods and attributes an
object has and how they behave. See the :doc:`Components: Interfaces and Adapters <components>` document for more information on
using interfaces in Twisted.
