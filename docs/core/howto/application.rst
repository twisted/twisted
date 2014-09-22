
:LastChangedDate: $LastChangedDate$
:LastChangedRevision: $LastChangedRevision$
:LastChangedBy: $LastChangedBy$

Using the Twisted Application Framework
=======================================

Introduction
------------

Audience
~~~~~~~~

The target audience of this document is a Twisted user who wants to deploy a significant amount of Twisted code in a re-usable, standard and easily configurable fashion.
A Twisted user who wishes to use the Application framework needs to be familiar with developing Twisted :doc:`servers <servers>` and/or :doc:`clients <clients>`.


Goals
~~~~~

- To introduce the Twisted Application infrastructure.
- To explain how to deploy your Twisted application using ``.tac`` files and ``twistd``.
- To outline the existing Twisted services.


Overview
--------

The Twisted Application infrastructure takes care of running and stopping your application.
Using this infrastructure frees you from from having to write a large amount of boilerplate code by hooking your application into existing tools that manage daemonization, logging, :doc:`choosing a reactor <choosing-reactor>` and more.

The major tool that manages Twisted applications is a command-line utility called ``twistd``.
``twistd`` is cross platform, and is the recommended tool for running Twisted applications.

The core component of the Twisted Application infrastructure is the :api:`twisted.application.service.Application <twisted.application.service.Application>` object --  an object which represents your application.
However, Application doesn't provide anything that you'd want to manipulate directly.
Instead, Application acts as a container of any "Services" (objects implementing :api:`twisted.application.service.IService <IService>`) that your application provides.
Most of your interaction with the Application infrastructure will be done through Services.

By "Service", we mean anything in your application that can be started and stopped.
Typical services include web servers, FTP servers and SSH clients.
Your Application object can contain many services, and can even contain structured hierarchies of Services using :api:`twisted.application.service.MultiService <MultiService>` or your own custom :api:`twisted.application.service.IServiceCollection <IServiceCollection>` implementations.
You will most likely want to use these to manage Services which are dependent on other Services.
For example, a proxying Twisted application might want its server Service to only start up after the associated Client service.

An :api:`twisted.application.service.IService <IService>` has two basic methods, ``startService()`` which is used to start the service, and ``stopService()`` which is used to stop the service.
The latter can return a :api:`twisted.internet.defer.Deferred <Deferred>`, indicating service shutdown is not over until the result fires.
For example:

.. code-block:: python

    from twisted.internet import reactor
    from twisted.application import service
    from somemodule import EchoFactory

    class EchoService(service.Service):
        def __init__(self, portNum):
            self.portNum = portNum

        def startService(self):
            self._port = reactor.listenTCP(self.portNum, EchoFactory())

        def stopService(self):
            return self._port.stopListening()


See :doc:`Writing Servers <servers>` for an explanation of ``EchoFactory`` and ``listenTCP``.


Using Services and Application
------------------------------

twistd and tac
~~~~~~~~~~~~~~
.. _core-howto-application-twistd:


To handle start-up and configuration of your Twisted application, the Twisted Application infrastructure uses ``.tac`` files.
``.tac`` are Python files which configure an :api:`twisted.application.service.Application <Application>` object and assign this object to the top-level variable "``application``" .

The following is a simple example of a ``.tac`` file:

:download:`service.tac <listings/application/service.tac>`

.. literalinclude:: listings/application/service.tac

``twistd`` is a program that runs Twisted applications using a ``.tac`` file. In its most simple form, it takes a single argument ``-y`` and a tac file name.
For example, you can run the above server with the command ``twistd -y service.tac``.

By default, ``twistd`` daemonizes and logs to a file called ``twistd.log``.
More usually, when debugging, you will want your application to run in the foreground and log to the command line.
To run the above file like this, use the command ``twistd -noy service.tac``.

For more information, see the ``twistd`` man page.


Customizing ``twistd``  logging
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``twistd`` logging can be customized using the command line.
This requires that a *log observer factory* be importable.
Given a file named ``my.py`` with the code:

.. code-block:: python

    from twisted.python.log import FileLogObserver

    def logger():
        return FileLogObserver(open("/tmp/my.log", "w")).emit


Invoking ``twistd --logger my.logger ...`` will log to a file named ``/tmp/my.log`` (this simple example could easily be replaced with use of the ``--logfile`` parameter to twistd).

Alternatively, the logging behavior can be customized through an API accessible from ``.tac`` files.
The :api:`twisted.python.log.ILogObserver <ILogObserver>` component can be set on an Application in order to customize the default log observer that ``twistd`` will use.

