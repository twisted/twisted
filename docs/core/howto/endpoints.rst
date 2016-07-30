:LastChangedDate: $LastChangedDate$
:LastChangedRevision: $LastChangedRevision$
:LastChangedBy: $LastChangedBy$


Getting Connected with Endpoints
================================


Introduction
------------

On a network, one can think of any given connection as a long wire, stretched between two points.
Lots of stuff can happen along the length of that wire - routers, switches, network address translation, and so on, but that is usually invisible to the application passing data across it.
Twisted strives to make the nature of the "wire" as transparent as possible, with highly abstract interfaces for passing and receiving data, such as :api:`twisted.internet.interfaces.ITransport <ITransport>` and :api:`twisted.internet.interfaces.IProtocol <IProtocol>`.

However, the application can't be completely ignorant of the wire.
In particular, it must do something to *start* the connection, and
to do so, it must identify the *end points* of the wire. There are
different names for the roles of each end point - "initiator" and
"responder", "connector" and "listener", or "client" and "server" - but the
common theme is that one side of the connection waits around for someone to
connect to it, and the other side does the connecting.

In Twisted 10.1, several new interfaces were introduced to describe each of these roles for stream-oriented connections: :api:`twisted.internet.interfaces.IStreamServerEndpoint <IStreamServerEndpoint>` and :api:`twisted.internet.interfaces.IStreamClientEndpoint <IStreamClientEndpoint>`.
The word "stream", in this case, refers to endpoints which treat a connection as a continuous stream of bytes, rather than a sequence of discrete datagrams:
TCP is a "stream" protocol whereas UDP is a "datagram" protocol.


Constructing and Using Endpoints
--------------------------------

In both :doc:`Writing Servers <servers>` and :doc:`Writing Clients <clients>`, we covered basic usage of endpoints;
you construct an appropriate type of server or client endpoint, and then call ``listen`` (for servers) or ``connect`` (for clients).

In both of those tutorials, we constructed specific types of endpoints directly.
However, in most programs, you will want to allow the user to specify where to listen or connect, in a way which will allow the user to request different strategies, without having to adjust your program.
In order to allow this, you should use :api:`twisted.internet.endpoints.clientFromString <clientFromString>` or :api:`twisted.internet.endpoints.serverFromString <serverFromString>`.


There's Not Much To It
~~~~~~~~~~~~~~~~~~~~~~

Each type of endpoint is just an interface with a single method that
takes an argument. ``serverEndpoint.listen(factory)`` will start
listening on that endpoint with your protocol factory, and ``clientEndpoint.connect(factory)`` will start a single connection
attempt. Each of these APIs returns a value, though, which can be important.

However, if you are not already, you *should* be very familiar with :doc:`Deferreds <defer>`, as they are returned by both ``connect`` and ``listen`` methods, to indicate when the connection has connected or the listening port is up and running.


Servers and Stopping
~~~~~~~~~~~~~~~~~~~~

:api:`twisted.internet.interfaces.IStreamServerEndpoint.listen <IStreamServerEndpoint.listen>` returns a :api:`twisted.internet.defer.Deferred <Deferred>` that fires with an :api:`twisted.internet.interfaces.IListeningPort <IListeningPort>`.
Note that this deferred may errback.
The most common cause of such an error would be that another program is already using the requested port number, but the exact cause may vary depending on what type of endpoint you are listening on.
If you receive such an error, it means that your application is not actually listening, and will not receive any incoming connections.
It's important to somehow alert an administrator of your server, in this case, especially if you only have one listening port!

Note also that once this has succeeded, it will continue listening forever.
If you need to *stop* listening for some reason, in response to anything other than a full server shutdown (``reactor.stop`` and / or ``twistd`` will usually handle that case for you), make sure you keep a reference around to that listening port object so you can call :api:`twisted.internet.interfaces.IListeningPort.stopListening <IListeningPort.stopListening>` on it.
Finally, keep in mind that ``stopListening`` itself returns a ``Deferred``, and the port may not have fully stopped listening until that ``Deferred`` has fired.

Most server applications will not need to worry about these details.
One example of a case where you would need to be concerned with all of these events would be an implementation of a protocol like non-``PASV`` FTP, where new listening ports need to be bound for the lifetime of a particular action, then disposed of.


