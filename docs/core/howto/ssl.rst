
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
After reading this document you should be able to create servers and clients that can use SSL to encrypt their connections, switch from using an unencrypted channel to an encrypted one mid-connection, and require client authentication.

Using SSL in Twisted requires that you have `pyOpenSSL <http://launchpad.net/pyopenssl>`_ installed. A quick test to verify that you do is to run ``from OpenSSL import SSL`` at a python prompt and not get an error.

Twisted provides SSL support as a transport --- that is, as an alternative to TCP.
When using SSL, use of the TCP APIs you're already familiar with, ``TCP4ClientEndpoint`` and ``TCP4ServerEndpoint`` --- or ``reactor.listenTCP`` and ``reactor.connectTCP`` --- is replaced by use of parallel SSL APIs.
To create an SSL server, use :api:`twisted.internet.endpoints.SSL4ServerEndpoint <SSL4ServerEndpoint>` or :api:`twisted.internet.interfaces.IReactorSSL.listenSSL <listenSSL>` .
To create an SSL client, use :api:`twisted.internet.endpoints.SSL4ClientEndpoint <SSL4ClientEndpoint>` or :api:`twisted.internet.interfaces.IReactorSSL.connectSSL <connectSSL>` .

SSL connections require SSL contexts. As with protocols, these context
objects are created by factories --- so that each connection can be given a
unique context, if necessary.  The context factories typically also keep
state which is necessary to properly configure an SSL context object for
its desired use --- for example, private key or certificate data.  The
context factory is passed as a mandatory argument to any and all of the
SSL APIs mentioned in the previous
paragraph.  :api:`twisted.internet.ssl.CertificateOptions <twisted.internet.ssl.CertificateOptions>`
is one commonly useful context factory for both clients and
servers.  :api:`twisted.internet.ssl.PrivateCertificate.options <twisted.internet.ssl.PrivateCertificate.options>`
is a convenient way to create a ``CertificateOptions`` instance
configured to use a particular key and certificate.

