
:LastChangedDate: $LastChangedDate$
:LastChangedRevision: $LastChangedRevision$
:LastChangedBy: $LastChangedBy$

Using TLS in Twisted
====================

Overview
--------

This document describes how to secure your communications using TLS (Transport Layer Security) --- also known as SSL (Secure Sockets Layer) --- in Twisted servers and clients.
It assumes that you know what TLS is, what some of the major reasons to use it are, and how to generate your own certificates.
It also assumes that you are comfortable with creating TCP servers and clients as described in the :doc:`server howto <servers>` and :doc:`client howto <clients>` .
After reading this document you should be able to create servers and clients that can use TLS to encrypt their connections, switch from using an unencrypted channel to an encrypted one mid-connection, and require client authentication.

Using TLS in Twisted requires that you have `pyOpenSSL <https://github.com/pyca/pyopenssl>`_ installed. A quick test to verify that you do is to run ``from OpenSSL import SSL`` at a python prompt and not get an error.

Twisted provides TLS support as a transport --- that is, as an alternative to TCP.
When using TLS, use of the TCP APIs you're already familiar with, ``TCP4ClientEndpoint`` and ``TCP4ServerEndpoint`` --- or ``reactor.listenTCP`` and ``reactor.connectTCP`` --- is replaced by use of parallel TLS APIs (many of which still use the legacy name "SSL" due to age and/or compatibility with older APIs).
To create a TLS server, use :api:`twisted.internet.endpoints.SSL4ServerEndpoint <SSL4ServerEndpoint>` or :api:`twisted.internet.interfaces.IReactorSSL.listenSSL <listenSSL>` .
To create a TLS client, use :api:`twisted.internet.endpoints.SSL4ClientEndpoint <SSL4ClientEndpoint>` or :api:`twisted.internet.interfaces.IReactorSSL.connectSSL <connectSSL>` .

TLS provides transport layer security, but it's important to understand what "security" means.
With respect to TLS it means three things:

    1. Identity: TLS servers (and sometimes clients) present a certificate, offering proof of who they are, so that you know who you are talking to.
    2. Confidentiality: once you know who you are talking to, encryption of the connection ensures that the communications can't be understood by any third parties who might be listening in.
    3. Integrity: TLS checks the encrypted messages to ensure that they actually came from the party you originally authenticated to.
       If the messages fail these checks, then they are discarded and your application does not see them.

Without identity, neither confidentiality nor integrity is possible.
If you don't know who you're talking to, then you might as easily be talking to your bank or to a thief who wants to steal your bank password.
Each of the APIs listed above with "SSL" in the name requires a configuration object called (for historical reasons) a ``contextFactory``.
(Please pardon the somewhat awkward name.)
The ``contextFactory`` serves three purposes:

    1. It provides the materials to prove your own identity to the other side of the connection: in other words, who you are.
    2. It expresses your requirements of the other side's identity: in other words, who you would like to talk to (and who you trust to tell you that you're talking to the right party).
    3. It allows you to specify certain specialized options about the way the TLS protocol itself operates.

The requirements of clients and servers are slightly different.
Both *can* provide a certificate to prove their identity, but commonly, TLS *servers* provide a certificate, whereas TLS *clients* check the server's certificate (to make sure they're talking to the right server) and then later identify themselves to the server some other way, often by offering a shared secret such as a password or API key via an application protocol secured with TLS and not as part of TLS itself.

Since these requirements are slightly different, there are different APIs to construct an appropriate ``contextFactory`` value for a client or a server.

For servers, we can use :api:`twisted.internet.ssl.CertificateOptions`.
In order to prove the server's identity, you pass the ``privateKey`` and ``certificate`` arguments to this object.
:api:`twisted.internet.ssl.PrivateCertificate.options` is a convenient way to create a ``CertificateOptions`` instance configured to use a particular key and certificate.