Clients and Cancelling
~~~~~~~~~~~~~~~~~~~~~~

:api:`twisted.internet.endpoints.connectProtocol <connectProtocol>` connects a :api:`twisted.internet.protocol.Protocol <Protocol>` instance to a given :api:`twisted.internet.interfaces.IStreamClientEndpoint <IStreamClientEndpoint>`. It returns a ``Deferred`` which fires with the ``Protocol`` once the connection has been made.
Connection attempts may fail, and so that :api:`twisted.internet.defer.Deferred <Deferred>` may also errback.
If it does so, you will have to try again; no further attempts will be made.
See the :doc:`client documentation <clients>` for an example use.

:api:`twisted.internet.endpoints.connectProtocol <connectProtocol>` is a wrapper around a lower-level API:
:api:`twisted.internet.interfaces.IStreamClientEndpoint.connect <IStreamClientEndpoint.connect>` will use a protocol factory for a new outgoing connection attempt.
It returns a ``Deferred`` which fires with the ``IProtocol`` returned from the factory's ``buildProtocol`` method, or errbacks with the connection failure.

Connection attempts may also take a long time, and your users may become bored and wander off.
If this happens, and your code decides, for whatever reason, that you've been waiting for the connection too long, you can call :api:`twisted.internet.defer.Deferred.cancel <Deferred.cancel>` on the ``Deferred`` returned from :api:`twisted.internet.interfaces.IStreamClientEndpoint.connect <connect>` or :api:`twisted.internet.endpoints.connectProtocol <connectProtocol>`, and the underlying machinery should give up on the connection.
This should cause the ``Deferred`` to errback, usually with :api:`twisted.internet.defer.CancelledError <CancelledError>`;
although you should consult the documentation for your particular endpoint type to see if it may do something different.

Although some endpoint types may imply a built-in timeout, the
interface does not guarantee one. If you don't have any way for the
application to cancel a wayward connection attempt, the attempt may just
keep waiting forever.  For example, a very simple 30-second timeout could be
implemented like this:

.. code-block:: python


    attempt = connectProtocol(myEndpoint, myProtocol)
    reactor.callLater(30, attempt.cancel)


.. note::
   If you've used ``ClientFactory`` before, keep in mind that the ``connect`` method takes a ``Factory``, not a ``ClientFactory``.
   Even if you pass a ``ClientFactory`` to ``endpoint.connect``, its ``clientConnectionFailed`` and ``clientConnectionLost`` methods will not be called.
   In particular, clients that extend ``ReconnectingClientFactory`` won't reconnect. The next section describes how to set up reconnecting clients on endpoints.


Persistent Client Connections
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

:api:`twisted.application.internet.ClientService` can maintain a persistent outgoing connection to a server which can be started and stopped along with your application.

One popular protocol to maintain a long-lived client connection to is IRC, so for an example of ``ClientService``, here's how you would make a long-lived encrypted connection to an IRC server (other details, like how to authenticate, omitted for brevity):

.. code-block:: python

   from twisted.internet.protocol import Factory
   from twisted.internet.endpoints import clientFromString
   from twisted.words.protocols.irc import IRCClient
   from twisted.application.internet import ClientService
   from twisted.internet import reactor

   myEndpoint = clientFromString(reactor, "tls:example.com:6997")
   myFactory = Factory.forProtocol(IRCClient)

   myReconnectingService = ClientService(myEndpoint, myFactory)

If you already have a parent service, you can add the reconnecting service as a child service:

.. code-block:: python

   parentService.addService(myReconnectingService)

If you do not have a parent service, you can start and stop the reconnecting service using its ``startService`` and ``stopService`` methods.

``ClientService.stopService`` returns a ``Deferred`` that fires once the current connection closes or the current connection attempt is cancelled.


Getting The Active Client
-------------------------

When maintaining a long-lived connection, it's often useful to be able to get the current connection (if the connection is active) or wait for the next connection (if a connection attempt is currently in progress).
For example, we might want to pass our ``ClientService`` from the previous example to some code that can send IRC notifications in response to some external event.
The ``ClientService.whenConnected`` method returns a ``Deferred`` that fires with the next available ``Protocol`` instance.
You can use it like so:

.. code-block:: python

    waitForConnection = myReconnectingService.whenConnected()
    def connectedNow(clientForIRC):
        clientForIRC.say("#bot-test", "hello, world!")
    waitForConnection.addCallback(connectedNow)