Those are the big immediate differences between TCP and SSL connections,
so let's look at an example. In it and all subsequent examples it is assumed
that keys and certificates for the server, certificate authority, and client
should they exist live in a *keys/* subdirectory of the directory
containing the example code, and that the certificates are self-signed.


SSL echo server and client without client authentication
--------------------------------------------------------

Authentication and encryption are two separate parts of the SSL protocol.
The server almost always needs a key and certificate to authenticate itself
to the client but is usually configured to allow encrypted connections with
unauthenticated clients who don't have certificates. This common case is
demonstrated first by adding SSL support to the echo client and server in
the `core examples <../examples/index.html>`_


SSL echo server
~~~~~~~~~~~~~~~

:download:`echoserv_ssl.py <../examples/echoserv_ssl.py>`

.. literalinclude:: ../examples/echoserv_ssl.py

SSL echo client
~~~~~~~~~~~~~~~

:download:`echoserv_ssl.py <../examples/echoclient_ssl.py>`

.. literalinclude:: ../examples/echoclient_ssl.py

Notice how all of the protocol code from the TCP version of the echo client and server examples is the same (imported or repeated) in these SSL versions -- only the reactor method used to initiate a network action is different.

One part of the SSL connection contexts control is which version of the SSL protocol will be used.
This is often called the context's "method".
By default, ``CertificateOptions`` creates contexts that require at least the TLSv1 protocol.
``CertificateOptions`` also supports the older SSLv3 protocol (which may be required interoperate with an existing service or piece of software), just pass ``OpenSSL.SSL.SSLv3_METHOD`` to its initializer: ``CertificateOptions(..., method=SSLv3_METHOD)``.
``SSLv23_METHOD`` is also supported (to enable SSLv3 or better, based on negotiation).
SSLv2 is explicitly not supported.

Additionally, it is possible to limit the acceptable ciphers for your connection by passing an :api:`twisted.internet.interfaces.IAcceptableCiphers <IAcceptableCiphers>` object to ``CertificateOptions``.
Since Twisted uses a secure cipher configuration by default, it is discouraged to do so unless absolutely necessary.

For servers, it is desirable to offer Diffie-Hellman based key exchange that provides perfect forward secrecy.
The ciphers are activated by default, however it is necessary to pass an instance of :api:`twisted.internet.ssl.DiffieHellmanParameters <DiffieHellmanParameters>` to ``CertificateOptions`` to be able to use them.


SSL client with server certificate verification
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

In the example above, the client did not attempt to verify the certificate presented by the server.
If you are writing a client which connects to a server on the Internet, it is important to verify that server is using a trusted certificate.
If you don't verify the server's certificate, you can not be sure that you are communicating with the intended server.

Peer certificate verification is enabled by supplying a ``trustRoot`` argument to :api:`twisted.internet.ssl.CertificateOptions <CertificateOptions>`.
This argument specifies the list of certificate authorities which you trust, and for what purpose.

For the majority of *client* applications using TLS, you will want to get the list of trusted root certificates from your platform --- meaning, your operating system, your desktop environment, or your TLS implementor's configuration --- and verify the server against that.
This list of certificates will generally include most of the certificate authorities commonly accepted by web browsers, but more importantly, it should also be under the control of the end-user who is using your software, taking security decisions about who to trust out of your code and placing it into the hands of those responsible for securing the systems where your code runs.

To support this common use-case, Twisted provides a function, :api:`twisted.internet.ssl.platformTrust <platformTrust>`, to obtain a set of trusted root certificates based on Twisted's best-effort attempt to discover the current platform's configuration.

.. note::

   Currently, Twisted only supports loading of OpenSSL's default trust roots.
   If you've built OpenSSL yourself, you must take care to include these in the appropriate location.
   If you're using the OpenSSL shipped as part of Mac OS X 10.5-10.9, this behavior will also be correct.
   If you're using Debian, or one of its derivatives like Ubuntu, install the `ca-certificates` package to ensure you have trust roots available, and this behavior should also be correct.
   Work is ongoing to make :api:`twisted.internet.ssl.platformTrust <platformTrust>` more robust.
   For example, :api:`twisted.internet.ssl.platformTrust <platformTrust>` should fall back to `the "certifi" package <http://pypi.python.org/pypi/certifi>`_ if no platform trust roots are available but it doesn't do that yet.
   When this happens, you shouldn't need to change your code.

Here is a short example, demonstrating how to enable verification using the trusted root certificates from your platform with :api:`twisted.internet.ssl.platformTrust <platformTrust>` and :api:`twisted.internet.ssl.CertificateOptions <CertificateOptions>`.

:download:`check_server_certificate.py <listings/ssl/check_server_certificate.py>`

.. literalinclude:: listings/ssl/check_server_certificate.py

You can use this tool fairly simply to retrieve certificates from an HTTPS server with a valid SSL certificate, by running it with a host name.
For example:

.. code-block:: text

    $ python check_server_certificate.py www.twistedmatrix.com
    OK: <Certificate Subject=www.twistedmatrix.com ...>
    $ python check_server_certificate.py www.cacert.org
    BAD: [(... 'certificate verify failed')]
    $ python check_server_certificate.py dornkirk.twistedmatrix.com
    BAD: No service reference ID could be validated against certificate.

.. warning::

   While ``platformTrust`` currently verifies that a certificate *has a valid trust path to a certificate authority*, it doesn't check to see if that certificate is *the right one for the host you're connecting to*.

   Always make sure to also pass the ``hostname`` parameter to :api:`twisted.internet.ssl.CertificateOptions <CertificateOptions>` to indicate which hostname is preferred.

.. note::

   To *properly* validate your ``hostname`` parameter according to RFC6125, please also install the `"service_identity" <https://pypi.python.org/pypi/service_identity>`_ and `"idna" <https://pypi.python.org/pypi/idna>`_ packages from PyPI.
   Twisted will currently make a conservative guess as to the correctness of your certificate, but this will reject a large number of potentially valid certificates.
   `service_identity` implements the standard correctly and it will be a required dependency for SSL in a future release of Twisted.

While the ``platformTrust`` works for applications that want to talk securely to arbitrary hosts on the public internet, some applications have more specific security needs.
For example, you might run a server for which there is only one dedicated client, and you have your own certificate authority specifically for that software, distinct from your users' general trust preferences.
Or you might want to set up trust settings for development, to ensure that you're testing encryption, but don't want the rest of your operating system to trust that throw-away certificate.
In these cases you might want to use a self-signed certificate and verify the server was using that certificate.
Let's say we wanted to do this with the included ``echoserve_ssl.py`` example.

If you use ``check_server_certificate.py`` to check the ``echoserve_ssl.py`` example server (above) you will see that the certificate verification fails.

.. code-block:: text

   $ python check_server_certificate.py localhost 8000
   SSL CONNECT ERROR: [('SSL routines', 'SSL3_GET_SERVER_CERTIFICATE', 'certificate verify failed')]

That's because the certificate used in the example has not been signed by any of the certificate authorities that are trusted by your operating system.
You certainly wouldn't want your entire system to trust the dummy certificate that comes with Twisted!
However, we can modify ``check_server_certificate.py`` to load that certificate, instead.

Certificates in the PEM format can be loaded using :api:`twisted.internet.ssl.Certificate.loadPEM <Certificate.loadPEM>`, just as we did with ``PrivateCertificate``, above.
The loaded ``Certificate`` object can then be used as a certificate authority by passing the :api:`twisted.internet.ssl.Certificate <Certificate>` object as the ``trustRoot`` argument, like this:
 
.. code-block:: python

   cert = ssl.Certificate.loadPEM(open(certificatePath).read())
   contextFactory = ssl.CertificateOptions(trustRoot=cert)

So let's modify ``check_server_certificate.py`` to do just that, with ``echoserve_ssl.py``'s dummy certificate as its ``trustRoot``:

:download:`check_echo_certificate.py <listings/ssl/check_echo_certificate.py>`

.. literalinclude:: listings/ssl/check_echo_certificate.py

This is just the same as above, just specifying a different ``trustRoot``.
While running ``python echoserve_ssl.py`` in the background, you can run this:

.. code-block:: text

  $ python check_echo_certificate.py localhost 8000
  <Certificate Subject=www.example.com Issuer=www.example.com>


Using startTLS
--------------

If you want to switch from unencrypted to encrypted traffic
mid-connection, you'll need to turn on SSL with :api:`twisted.internet.interfaces.ITLSTransport.startTLS <startTLS>` on both
ends of the connection at the same time via some agreed-upon signal like the
reception of a particular message. You can readily verify the switch to an
encrypted channel by examining the packet payloads with a tool like
`Wireshark <http://www.wireshark.org/>`_ .


startTLS server
~~~~~~~~~~~~~~~

.. code-block:: python


    from twisted.internet import reactor, ssl
    from twisted.internet.protocol import ServerFactory
    from twisted.protocols.basic import LineReceiver

    class TLSServer(LineReceiver):
        def lineReceived(self, line):
            print("received: " + line)

            if line == "STARTTLS":
                print("-- Switching to TLS")
                self.sendLine('READY')

                self.transport.startTLS(self.factory.contextFactory)


    if __name__ == '__main__':
        with open("keys/server.key") as keyFile:
            with open("keys/server.crt") as certFile:
                cert = PrivateCertificate.loadPEM(
                    keyFile.read() + certFile.read())

        factory = ServerFactory()
        factory.protocol = TLSServer
        factory.contextFactory = cert.options()
        reactor.listenTCP(8000, factory)
        reactor.run()


startTLS client
~~~~~~~~~~~~~~~


.. code-block:: python

    from __future__ import print_function
    from twisted.internet import reactor, ssl
    from twisted.internet.protocol import ClientFactory
    from twisted.protocols.basic import LineReceiver

    class TLSClient(LineReceiver):
        pretext = [
            "first line",
            "last thing before TLS starts",
            "STARTTLS"]

        posttext = [
            "first thing after TLS started",
            "last thing ever"]

        def connectionMade(self):
            for l in self.pretext:
                self.sendLine(l)

        def lineReceived(self, line):
            print("received: " + line)
            if line == "READY":
                self.transport.startTLS(ssl.CertificateOptions())
                for l in self.posttext:
                    self.sendLine(l)
                self.transport.loseConnection()

    class TLSClientFactory(ClientFactory):
        protocol = TLSClient

        def clientConnectionFailed(self, connector, reason):
            print("connection failed: ", reason.getErrorMessage())
            reactor.stop()

        def clientConnectionLost(self, connector, reason):
            print("connection lost: ", reason.getErrorMessage())
            reactor.stop()

    if __name__ == "__main__":
        factory = TLSClientFactory()
        reactor.connectTCP('localhost', 8000, factory)
        reactor.run()


``startTLS`` is a transport method that gets passed a context
factory.  It is invoked at an agreed-upon time in the data reception method
of the client and server protocols. The server
uses ``PrivateCertificate.options`` to create a context factory
which will use a particular certificate and private key (a common
requirement for SSL servers).  The client creates an
uncustomized ``CertificateOptions`` which is all that's necessary
for an SSL client to interact with an SSL server, although it is missing
some verification settings necessary to ensure correct authentication of the
server and confidentiality of data exchanged.


Client authentication
---------------------

Server and client-side changes to require client authentication fall
largely under the dominion of pyOpenSSL, but few examples seem to exist on
the web so for completeness a sample server and client are provided here.


TLS server with client authentication via client certificate verification
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~


.. code-block:: python


    from twisted.internet import ssl, reactor
    from twisted.internet.protocol import Factory, Protocol

    class Echo(Protocol):
        def dataReceived(self, data):
            self.transport.write(data)

    if __name__ == '__main__':
        factory = Factory()
        factory.protocol = Echo

        with open("keys/ca.pem") as certAuthCertFile:
            certAuthCert = ssl.Certificate.loadPEM(certAuthCertFile.read())

        with open("keys/server.key") as keyFile:
            with open("keys/server.crt") as certFile:
                serverCert = ssl.PrivateCertificate.loadPEM(
                    keyFile.read() + certFile.read())

        contextFactory = serverCert.options(certAuthCert)

        reactor.listenSSL(8000, factory, contextFactory)
        reactor.run()


When one or more certificates are passed
to ``PrivateCertificate.options`` , the resulting context factory
will use those certificates as trusted authorities and require that the
peer present a certificate with a valid chain terminating in one of those
authorities.


Client with certificates
~~~~~~~~~~~~~~~~~~~~~~~~


.. code-block:: python


    from __future__ import print_function
    from twisted.internet import ssl, reactor
    from twisted.internet.protocol import ClientFactory, Protocol

    class EchoClient(Protocol):
        def connectionMade(self):
            print("hello, world")
            self.transport.write("hello, world!")

        def dataReceived(self, data):
            print("Server said:", data)
            self.transport.loseConnection()


    class EchoClientFactory(ClientFactory):
        protocol = EchoClient

        def clientConnectionFailed(self, connector, reason):
            print("Connection failed - goodbye!")
            reactor.stop()

        def clientConnectionLost(self, connector, reason):
            print("Connection lost - goodbye!")
            reactor.stop()


    if __name__ == '__main__':
        with open("keys/server.key") as keyFile:
            with open("keys/server.crt") as certFile:
                clientCert = ssl.PrivateCertificate.loadPEM(
                    keyFile.read() + certFile.read())

        ctx = clientCert.options()
        factory = EchoClientFactory()
        reactor.connectSSL('localhost', 8000, factory, ctx)
        reactor.run()


Notice this client code does not pass any certificate authority
certificates to ``PrivateCertificate.options`` .  This means that
it will not validate the server's certificate, it will only present its
certificate to the server for validation.


Other facilities
----------------

:api:`twisted.protocols.amp <twisted.protocols.amp>` supports encrypted
connections and exposes a ``startTLS`` method one can use or
subclass. :api:`twisted.web <twisted.web>` has built-in SSL support in
its :api:`twisted.web.client <client>` , :api:`twisted.web.http <http>` , and :api:`twisted.web.xmlrpc <xmlrpc>` modules.


Conclusion
----------

After reading through this tutorial, you should be able to:

- Use ``listenSSL`` and ``connectSSL`` to create servers and clients that use
  SSL
- Use ``startTLS`` to switch a channel from being unencrypted to using SSL
  mid-connection
- Add server and client support for client authentication