Here is an example of how to use :api:`twisted.python.logfile.DailyLogFile <DailyLogFile>`, which rotates the log once per day.

.. code-block:: python

    from twisted.application.service import Application
    from twisted.python.log import ILogObserver, FileLogObserver
    from twisted.python.logfile import DailyLogFile

    application = Application("myapp")
    logfile = DailyLogFile("my.log", "/tmp")
    application.setComponent(ILogObserver, FileLogObserver(logfile).emit)


Invoking ``twistd -y my.tac`` will create a log file at ``/tmp/my.log``.


Services provided by Twisted
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Twisted also provides pre-written :api:`twisted.application.service.IService <IService>` implementations for common cases like listening on a TCP port, in the :api:`twisted.application.internet <twisted.application.internet>` module.
Here's a simple example of constructing a service that runs an echo server on TCP port 7001:

.. code-block:: python

    from twisted.application import internet, service
    from somemodule import EchoFactory

    port = 7001
    factory = EchoFactory()

    echoService = internet.TCPServer(port, factory) # create the service


Each of these services (except TimerService) has a corresponding "connect" or "listen" method on the reactor, and the constructors for the services take the same arguments as the reactor methods.
The "connect" methods are for clients and the "listen" methods are for servers.
For example, ``TCPServer`` corresponds to ``reactor.listenTCP`` and ``TCPClient`` corresponds to ``reactor.connectTCP``.

``TCPServer``

``TCPClient``

  Services which allow you to make connections and listen for connections
  on TCP ports.

  - :api:`twisted.internet.interfaces.IReactorTCP.listenTCP <listenTCP>`
  - :api:`twisted.internet.interfaces.IReactorTCP.connectTCP <connectTCP>`


``UNIXServer``

``UNIXClient``

  Services which listen and make connections over UNIX sockets.

  - :api:`twisted.internet.interfaces.IReactorUNIX.listenUNIX <listenUNIX>`
  - :api:`twisted.internet.interfaces.IReactorUNIX.connectUNIX <connectUNIX>`


``SSLServer``

``SSLClient``

  Services which allow you to make SSL connections and run SSL servers.

  - :api:`twisted.internet.interfaces.IReactorSSL.listenSSL <listenSSL>`
  - :api:`twisted.internet.interfaces.IReactorSSL.connectSSL <connectSSL>`


``UDPServer``

  A service which allows you to send and receive data over UDP.

  - :api:`twisted.internet.interfaces.IReactorUDP.listenUDP <listenUDP>`

  See also the :doc:`UDP documentation <udp>`.


``UNIXDatagramServer``

``UNIXDatagramClient``

  Services which send and receive data over UNIX datagram sockets.

  - :api:`twisted.internet.interfaces.IReactorUNIXDatagram.listenUNIXDatagram <listenUNIXDatagram>`
  - :api:`twisted.internet.interfaces.IReactorUNIXDatagram.connectUNIXDatagram <connectUNIXDatagram>`


``MulticastServer``

  A server for UDP socket methods that support multicast.

  - :api:`twisted.internet.interfaces.IReactorMulticast.listenMulticast <listenMulticast>`


``TimerService``

  A service to periodically call a function.

  - :api:`twisted.application.internet.TimerService <TimerService>`


Service Collection
~~~~~~~~~~~~~~~~~~

:api:`twisted.application.service.IServiceCollection <IServiceCollection>` objects contain :api:`twisted.application.service.IService <IService>` objects.
IService objects can be added to IServiceCollection by calling :api:`twisted.application.service.IService.setServiceParent <setServiceParent>` and detached by using :api:`twisted.application.service.IService.disownServiceParent <disownServiceParent>`.

The standard implementation of IServiceCollection is :api:`twisted.application.service.MultiService <MultiService>`, which also implements IService.
MultiService is useful for creating a new Service which combines two or more existing Services.
For example, you could create a DNS Service as a MultiService which has a TCP and a UDP Service as children.

.. code-block:: python

    from twisted.application import internet, service
    from twisted.names import server, dns, hosts

    port = 53

    # Create a MultiService, and hook up a TCPServer and a UDPServer to it as
    # children.
    dnsService = service.MultiService()
    hostsResolver = hosts.Resolver('/etc/hosts')
    tcpFactory = server.DNSServerFactory([hostsResolver])
    internet.TCPServer(port, tcpFactory).setServiceParent(dnsService)
    udpFactory = dns.DNSDatagramProtocol(tcpFactory)
    internet.UDPServer(port, udpFactory).setServiceParent(dnsService)

    # Create an application as normal
    application = service.Application("DNSExample")

    # Connect our MultiService to the application, just like a normal service.
    dnsService.setServiceParent(application)