Keep in mind that you may need to wrap this up for your particular application, since when no existing connection is available, the callback is executed just as soon as the connection is established.
For example, that little snippet is slightly oversimplified: at the time ``connectedNow`` is run, the bot hasn't authenticated or joined the channel yet, so its message will be refused.
A real-life IRC bot would need to have its own method for waiting until the connection is fully ready for chat before chatting.

Retry Policies
--------------

``ClientService`` will immediately attempt an outgoing connection when ``startService`` is called.
If that connection attempt fails for any reason (name resolution, connection refused, network unreachable, and so on), it will retry according to the policy specified in the ``retryPolicy`` constructor argument.
By default, ``ClientService`` will use an exponential backoff algorithm with a minimum delay of 1 second and a maximum delay of 1 minute, and a jitter of up to 1 additional second to prevent stampeding-herd performance cascades.
This is a good default, and if you do not have highly specialized requirements, you probably want to use it.
If you need to tune these parameters, you have two options:

1. You can pass your own timeout policy to ``ClientService``'s constructor.
   A timeout policy is a callable that takes the number of failed attempts, and computes a delay until the next connection attempt.
   So, for example, if you are *really really sure* that you want to reconnect *every single second* if the service you are talking to goes down, you can do this:

   .. code-block:: python

      myReconnectingService = ClientService(myEndpoint, myFactory, retryPolicy=lambda ignored: 1)

   Of course, unless you have only one client and only one server and they're both on localhost, this sort of policy is likely to cause massive performance degradation and thundering herd resource contention in the event of your server's failure, so you probably want to take the second option...

2. You can tweak the default exponential backoff policy with a few parameters by passing the result of :api:`twisted.application.internet.backoffPolicy` to the ``retryPolicy`` argument.
   For example, if you want to make it triple the delay between attempts, but start with a faster connection interval (half a second instead of one second), you could do it like so:

   .. code-block:: python

      myReconnectingService = ClientService(
          myEndpoint, myFactory,
          retryPolicy=backoffPolicy(initialDelay=0.5, factor=3.0)
      )

.. note::

   Before endpoints, reconnecting clients were created as subclasses of ``ReconnectingClientFactory``.
   These subclasses were required to call ``resetDelay``.
   One of the many advantages of using endpoints is that these special subclasses are no longer needed.
   ``ClientService`` accepts ordinary ``IProtocolFactory`` providers.


Maximizing the Return on your Endpoint Investment
-------------------------------------------------

Directly constructing an endpoint in your application is rarely the
best option, because it ties your application to a particular type of
transport. The strength of the endpoints API is in separating the
construction of the endpoint (figuring out where to connect or listen) and
its activation (actually connecting or listening).

If you are implementing a library that needs to listen for
connections or make outgoing connections, when possible, you should write
your code to accept client and server endpoints as parameters to functions
or to your objects' constructors. That way, application code that calls
your library can provide whatever endpoints are appropriate.

If you are writing an application and you need to construct endpoints yourself, you can allow users to specify arbitrary endpoints described by a string using the :api:`twisted.internet.endpoints.clientFromString <clientFromString>` and :api:`twisted.internet.endpoints.serverFromString <serverFromString>` APIs.
Since these APIs just take a string, they provide flexibility:
if Twisted adds support for new types of endpoints (for example, IPv6 endpoints, or WebSocket endpoints), your application will automatically be able to take advantage of them with no changes to its code.


Endpoints Aren't Always the Answer
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

For many use-cases, especially the common case of a ``twistd`` plugin which runs a long-running server that just binds a simple port, you might not want to use the endpoints APIs directly.
Instead, you may want to construct an :api:`twisted.application.service.IService <IService>`, using :api:`twisted.application.strports.service <strports.service>`, which will fit neatly into the required structure of :doc:`the twistd plugin API <plugin>`.
This doesn't give your application much control - the port starts listening at startup and stops listening at shutdown - but it does provide the same flexibility in terms of what type of server endpoint your application will support.

It is, however, almost always preferable to use an endpoint rather than calling a lower-level APIs like :api:`twisted.internet.interfaces.IReactorTCP.connectTCP <connectTCP>`, :api:`twisted.internet.interfaces.IReactorTCP.listenTCP <listenTCP>`, etc, directly.
By accepting an arbitrary endpoint rather than requiring a specific reactor interface, you leave your application open to lots of interesting transport-layer extensibility for the future.


