Using TLS in Twisted
====================

Overview
--------

This document describes how to secure your communications using TLS (Transport Layer Security) --- also known as SSL (Secure Sockets Layer) --- in Twisted servers and clients.
TLS is the protocol underlying the HTTPS protocol, so many of these concepts are used to secure your web server as well.

To read this document, you will need to understand some pre-requisites:

- You should already know how to create TCP servers and clients with Twisted as described in the :doc:`server howto <servers>` and :doc:`client howto <clients>`.
- You should know how to create an :doc:`Endpoint <endpoints>` .
- You should be able to obtain trusted TLS certificates, with something like
  `certbot <https://certbot.eff.org/>`_ and `Let's Encrypt
  <https://letsencrypt.org>`_

After reading this document you should be able to:

- create servers and clients that can use TLS to encrypt their connectios
- switch from using an unencrypted channel to an encrypted one mid-connection, and
- require client authentication using client certificates.

Using TLS in Twisted requires that you have various dependencies installed that are included in Twisted's ``tls`` optional dependency group.
To ensure that you have the required additional libraries installed, please ``pip install 'twisted[tls]'`` .

TLS Quick Start
---------------

To set up a TLS server, use the ``tls:`` string endpoint prefix.
If you're using a command-line tool with a ``--listen`` argument, such as ``twist web``, you can create an ``tls:`` endpoint that serves your certificate on port 443, by doing ``twist web --listen tls:/path/to/certbot/config/live:443``.
If you're writing your own server, use :py:func:`twisted.internet.endpoints.serverFromString` and let your users configure TLS this way when they need it.

For TLS clients, we can use :py:func:`twisted.internet.endpoints.wrapClientTLS` together with :py:class:`twisted.internet.endpoints.HostnameEndpoint` and :py:func:`twisted.internet.ssl.optionsForClientTLS`, passing the same hostname to both.

If your client is an HTTP client via :py:class:`twisted.web.client.Agent`, simply pass an HTTPS URL and the verification behavior will be correct by default, using your platform's trust store.

TLS Security Basics
-------------------

TLS provides transport layer security, but it's important to understand what "security" means.
With respect to TLS it means three things:

#. Identity: TLS servers (and sometimes clients) present a certificate, offering proof of who they are, so that you know who you are talking to.
#. Confidentiality: once you know who you are talking to, encryption of the connection ensures that the communications can't be understood by any third parties who might be listening in.
#. Integrity: TLS checks the encrypted messages to ensure that they actually came from the party you originally authenticated to.
   If the messages fail these checks, then they are discarded and your application does not see them.

Without identity, neither confidentiality nor integrity is possible.
If you don't know who you're talking to, then you might as easily be talking to your bank or to a thief who wants to steal your bank password.

.. note::

   Twisted's TLS support is currently based on PyOpenSSL (which is, in turn, based on OpenSSL) and inherits certain PyOpenSSL terminology and types.
   Twisted will often refer to a TLS *connection*, which is a reference to an :py:class:`pyOpenSSL Connection <OpenSSL.SSL.Connection>`, or a *context*, which is a reference to an :py:class:`pyOpenSSL Context <OpenSSL.SSL.Context>`.
   You should not need to know PyOpenSSL's API to use Twisted's TLS support, but it's useful to understand that:

   1. A Connection is an object used to individually configure a single connection to a peer, and
   2. a Context is an object that may be shared among many connections (particularly on a server), that describes common areas of configuration between multiple connections.

The requirements of clients and servers are slightly different.
Both *can* provide a certificate to prove their identity.
Commonly, however, TLS *servers* provide a certificate, whereas TLS *clients* check the server's certificate (to make sure they're talking to the right server).
Clients then later identify themselves to the server some other way, often by offering a shared secret (such as a password or API key) via an application protocol secured with TLS, not as part of TLS itself.

Therefore, let's begin with a simple TLS client, that will connect to an existing server.

