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
listening on that endpoint with your protocol factory, and``clientEndpoint.connect(factory)`` will start a single connection
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
This should cause the``Deferred`` to errback, usually with :api:`twisted.internet.defer.CancelledError <CancelledError>`;
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

SSL
   All TCP arguments are supported, plus: ``certKey``, ``privateKey``, ``caCertsDir``.
   ``certKey`` (optional) gives a filesystem path to a certificate (PEM format).
   ``privateKey`` (optional) gives a filesystem path to a private key (PEM format).
   ``caCertsDir`` (optional) gives a filesystem path to a directory containing trusted CA certificates to use to verify the server certificate.

   For example, ``ssl:host=twistedmatrix.com:port=443:caCertsDir=/etc/ssl/certs`` .
UNIX
   Supported arguments: ``path``, ``timeout``, ``checkPID``.
   ``path`` gives a filesystem path to a listening UNIX domain socket server.
   ``checkPID`` (optional) enables a check of the lock file Twisted-based UNIX domain socket servers use to prove they are still running.

   For example, ``unix:path=/var/run/web.sock``.

TLS
   Supported arguments: ``wrappedEndpoint``, ``certKey``, ``privateKey``, ``caCertsDir``.
   The latter three arguments have the same semantics as the SSL client.
   This client connects to the wrapped endpoint and then upgrades to TLS as soon as the connection is established.

   For example, ``tls:tcp\:example.com\:443:caCertsDir=/etc/ssl/certs`` .
   This connects to the endpoint ``tcp:example.com:443`` before starting TLS.
   The colons are escaped because the TLS endpoint string syntax itself calls ``clientFromString`` to create the wrapped endpoint, and expects a single string argument.

   Or, from python code::

     wrapped = TCP4ClientEndpoint('example.com', 443)
     endpoint = TLSWrapperClientEndpoint(contextFactory, wrapped)
     conn = endpoint.connect(Factory.forProtocol(Protocol))

TCP (Hostname)
   Supported arguments: ``host``, ``port``, ``timeout``.
   ``host`` is a hostname to connect to.
   ``timeout`` is optional.
   It is a name-based TCP endpoint that returns the connection which is established first amongst the resolved addresses.

   For example,

   .. code-block:: python


      endpoint = HostnameEndpoint(reactor, "twistedmatrix.com", 80)
      conn = endpoint.connect(Factory.forProtocol(Protocol))


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