Endpoint Types Included With Twisted
------------------------------------

The parser used by ``clientFromString`` and ``serverFromString`` is extensible via third-party plugins, so the endpoints available on your system depend on what packages you have installed.
However, Twisted itself includes a set of basic endpoints that will always be available.


Clients
~~~~~~~

TCP
   Supported arguments: ``host``, ``port``, ``timeout``.
   ``timeout`` is optional.

   For example, ``tcp:host=twistedmatrix.com:port=80:timeout=15``.

TLS
   Required arguments: ``host``, ``port``.

   Optional arguments: ``timeout``, ``bindAddress``, ``certificate``, ``privateKey``, ``trustRoots``, ``endpoint``.

   - ``host`` is a (UTF-8 encoded) hostname to connect to, as well as the host name to verify against.
   - ``port`` is a numeric port number to connect to.
   - ``timeout`` and ``bindAddress`` have the same meaning as the ``timeout`` and ``bindAddress`` for TCP clients.
   - ``certificate`` is the certificate to use for the client; it should be the path name of a PEM file containing a certificate for which ``privateKey`` is the private key.
   - ``privateKey`` is the client's private key, matching the certificate specified by ``certificate``.
     It should be the path name of a PEM file containing an X.509 client certificate.
     If ``certificate`` is specified but ``privateKey`` is unspecified, Twisted will look for the certificate in the same file as specified by ``certificate``.
   - ``trustRoots`` specifies a path to a directory of PEM-encoded certificate files.  If you leave this unspecified, Twisted will do its best to use the platform default set of trust roots, which should be the default WebTrust set.
   - the optional ``endpoint`` parameter changes the meaning of the ``tls:`` endpoint slightly.
     Rather than the default of connecting over TCP with the same hostname used for verification, you can connect over *any* endpoint type.
     If you specify the endpoint here, ``host`` and ``port`` are used for certificate verification purposes only.
     Bear in mind you will need to backslash-escape the colons in the endpoint description here.

   This client connects to the supplied hostname, validates the server's hostname against the supplied hostname, and then upgrades to TLS immediately after validation succeeds.

   The simplest example of this would be: ``tls:example.com:443``.

   You can use the ``endpoint:`` feature with TCP if you want to connect to a host name; for example, if your DNS is not working, but you know that the IP address 7.6.5.4 points to ``awesome.site.example.com``, you could specify: ``tls:awesome.site.example.com:443:endpoint=tcp\:7.6.5.4\:443``.

   You can use it with any other endpoint type as well, though; for example, if you had a local UNIX socket that established a tunnel to ``awesome.site.example.com`` in ``/var/run/awesome.sock``, you could instead do ``tls:awesome.site.example.com:443:endpoint=unix\:/var/run/awesome.sock``.

   Or, from python code::

     wrapped = HostnameEndpoint('example.com', 443)
     contextFactory = optionsForClientTLS(hostname=u'example.com')
     endpoint = wrapClientTLS(contextFactory, wrapped)
     conn = endpoint.connect(Factory.forProtocol(Protocol))

UNIX
   Supported arguments: ``path``, ``timeout``, ``checkPID``.
   ``path`` gives a filesystem path to a listening UNIX domain socket server.
   ``checkPID`` (optional) enables a check of the lock file Twisted-based UNIX domain socket servers use to prove they are still running.

   For example, ``unix:path=/var/run/web.sock``.

TCP (Hostname)
   Supported arguments: ``host``, ``port``, ``timeout``.
   ``host`` is a hostname to connect to.
   ``timeout`` is optional.
   It is a name-based TCP endpoint that returns the connection which is established first amongst the resolved addresses.

   For example,

   .. code-block:: python


      endpoint = HostnameEndpoint(reactor, "twistedmatrix.com", 80)
      conn = endpoint.connect(Factory.forProtocol(Protocol))