For clients, we can use :api:`twisted.internet.ssl.optionsForClientTLS`.
This takes two arguments, ``hostname`` (which indicates what hostname must be advertised in the server's certificate) and optionally ``trustRoot``.
By default, :api:`twisted.internet.ssl.optionsForClientTLS <optionsForClientTLS>` tries to obtain the trust roots from your platform, but you can specify your own.

You may obtain an object suitable to pass as the ``trustRoot=`` parameter with an explicit list of :api:`twisted.internet.ssl.Certificate` or :api:`twisted.internet.ssl.PrivateCertificate` instances by calling :api:`twisted.internet.ssl.trustRootFromCertificates`. This will cause :api:`twisted.internet.ssl.optionsForClientTLS <optionsForClientTLS>` to accept any connection so long as the server's certificate is signed by at least one of the certificates passed.

.. note::

   Currently, Twisted only supports loading of OpenSSL's default trust roots.
   If you've built OpenSSL yourself, you must take care to include these in the appropriate location.
   If you're using the OpenSSL shipped as part of Mac OS X 10.5-10.9, this behavior will also be correct.
   If you're using Debian, or one of its derivatives like Ubuntu, install the `ca-certificates` package to ensure you have trust roots available, and this behavior should also be correct.
   Work is ongoing to make :api:`twisted.internet.ssl.platformTrust <platformTrust>` --- the API that :api:`twisted.internet.ssl.optionsForClientTLS <optionsForClientTLS>` uses by default --- more robust.
   For example, :api:`twisted.internet.ssl.platformTrust <platformTrust>` should fall back to `the "certifi" package <http://pypi.python.org/pypi/certifi>`_ if no platform trust roots are available but it doesn't do that yet.
   When this happens, you shouldn't need to change your code.

TLS echo server and client
--------------------------

Now that we've got the theory out of the way, let's try some working examples of how to get started with a TLS server.
The following examples rely on the files ``server.pem`` (private key and self-signed certificate together) and ``public.pem`` (the server's public certificate by itself).

TLS echo server
~~~~~~~~~~~~~~~

:download:`echoserv_ssl.py <../examples/echoserv_ssl.py>`

.. literalinclude:: ../examples/echoserv_ssl.py

This server uses :api:`twisted.internet.interfaces.IReactorSSL.listenSSL <listenSSL>` to listen for TLS traffic on port 8000, using the certificate and private key contained in the file ``server.pem``.
It uses the same echo example server as the TCP echo server --- even going so far as to import its protocol class.
Assuming that you can buy your own TLS certificate from a certificate authority, this is a fairly realistic TLS server.

TLS echo client
~~~~~~~~~~~~~~~

:download:`echoclient_ssl.py <../examples/echoclient_ssl.py>`

.. literalinclude:: ../examples/echoclient_ssl.py

This client uses :api:`twisted.internet.endpoints.SSL4ClientEndpoint <SSL4ClientEndpoint>` to connect to ``echoserv_ssl.py``.
It *also* uses the same echo example client as the TCP echo client.
Whenever you have a protocol that listens on plain-text TCP it is easy to run it over TLS instead.
It specifies that it only wants to talk to a host named ``"example.com"``, and that it trusts the certificate authority in ``"public.pem"`` to say who ``"example.com"`` is.
Note that the host you are connecting to --- localhost --- and the host whose identity you are verifying --- example.com --- can differ.
In this case, our example ``server.pem`` certificate identifies a host named "example.com", but your server is proably running on localhost.

In a realistic client, it's very important that you pass the same "hostname"  your connection API (in this case, :api:`twisted.internet.endpoints.SSL4ClientEndpoint <SSL4ClientEndpoint>`) and :api:`twisted.internet.ssl.optionsForClientTLS <optionsForClientTLS>`.
In this case we're using "``localhost``" as the host to connect to because you're probably running this example on your own computer and "``example.com``" because that's the value hard-coded in the dummy certificate distributed along with Twisted's example code.

Connecting To Public Servers
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Here is a short example, now using the default trust roots for :api:`twisted.internet.ssl.optionsForClientTLS <optionsForClientTLS>` from :api:`twisted.internet.ssl.platformTrust <platformTrust>`.

:download:`check_server_certificate.py <listings/ssl/check_server_certificate.py>`

.. literalinclude:: listings/ssl/check_server_certificate.py

You can use this tool fairly simply to retrieve certificates from an HTTPS server with a valid TLS certificate, by running it with a host name.
For example:

.. code-block:: text

    $ python check_server_certificate.py www.twistedmatrix.com
    OK: <Certificate Subject=www.twistedmatrix.com ...>
    $ python check_server_certificate.py www.cacert.org
    BAD: [(... 'certificate verify failed')]
    $ python check_server_certificate.py dornkirk.twistedmatrix.com
    BAD: No service reference ID could be validated against certificate.

.. note::

   To *properly* validate your ``hostname`` parameter according to RFC6125, please also install the `"service_identity" <https://pypi.python.org/pypi/service_identity>`_ and `"idna" <https://pypi.python.org/pypi/idna>`_ packages from PyPI.
   Without this package, Twisted will currently make a conservative guess as to the correctness of the server's certificate, but this will reject a large number of potentially valid certificates.
   `service_identity` implements the standard correctly and it will be a required dependency for TLS in a future release of Twisted.

Using startTLS
--------------

If you want to switch from unencrypted to encrypted traffic
mid-connection, you'll need to turn on TLS with :api:`twisted.internet.interfaces.ITLSTransport.startTLS <startTLS>` on both
ends of the connection at the same time via some agreed-upon signal like the
reception of a particular message. You can readily verify the switch to an
encrypted channel by examining the packet payloads with a tool like
`Wireshark <http://www.wireshark.org/>`_ .

startTLS server
~~~~~~~~~~~~~~~

:download:`starttls_server.py <../examples/starttls_server.py>`

.. literalinclude:: ../examples/starttls_server.py

startTLS client
~~~~~~~~~~~~~~~

:download:`starttls_client.py <../examples/starttls_client.py>`

.. literalinclude:: ../examples/starttls_client.py

``startTLS`` is a transport method that gets passed a ``contextFactory``.
It is invoked at an agreed-upon time in the data reception method of the client and server protocols.
The server uses ``PrivateCertificate.options`` to create a ``contextFactory`` which will use a particular certificate and private key (a common requirement for TLS servers).

The client creates an uncustomized ``CertificateOptions`` which is all that's necessary for a TLS client to interact with a TLS server.


Client authentication
---------------------

Server and client-side changes to require client authentication fall
largely under the dominion of pyOpenSSL, but few examples seem to exist on
the web so for completeness a sample server and client are provided here.


TLS server with client authentication via client certificate verification
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

When one or more certificates are passed to ``PrivateCertificate.options``, the resulting ``contextFactory`` will use those certificates as trusted authorities and require that the peer present a certificate with a valid chain anchored by one of those authorities.

A server can use this to verify that a client provides a valid certificate signed by one of those certificate authorities; here is an example of such a certificate.

:download:`ssl_clientauth_server.py <../examples/ssl_clientauth_server.py>`

.. literalinclude:: ../examples/ssl_clientauth_server.py

Client with certificates
~~~~~~~~~~~~~~~~~~~~~~~~

The following client then supplies such a certificate as the ``clientCertificate`` argument to :api:`twisted.internet.ssl.optionsForClientTLS <optionsForClientTLS>`, while still validating the server's identity.

:download:`ssl_clientauth_client.py <../examples/ssl_clientauth_client.py>`

.. literalinclude:: ../examples/ssl_clientauth_client.py

Notice that these two examples are very, very similar to the TLS echo examples above.
In fact, you can demonstrate a failed authentication by simply running ``echoclient_ssl.py`` against ``ssl_clientauth_server.py``; you'll see no output because the server closed the connection rather than echoing the client's authenticated input.

TLS Protocol Options
~~~~~~~~~~~~~~~~~~~~

For servers, it is desirable to offer Diffie-Hellman based key exchange that provides perfect forward secrecy.
The ciphers are activated by default, however it is necessary to pass an instance of :api:`twisted.internet.ssl.DiffieHellmanParameters <DiffieHellmanParameters>` to ``CertificateOptions`` via the ``dhParameters`` option to be able to use them.

For example,

.. code-block:: python

    from twisted.internet.ssl import CertificateOptions, DiffieHellmanParameters
    from twisted.python.filepath import FilePath
    dhFilePath = FilePath('dh_param_1024.pem')
    dhParams = DiffieHellmanParameters.fromFile(dhFilePath)
    options = CertificateOptions(..., dhParameters=dhParams)

Another part of the TLS protocol which ``CertificateOptions`` can control is the version of the TLS or SSL protocol used.
This is often called the context's "method".
By default, ``CertificateOptions`` creates contexts that require at least the TLSv1 protocol.
``CertificateOptions`` also supports the older SSLv3 protocol (which may be required interoperate with an existing service or piece of software).
To allow SSLv3, just pass ``OpenSSL.SSL.SSLv3_METHOD`` to ``CertificateOptions``'s initializer:

.. code-block:: python

    from twisted.internet.ssl import CertificateOptions
    from OpenSSL.SSL import SSLv3_METHOD
    options = CertificateOptions(..., method=SSLv3_METHOD)

The somewhat confusingly-named ``OpenSSL.SSL.SSLv23_METHOD`` is also supported (to enable SSLv3 or better, based on negotiation).
SSLv2 is insecure; it is explicitly not supported and will be disabled in all configurations.

Additionally, it is possible to limit the acceptable ciphers for your connection by passing an :api:`twisted.internet.interfaces.IAcceptableCiphers <IAcceptableCiphers>` object to ``CertificateOptions``.
Since Twisted uses a secure cipher configuration by default, it is discouraged to do so unless absolutely necessary.


Application Layer Protocol Negotiation (ALPN) and Next Protocol Negotiation (NPN)
---------------------------------------------------------------------------------

ALPN and NPN are TLS extensions that can be used by clients and servers to negotiate what application-layer protocol will be spoken once the encrypted connection is established.
This avoids the need for extra custom round trips once the encrypted connection is established. It is implemented as a standard part of the TLS handshake.

NPN is supported from OpenSSL version 1.0.1.
ALPN is the newer of the two protocols, supported in OpenSSL versions 1.0.2 onward.
These functions require pyOpenSSL version 0.15 or higher.
To query the methods supported by your system,  use :api:`twisted.internet.ssl.protocolNegotiationMechanisms`.
It will return a collection of flags indicating support for NPN and/or ALPN.

:api:`twisted.internet.ssl.CertificateOptions` and :api:`twisted.internet.ssl.optionsForClientTLS` allow for selecting the protocols your program is willing to speak after the connection is established.

On the server=side you will have:

.. code-block:: python

    from twisted.internet.ssl import CertificateOptions
    options = CertificateOptions(..., acceptableProtocols=[b'h2', b'http/1.1'])

and for clients:

.. code-block:: python

    from twisted.internet.ssl import optionsForClientTLS
    options = optionsForClientTLS(hostname=hostname, acceptableProtocols=[b'h2', b'http/1.1'])

Twisted will attempt to use both ALPN and NPN, if they're available, to maximise compatibility with peers.
If both ALPN and NPN are supported by the peer, the result from ALPN is preferred.

For NPN, the client selects the protocol to use;
For ALPN, the server does.
If Twisted is acting as the peer who is supposed to select the protocol, it will prefer the earliest protocol in the list that is supported by both peers.

To determine what protocol was negotiated, after the connection is done,  use :api:`twisted.protocols.tls.TLSMemoryBIOProtocol.negotiatedProtocol <TLSMemoryBIOProtocol.negotiatedProtocol>`.
It will return one of the protocol names passed to the ``acceptableProtocols`` parameter.
It will return ``None`` if the peer did not offer ALPN or NPN.

It can also return ``None`` if no overlap could be found and the connection was established regardless (some peers will do this: Twisted will not).
In this case, the protocol that should be used is whatever protocol would have been used if negotiation had not been attempted at all.

.. warning::
    If ALPN or NPN are used and no overlap can be found, then the remote peer may choose to terminate the connection.
    This may cause the TLS handshake to fail, or may result in the connection being torn down immediately after being made.
    If Twisted is the selecting peer (that is, Twisted is the server and ALPN is being used, or Twisted is the client and NPN is being used), and no overlap can be found, Twisted will always choose to fail the handshake rather than allow an ambiguous connection to set up.

An example of using this functionality can be found in :download:`this example script for clients </core/examples/tls_alpn_npn_client.py>` and :download:`this example script for servers </core/examples/tls_alpn_npn_server.py>`.


Related facilities
------------------

:api:`twisted.protocols.amp <twisted.protocols.amp>` supports encrypted
connections and exposes a ``startTLS`` method one can use or
subclass. :api:`twisted.web <twisted.web>` has built-in TLS support in
its :api:`twisted.web.client <client>` , :api:`twisted.web.http <http>` , and :api:`twisted.web.xmlrpc <xmlrpc>` modules.


Conclusion
----------

After reading through this tutorial, you should be able to:

- Use ``listenSSL`` and ``connectSSL`` to create servers and clients that use
  TLS
- Use ``startTLS`` to switch a channel from being unencrypted to using TLS
  mid-connection
- Add server and client support for client authentication
