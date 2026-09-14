
:LastChangedDate: $LastChangedDate$
:LastChangedRevision: $LastChangedRevision$
:LastChangedBy: $LastChangedBy$

Writing Servers
===============

Overview
--------

This document explains how you can use Twisted to implement network protocol parsing and handling for TCP servers (the same code can be reused for SSL and Unix socket servers).
There is a :doc:`separate document <udp>` covering UDP.

Your protocol handling class must implement the :py:class:`IProtocol <twisted.internet.interfaces.IProtocol>` interface, and may subclass :py:class:`twisted.internet.protocol.Protocol` for a convenient default implementation so you don't need to implement every method yourself.
Most protocols inherit either from this class or from one of its convenience children.
An instance of the protocol class is instantiated per-connection, on demand, and will go away when the connection is finished.
This means that any state that lives longer than a single connection, such as configuration, cannot be stored on the protocol.

Connection-independent configuration is kept in a protocol factory, which must implement the :py:class:`IProtocolFactory <twisted.internet.interfaces.IProtocolFactory>` interface, and may similarly inherit from :py:class:`twisted.internet.protocol.Factory` for a convenient default initial implementation.
The ``buildProtocol`` method of the factory is used to create a protocol for each new connection.

It is usually useful to be able to offer the same service on multiple ports or network addresses.
This is why the factory does not listen to connections, and in fact does not know anything about the network.
See :doc:`the endpoints documentation <endpoints>` for more information, or :py:meth:`IReactorTCP.listenTCP <twisted.internet.interfaces.IReactorTCP.listenTCP>` and the other ``IReactor*.listen*`` APIs for the lower level APIs that endpoints are based on.

This document will explain each step of the way.


Protocols
---------

As mentioned above, this, along with auxiliary classes and functions, is where most of the code is.
A Twisted protocol handles data in an asynchronous manner.
The protocol responds to events as they arrive from the network and the events arrive as calls to methods on the protocol.

Here is a simple example::

    from twisted.internet.protocol import Protocol

    class Echo(Protocol):

        def dataReceived(self, data):
            self.transport.write(data)

This is one of the simplest protocols.
It simply writes back whatever is written to it, and does not respond to all events.
Here is an example of a Protocol responding to another event::

    from twisted.internet.protocol import Protocol

    class QOTD(Protocol):

        def connectionMade(self):
            self.transport.write("An apple a day keeps the doctor away\r\n")
            self.transport.loseConnection()

This protocol responds to the initial connection with a well known quote, and then terminates the connection.

The ``connectionMade`` event is usually where setup of the connection object happens, as well as any initial greetings (as in the QOTD protocol above, which is actually based on :rfc:`865`).
The ``connectionLost`` event is where tearing down of any connection-specific objects is done.
Here is an example::

    from twisted.internet.protocol import Protocol

    class Echo(Protocol):

        def __init__(self, factory):
            self.factory = factory

        def connectionMade(self):
            self.factory.numProtocols = self.factory.numProtocols + 1
            self.transport.write(
                "Welcome! There are currently %d open connections.\n" %
                (self.factory.numProtocols,))

        def connectionLost(self, reason):
            self.factory.numProtocols = self.factory.numProtocols - 1

        def dataReceived(self, data):
            self.transport.write(data)

Here ``connectionMade`` and ``connectionLost`` cooperate to keep a count of the active protocols in a shared object, the factory.
The factory must be passed to ``Echo.__init__`` when creating a new instance.
The factory is used to share state that exists beyond the lifetime of any given connection.
You will see why this object is called a "factory" in the next section.


loseConnection() and abortConnection()
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

In the code above, ``loseConnection`` is called immediately after writing to the transport.
The ``loseConnection`` call will close the connection only when all the data has been written by Twisted out to the operating system, so it is safe to use in this case without worrying about transport writes being lost.
If a :doc:`producer <producers>` is being used with the transport, ``loseConnection`` will only close the connection once the producer is unregistered.

In some cases, waiting until all the data is written out is not what we want.
Due to network failures, or bugs or maliciousness in the other side of the connection, data written to the transport may not be deliverable, and so even though ``loseConnection`` was called the connection will not be lost.
In these cases, ``abortConnection`` can be used: it closes the connection immediately, regardless of buffered data that is still unwritten in the transport, or producers that are still registered.
Note that ``abortConnection`` is only available in Twisted 11.1 and newer.


Using the Protocol
~~~~~~~~~~~~~~~~~~

In this section, you will learn how to run a server which uses your protocol.

Here is code that will run the QOTD server discussed earlier::

    from twisted.internet.protocol import Factory
    from twisted.internet.endpoints import TCP4ServerEndpoint
    from twisted.internet import reactor

    class QOTDFactory(Factory):
        def buildProtocol(self, addr):
            return QOTD()

    # 8007 is the port you want to run under. Choose something >1024
    endpoint = TCP4ServerEndpoint(reactor, 8007)
    endpoint.listen(QOTDFactory())
    reactor.run()

In this example, I create a protocol factory.
I want to tell this factory that its job is to build QOTD protocol instances, so I set its ``buildProtocol`` method to return instances of the QOTD class.
Then, I want to listen on a TCP port, so I make a :py:class:`TCP4ServerEndpoint <twisted.internet.endpoints.TCP4ServerEndpoint>` to identify the port that I want to bind to, and then pass the factory I just created to its ``listen`` method.

``endpoint.listen()`` tells the reactor to handle connections to the endpoint's address using a particular protocol, but the reactor needs to be *running* in order for it to do anything.
``reactor.run()`` starts the reactor and then waits forever for connections to arrive on the port you've specified.
You can stop the reactor by hitting Control-C in a terminal or calling ``reactor.stop()``.