SSL (Deprecated)

   .. note::

       You should generally prefer the "TLS" client endpoint, above, unless you need to work with versions of Twisted older than 16.0.
       Among other things:

        - the ``ssl:`` client endpoint requires that you pass ''both'' ``hostname=`` (for hostname verification) as well as ``host=`` (for a TCP connection address) in order to get hostname verification, which is required for security, whereas ``tls:`` does the correct thing by default by using the same hostname for both.

        - the ``ssl:`` client endpoint doesn't work with IPv6, and the ``tls:`` endpoint does.

   All TCP arguments are supported, plus: ``certKey``, ``privateKey``, ``caCertsDir``.
   ``certKey`` (optional) gives a filesystem path to a certificate (PEM format).
   ``privateKey`` (optional) gives a filesystem path to a private key (PEM format).
   ``caCertsDir`` (optional) gives a filesystem path to a directory containing trusted CA certificates to use to verify the server certificate.

   For example, ``ssl:host=twistedmatrix.com:port=443:caCertsDir=/etc/ssl/certs``.


Servers
~~~~~~~

TCP (IPv4)
   Supported arguments: ``port``, ``interface``, ``backlog``.
   ``interface`` and ``backlog`` are optional.
   ``interface`` is an IP address (belonging to the IPv4 address family) to bind to.

   For example, ``tcp:port=80:interface=192.168.1.1``.

TCP (IPv6)
   All TCP (IPv4) arguments are supported, with ``interface`` taking an IPv6 address literal instead.

   For example, ``tcp6:port=80:interface=2001\:0DB8\:f00e\:eb00\:\:1``.

SSL
   All TCP arguments are supported, plus: ``certKey``, ``privateKey``, ``extraCertChain``, ``sslmethod``, and ``dhParameters``.
   ``certKey`` (optional, defaults to the value of privateKey) gives a filesystem path to a certificate (PEM format).
   ``privateKey`` gives a filesystem path to a private key (PEM format).
   ``extraCertChain`` gives a filesystem path to a file with one or more concatenated certificates in PEM format that establish the chain from a root CA to the one that signed your certificate.
   ``sslmethod`` indicates which SSL/TLS version to use (a value like ``TLSv1_METHOD``).
   ``dhParameters`` gives a filesystem path to a file in PEM format with parameters that are required for Diffie-Hellman key exchange.
   Since the this is required for the ``DHE``-family of ciphers that offer perfect forward secrecy (PFS), it is recommended to specify one.
   Such a file can be created using ``openssl dhparam -out dh_param_1024.pem -2 1024``.
   Please refer to `OpenSSL's documentation on dhparam <http://www.openssl.org/docs/apps/dhparam.html>`_ for further details.

   For example, ``ssl:port=443:privateKey=/etc/ssl/server.pem:extraCertChain=/etc/ssl/chain.pem:sslmethod=SSLv3_METHOD:dhParameters=dh_param_1024.pem``.

UNIX
   Supported arguments: ``address``, ``mode``, ``backlog``, ``lockfile``.
   ``address`` gives a filesystem path to listen on with a UNIX domain socket server.
   ``mode`` (optional) gives the filesystem permission/mode (in octal) to apply to that socket.
   ``lockfile`` enables use of a separate lock file to prove the server is still running.

   For example, ``unix:address=/var/run/web.sock:lockfile=1``.

systemd
   Supported arguments: ``domain``, ``index``.
   ``domain`` indicates which socket domain the inherited file descriptor belongs to (eg INET, INET6).
   ``index`` indicates an offset into the array of file descriptors which have been inherited from systemd.

   For example, ``systemd:domain=INET6:index=3``.

   See also :doc:`Deploying Twisted with systemd <systemd>`.

PROXY
  The PROXY protocol is a stream wrapper and can be applied any of the other server endpoints by placing ``haproxy:`` in front of a normal port definition.

  For example, ``haproxy:tcp:port=80:interface=192.168.1.1`` or ``haproxy:ssl:port=443:privateKey=/etc/ssl/server.pem:extraCertChain=/etc/ssl/chain.pem:sslmethod=SSLv3_METHOD:dhParameters=dh_param_1024.pem``.

  The PROXY protocol provides a way for load balancers and reverse proxies to send down the real IP of a connection's source and destination without relying on X-Forwarded-For headers. A Twisted service using this endpoint wrapper must run behind a service that sends valid PROXY protocol headers. For more on the protocol see `the formal specification <http://www.haproxy.org/download/1.5/doc/proxy-protocol.txt>`_. Both version one and two of the protocol are currently supported.