We can wrap any stream client endpoint with :py:func:`twisted.internet.endpoints.wrapClientTLS`, which will run an encrypted TLS connection over whatever the underlying transport is.

This example client uses a combination of :py:class:`twisted.internet.endpoints.HostnameEndpoint`,  :py:func:`twisted.internet.endpoints.wrapClientTLS`, and :py:func:`twisted.internet.ssl.optionsForClientTLS` to connect to ``example.com`` via TLS, and issue an extremely simple HTTPS request.

:download:`wrapped_client.py <listings/ssl/wrapped_client.py>`

.. literalinclude:: listings/ssl/wrapped_client.py

Since these requirements are slightly different, there are different APIs to construct an appropriate ``contextFactory`` value for a client or a server.

For servers, we can use :py:class:`twisted.internet.ssl.CertificateOptions`.
In order to prove the server's identity, you pass the ``privateKey`` and ``certificate`` arguments to this object.
:py:meth:`twisted.internet.ssl.PrivateCertificate.options` is a convenient way to create a ``CertificateOptions`` instance configured to use a particular key and certificate.

As mentioned above, we can get a context factory configured for clients with :py:func:`twisted.internet.ssl.optionsForClientTLS`.
This takes two arguments, ``hostname`` (which indicates what hostname must be advertised in the server's certificate) and optionally ``trustRoot``.
By default, :py:func:`optionsForClientTLS <twisted.internet.ssl.optionsForClientTLS>` tries to obtain the trust roots from your platform, but you can specify your own.

You may obtain an object suitable to pass as the ``trustRoot=`` parameter with an explicit list of :py:class:`twisted.internet.ssl.Certificate` or :py:class:`twisted.internet.ssl.PrivateCertificate` instances by calling :py:func:`twisted.internet.ssl.trustRootFromCertificates`. This will cause :py:func:`optionsForClientTLS <twisted.internet.ssl.optionsForClientTLS>` to accept any connection so long as the server's certificate is signed by at least one of the certificates passed.

.. note::

   Currently, Twisted only supports loading of OpenSSL's default trust roots.
   If you've built OpenSSL yourself, you must take care to include these in the appropriate location.
   If you're using macOS, it will work by default as long as the homebrew ``openssl`` package is installed.
   If you're using Debian, or one of its derivatives like Ubuntu, install the `ca-certificates` package to ensure you have trust roots available, and this behavior should also be correct.
   Work is ongoing to make :py:func:`platformTrust <twisted.internet.ssl.platformTrust>` --- the API that :py:func:`optionsForClientTLS <twisted.internet.ssl.optionsForClientTLS>` uses by default --- more robust.
   For example, :py:func:`platformTrust <twisted.internet.ssl.platformTrust>` should fall back to `the "certifi" package <https://pypi.org/project/certifi>`_ if no platform trust roots are available but it doesn't do that yet.
   When this happens, you shouldn't need to change your code.

TLS echo server and client
--------------------------

Now that we've got the theory out of the way, let's try some working examples of how to get started with a TLS server.
The following examples rely on the files ``server.pem`` (private key and self-signed certificate together) and ``public.pem`` (the server's public certificate by itself).

TLS echo server
~~~~~~~~~~~~~~~

:download:`echoserv_ssl.py <../examples/echoserv_ssl.py>`

.. literalinclude:: ../examples/echoserv_ssl.py

This server uses :py:func:`wrapServerTLS <twisted.internet.endpoints.wrapServerTLS>` to listen for TLS traffic on port 8000, using the certificate and private key contained in the file ``server.pem``.
It uses the same echo example server as the TCP echo server --- even going so far as to import its protocol class.
Assuming that you can buy your own TLS certificate from a certificate authority, this is a fairly realistic TLS server.

TLS echo client
~~~~~~~~~~~~~~~

:download:`echoclient_ssl.py <../examples/echoclient_ssl.py>`

.. literalinclude:: ../examples/echoclient_ssl.py

This client uses :py:class:`SSL4ClientEndpoint <twisted.internet.endpoints.SSL4ClientEndpoint>` to connect to ``echoserv_ssl.py``.
It *also* uses the same echo example client as the TCP echo client.
Whenever you have a protocol that listens on plain-text TCP it is easy to run it over TLS instead.
It specifies that it only wants to talk to a host named ``"example.com"``, and that it trusts the certificate authority in ``"public.pem"`` to say who ``"example.com"`` is.
Note that the host you are connecting to --- localhost --- and the host whose identity you are verifying --- example.com --- can differ.
In this case, our example ``server.pem`` certificate identifies a host named "example.com", but your server is proably running on localhost.

In a realistic client, it's very important that you pass the same "hostname"  your connection API (in this case, :py:class:`SSL4ClientEndpoint <twisted.internet.endpoints.SSL4ClientEndpoint>`) and :py:func:`optionsForClientTLS <twisted.internet.ssl.optionsForClientTLS>`.
In this case we're using "``localhost``" as the host to connect to because you're probably running this example on your own computer and "``example.com``" because that's the value hard-coded in the dummy certificate distributed along with Twisted's example code.

Connecting To Public Servers
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Here is a short example, now using the default trust roots for :py:func:`optionsForClientTLS <twisted.internet.ssl.optionsForClientTLS>` from :py:func:`platformTrust <twisted.internet.ssl.platformTrust>`.

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

Client authentication
---------------------

While TLS clients must always verify their server's certificate, servers may also authenticate clients by way of a client certificate.

TLS server with client authentication via client certificate verification
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

When one or more certificates are passed to :py:meth:`twisted.internet.ssl.PrivateCertificate.options`, the resulting ``contextFactory`` will use those certificates as trusted authorities and require that the client present a certificate with a valid chain anchored by one of those authorities, much as the ``trustRoot`` parameter to :py:func:`twisted.internet.ssl.optionsForClientTLS` works.

A server can use this to verify that a client provides a valid certificate signed by one of those certificate authorities; here is an example of passing such a certificate.

:download:`ssl_clientauth_server.py <../examples/ssl_clientauth_server.py>`

.. literalinclude:: ../examples/ssl_clientauth_server.py

Client with certificates
~~~~~~~~~~~~~~~~~~~~~~~~

The following client then supplies such a certificate as the ``clientCertificate`` argument to :py:func:`optionsForClientTLS <twisted.internet.ssl.optionsForClientTLS>`, while still validating the server's identity.

:download:`ssl_clientauth_client.py <../examples/ssl_clientauth_client.py>`

.. literalinclude:: ../examples/ssl_clientauth_client.py

Notice that these two examples are very similar to the TLS echo examples above.
In fact, you can demonstrate a failed authentication by simply running ``echoclient_ssl.py`` against ``ssl_clientauth_server.py``; you'll see no output because the server closed the connection rather than echoing the client's authenticated input.


TLS Protocol Options
~~~~~~~~~~~~~~~~~~~~

For servers, it is desirable to offer Diffie-Hellman based key exchange that provides perfect forward secrecy.
The ciphers are activated by default, however it is necessary to pass an instance of :py:class:`DiffieHellmanParameters <twisted.internet.ssl.DiffieHellmanParameters>` to ``CertificateOptions`` via the ``dhParameters`` option to be able to use them.

For example,

.. code-block:: python

    from twisted.internet.ssl import CertificateOptions, DiffieHellmanParameters
    from twisted.python.filepath import FilePath
    dhFilePath = FilePath('dh_param_1024.pem')
    dhParams = DiffieHellmanParameters.fromFile(dhFilePath)
    options = CertificateOptions(..., dhParameters=dhParams)

Another part of the TLS protocol which ``CertificateOptions`` can control is the version of the TLS or SSL protocol used.
By default, Twisted will configure it to use TLSv1.2 or later and disable the insecure SSLv3 protocol.
Manual control over protocols can be helpful if you need to support legacy SSLv3 systems, or you wish to restrict it down to just the strongest of the TLS versions.

You can ask ``CertificateOptions`` to use a more secure default minimum than Twisted's by using the ``raiseMinimumTo`` argument in the initializer:

.. code-block:: python

    from twisted.internet.ssl import CertificateOptions, TLSVersion
    options = CertificateOptions(
        ...,
        raiseMinimumTo=TLSVersion.TLSv1_3)

This will always negotiate a minimum of TLSv1.3, but will negotiate higher versions if Twisted's default is higher.
This usage will stay secure if Twisted updates the minimum to some hypothetical future TLS version, rather than causing your application to use the now theoretically insecure minimum you set.

If you need a strictly hard range of TLS versions you wish ``CertificateOptions`` to negotiate, you can use the ``insecurelyLowerMinimumTo`` and ``lowerMaximumSecurityTo`` arguments in the initializer:

.. code-block:: python

    from twisted.internet.ssl import CertificateOptions, TLSVersion
    options = CertificateOptions(
        ...,
        insecurelyLowerMinimumTo=TLSVersion.TLSv1_0,
        lowerMaximumSecurityTo=TLSVersion.TLSv1_2)

This will cause it to negotiate between TLSv1.0 and TLSv1.2, and will not change if Twisted's default minimum TLS version is raised.
Note that this may not work at all, due to your version of OpenSSL potentially limiting the availability of deprecated or broken TLS versions.
It is highly recommended not to set ``lowerMaximumSecurityTo`` unless you have a peer that is known to misbehave on newer TLS versions, and to only set ``insecurelyLowerMinimumTo`` when Twisted's minimum is not acceptable.
Using these two arguments to ``CertificateOptions`` may make your application's TLS insecure if you do not review it frequently, and should not be used in libraries.

SSLv3 support is still available and you can enable support for it if you wish.
As an example, this supports all TLS versions and SSLv3:

.. code-block:: python

    from twisted.internet.ssl import CertificateOptions, TLSVersion
    options = CertificateOptions(
        ...,
        insecurelyLowerMinimumTo=TLSVersion.SSLv3)

Future OpenSSL versions may completely remove the ability to negotiate the insecure SSLv3 protocol, and this will not allow you to re-enable it.

Additionally, it is possible to limit the acceptable ciphers for your connection by passing an :py:class:`IAcceptableCiphers <twisted.internet.interfaces.IAcceptableCiphers>` object to ``CertificateOptions``.
Since Twisted uses a secure cipher configuration by default, it is discouraged to do so unless absolutely necessary.


Application Layer Protocol Negotiation (ALPN)
---------------------------------------------

ALPN is a TLS extension that can be used by clients and servers to negotiate what application-layer protocol will be spoken once the encrypted connection is established.
This avoids the need for extra custom round trips once the encrypted connection is established. It is implemented as a standard part of the TLS handshake.

:py:class:`twisted.internet.ssl.CertificateOptions` and :py:func:`twisted.internet.ssl.optionsForClientTLS` allow for selecting the protocols your program is willing to speak after the connection is established.

On the server-side you will have:

.. code-block:: python

    from twisted.internet.ssl import CertificateOptions
    options = CertificateOptions(..., acceptableProtocols=[b'h2', b'http/1.1'])

and for clients:

.. code-block:: python

    from twisted.internet.ssl import optionsForClientTLS
    options = optionsForClientTLS(hostname=hostname, acceptableProtocols=[b'h2', b'http/1.1'])

If Twisted is acting as the server - which, in ALPN, is the peer who is supposed to select the protocol - it will prefer the earliest protocol in the list that is supported by both peers.

To determine what protocol was negotiated, after the connection is done,  use :py:attr:`TLSMemoryBIOProtocol.negotiatedProtocol <twisted.protocols.tls.TLSMemoryBIOProtocol.negotiatedProtocol>`.
It will return one of the protocol names passed to the ``acceptableProtocols`` parameter.
It will return ``None`` if the peer did not offer ALPN.

It can also return ``None`` if no overlap could be found and the connection was established regardless (some peers will do this: Twisted will not).
In this case, the protocol that should be used is whatever protocol would have been used if negotiation had not been attempted at all.

.. warning::
    If ALPN is used and no overlap can be found, then the remote peer may terminate the connection.
    This may cause the TLS handshake to fail, or may result in the connection being torn down immediately after being made.
    If Twisted is the server, and no overlap can be found, Twisted will always choose to fail the handshake rather than allow an ambiguous connection to set up.

An example of using this functionality can be found in :download:`this example script for clients </core/examples/tls_alpn_client.py>` and :download:`this example script for servers </core/examples/tls_alpn_server.py>`.

Using STARTTLS
--------------

If you want to switch from unencrypted to encrypted traffic mid-connection, in the style of protocols like `SMTP STARTTLS <https://datatracker.ietf.org/doc/html/rfc3207>`_\ , you can begin a TLS negotiation mid-connection with the :py:meth:`startTLS <twisted.internet.interfaces.ITLSTransport.startTLS>` methods on both ends of the connection at the same time via some agreed-upon signal like the reception of a particular plain-text message.

.. warning::

   While Twisted provides support for handling ``STARTTLS``-style commands, as they are an important part of several core internet protocols, note that any plain-text messages that you send prior to starting the secure connection are parts of a secure protocol cryptographic construction and thus count as “`rolling your own crypto <https://www.schneier.com/blog/archives/2011/04/schneiers_law.html>`_\ ”, and you shouldn't do it unless you **really** know what you're doing!  In general, prefer using TLS endpoints, especially when designing new protocols.

startTLS server
~~~~~~~~~~~~~~~

:download:`starttls_server.py <../examples/starttls_server.py>`

.. literalinclude:: ../examples/starttls_server.py

startTLS client
~~~~~~~~~~~~~~~

:download:`starttls_client.py <../examples/starttls_client.py>`

.. literalinclude:: ../examples/starttls_client.py

:py:meth:`twisted.internet.interfaces.ITLSTransport.startTLS` is a transport method that gets passed a ``contextFactory``.
It is invoked at an agreed-upon time in the data reception method of the client and server protocols.
The server uses ``PrivateCertificate.options`` to create a ``contextFactory`` which will use a particular certificate and private key (a common requirement for TLS servers).

The client creates an uncustomized ``CertificateOptions`` which is all that's necessary for a TLS client to interact with a TLS server.

Related facilities
------------------

- :py:mod:`twisted.web` has built-in TLS support in its :py:mod:`client <twisted.web.client>` , :py:mod:`http <twisted.web.http>` , and :py:mod:`xmlrpc <twisted.web.xmlrpc>` modules.

- :py:mod:`twisted.protocols.amp.StartTLS` is a command you can subclass to allow sending an unencrypted preamble to a custom AMP protocol, but for the reasons mentioned above, you should always prefer running AMP over a TLS endpoint unless you know exactly why you might need this and are confident that you have the relevant expertise to design a secure protocol using it.


Conclusion
----------

After reading through this tutorial, you should be able to:

- Use :py:func:`wrapServerTLS <twisted.internet.endpoints.wrapServerTLS>` and :py:func:`wrapClientTLS <twisted.internet.endpoints.wrapClientTLS>` to create servers and clients that use TLS
- Use ALPN to negotiate application-level protocols.
- Use :py:meth:`twisted.internet.interfaces.ITLSTransport.startTLS` to switch a channel from being unencrypted to using TLS mid-connection
- Add server and client support for client authentication