For more information on different ways you can listen for incoming connections, see :doc:`the documentation for the endpoints API <endpoints>`.
For more information on using the reactor, see :doc:`the reactor overview <reactor-basics>`.


Helper Protocols
~~~~~~~~~~~~~~~~

Many protocols build upon similar lower-level abstractions.

For example, many popular internet protocols are line-based, containing text data terminated by line breaks (commonly CR-LF), rather than containing straight raw data.
However, quite a few protocols are mixed - they have line-based sections and then raw data sections.
Examples include HTTP/1.1 and the Freenet protocol.

For those cases, there is the :py:class:`LineReceiver <twisted.protocols.basic.LineReceiver>` protocol.
This protocol dispatches to two different event handlers -- ``lineReceived`` and ``rawDataReceived``.
By default, only ``lineReceived`` will be called, once for each line.
However, if ``setRawMode`` is called, the protocol will call ``rawDataReceived`` until ``setLineMode`` is called, which returns it to using ``lineReceived``.
It also provides a method, ``sendLine``, that writes data to the transport along with the delimiter the class uses to split lines (by default, ``\r\n``).

Here is an example for a simple use of the line receiver::

    from twisted.protocols.basic import LineReceiver

    class Answer(LineReceiver):

        answers = {'How are you?': 'Fine', None: "I don't know what you mean"}

        def lineReceived(self, line):
            if line in self.answers:
                self.sendLine(self.answers[line])
            else:
                self.sendLine(self.answers[None])

Note that the delimiter is not part of the line.

Several other helpers exist, such as a :py:class:`netstring based protocol <twisted.protocols.basic.NetstringReceiver>` and :py:class:`prefixed-message-length protocols <twisted.protocols.basic.IntNStringReceiver>`.


State Machines
~~~~~~~~~~~~~~

Many Twisted protocols need to write a state machine to record the state they are at.
Here are some pieces of advice which help to write state machines:

- Don't write big state machines.
  Prefer to write a state machine which deals with one level of abstraction at a time.
- Don't mix application-specific code with Protocol handling code.
  When the protocol has to make an application-specific call, keep it as a method call.


Factories
---------

Simpler Protocol Creation
~~~~~~~~~~~~~~~~~~~~~~~~~

For a factory whose only customization is to instantiate a particular protocol class in buildProtocol, there is a simpler way to implement the factory.
:py:class:`twisted.internet.protocol.Factory`'s implementation of :py:class:`IProtocolFactory.buildProtocol<twisted.internet.protocol.IProtocolFactory.buildProtocol>` calls the ``protocol`` attribute of the factory, with no arguments, to create a protocol instance, and then sets an attribute on it called ``factory`` which points to the factory itself.
This lets every protocol access the connection-independent state on the factory.
Here is an example that uses these features instead of overriding ``buildProtocol``::

    from twisted.internet.protocol import Factory, Protocol
    from twisted.internet.endpoints import TCP4ServerEndpoint
    from twisted.internet import reactor

    class QOTD(Protocol):

        def connectionMade(self):
            # self.factory was set by the factory's default buildProtocol:
            self.transport.write(self.factory.quote + '\r\n')
            self.transport.loseConnection()


    class QOTDFactory(Factory):

        # This will be used by the default buildProtocol to create new protocols:
        protocol = QOTD

        def __init__(self, quote=None):
            self.quote = quote or 'An apple a day keeps the doctor away'

    endpoint = TCP4ServerEndpoint(reactor, 8007)
    endpoint.listen(QOTDFactory("configurable quote"))
    reactor.run()

If all you need is a simple factory that builds a protocol without any additional behavior, Twisted 13.1 added :py:meth:`Factory.forProtocol <twisted.internet.protocol.Factory.forProtocol>`, an even simpler approach.


Factory Startup and Shutdown
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

:py:class:`Factory <twisted.internet.protocol.Factory>` has two methods you can override to perform application-specific setup and teardown: ``startFactory`` and ``stopFactory``.

These are called when the factory begins listening on its first port, and when it stops listening on its last port, respectively.

Here is an example of a factory which allows its Protocols to write to a special log-file::

    from twisted.internet.protocol import Factory
    from twisted.protocols.basic import LineReceiver


    class LoggingProtocol(LineReceiver):

        def lineReceived(self, line):
            self.factory.fp.write(line + '\n')


    class LogfileFactory(Factory):

        protocol = LoggingProtocol

        def __init__(self, fileName):
            self.file = fileName

        def startFactory(self):
            self.fp = open(self.file, 'a')

        def stopFactory(self):
            self.fp.close()


Putting it All Together
-----------------------

As a final example, here's a simple chat server that allows users to choose a username and then communicate with other users.
It demonstrates the use of shared state in the factory, a state machine for each individual protocol, and communication between different protocols.

:download:`chat.py <listings/servers/chat.py>`

.. literalinclude:: listings/servers/chat.py

The only API you might not be familiar with is ``listenTCP``.
:py:meth:`listenTCP <twisted.internet.interfaces.IReactorTCP.listenTCP>` is the method which connects a protocol factory to the network.
This is the lower-level API that :doc:`endpoints <endpoints>` wraps for you.

Here's a sample transcript of a chat session (emphasised text is entered by the user):

.. code-block:: console
   :emphasize-lines: 1,6,8,10,12

    $ telnet 127.0.0.1 8123
    Trying 127.0.0.1...
    Connected to 127.0.0.1.
    Escape character is '^]'.
    What's your name?
    test
    Name taken, please choose another.
    bob
    Welcome, bob!
    hello
    <alice> hi bob
    twisted makes writing servers so easy!
    <alice> I couldn't agree more
    <carrol> yeah, it's great
