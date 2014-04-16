
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

Using TLS in Twisted requires that you have `pyOpenSSL <http://launchpad.net/pyopenssl>`_ installed. A quick test to verify that you do is to run ``from OpenSSL import SSL`` at a python prompt and not get an error.

Twisted provides SSL support as a transport --- that is, as an alternative to TCP.
When using SSL, use of the TCP APIs you're already familiar with, ``TCP4ClientEndpoint`` and ``TCP4ServerEndpoint`` --- or ``reactor.listenTCP`` and ``reactor.connectTCP`` --- is replaced by use of parallel SSL APIs.
To create an SSL server, use :api:`twisted.internet.endpoints.SSL4ServerEndpoint <SSL4ServerEndpoint>` or :api:`twisted.internet.interfaces.IReactorSSL.listenSSL <listenSSL>` .
To create an SSL client, use :api:`twisted.internet.endpoints.SSL4ClientEndpoint <SSL4ClientEndpoint>` or :api:`twisted.internet.interfaces.IReactorSSL.connectSSL <connectSSL>` .

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

For servers, we can use :api:`twisted.internet.ssl.CertificateOptions <twisted.internet.ssl.CertificateOptions>`.
In order to prove the server's identity, you pass the ``privateKey`` and ``certificate`` arguments to this object.
:api:`twisted.internet.ssl.PrivateCertificate.options` is a convenient way to create a ``CertificateOptions`` instance configured to use a particular key and certificate.

For clients, we can use :api:`twisted.internet.ssl.settingsForClientTLS`.
This takes two arguments, ``hostname`` (which indicates what hostname must be advertised in the server's certificate) and optionally ``trustRoot``.
By default, :api:`twisted.internet.ssl.settingsForClientTLS <settingsForClientTLS>` tries to obtain the trust roots from your platform, but you can specify your own.

.. note::

   Currently, Twisted only supports loading of OpenSSL's default trust roots.
   If you've built OpenSSL yourself, you must take care to include these in the appropriate location.
   If you're using the OpenSSL shipped as part of Mac OS X 10.5-10.9, this behavior will also be correct.
   If you're using Debian, or one of its derivatives like Ubuntu, install the `ca-certificates` package to ensure you have trust roots available, and this behavior should also be correct.
   Work is ongoing to make :api:`twisted.internet.ssl.platformTrust <platformTrust>` - the API that :api:`twisted.internet.ssl.settingsForClientTLS <settingsForClientTLS>` uses by default - more robust.
   For example, :api:`twisted.internet.ssl.platformTrust <platformTrust>` should fall back to `the "certifi" package <http://pypi.python.org/pypi/certifi>`_ if no platform trust roots are available but it doesn't do that yet.
   When this happens, you shouldn't need to change your code.

SSL echo server and client
--------------------------

Now that we've got the theory out of the way, let's try some working examples of how to get started with a TLS server.
The following examples rely on the files ``server.pem`` (private key and self-signed certificate together) and ``public.pem`` (the server's public certificate by itself).

SSL echo server
~~~~~~~~~~~~~~~

:download:`echoserv_ssl.py <../examples/echoserv_ssl.py>`

.. literalinclude:: ../examples/echoserv_ssl.py

This server uses :api:`twisted.internet.interfaces.IReactorSSL.listenSSL <listenSSL>` to listen for SSL traffic on port 8000, using the certificate and private key contained in the file ``server.pem``.
It uses the same echo example server as the TCP echo server - even going so far as to import its protocol class.
Assuming that you can buy your own SSL certificate from a certificate authority, this is a fairly realistic SSL server.

SSL echo client
~~~~~~~~~~~~~~~

:download:`echoserv_ssl.py <../examples/echoclient_ssl.py>`

.. literalinclude:: ../examples/echoclient_ssl.py

This client uses :api:`twisted.internet.interfaces.IReactorSSL.connectSSL <connectSSL>` to connect to ``echoserv_ssl.py``.
It uses specifies that it only wants to talk to a host named ``"example.com"``, and and that it trusts the certificate authority in ``"public.pem"`` to say who ``"example.com"`` is.
Note that the host you are connecting to --- localhost --- and the host whose identity you are verifying --- example.com --- can differ.
In this case, our example ``server.pem`` certificate identifies a host named "example.com", but your server is proably running on localhost.

In a realistic server, it's very important that these names match; in a realistic client, they should always be the same.

Connecting To Public Servers
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Here is a short example, now using the default trust roots for :api:`twisted.internet.ssl.settingsForClientTLS <settingsForClientTLS>` from :api:`twisted.internet.ssl.platformTrust <platformTrust>`.

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

.. note::

   To *properly* validate your ``hostname`` parameter according to RFC6125, please also install the `"service_identity" <https://pypi.python.org/pypi/service_identity>`_ and `"idna" <https://pypi.python.org/pypi/idna>`_ packages from PyPI.
   Without this package, Twisted will currently make a conservative guess as to the correctness of the server's certificate, but this will reject a large number of potentially valid certificates.
   `service_identity` implements the standard correctly and it will be a required dependency for SSL in a future release of Twisted.

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

                self.transport.startTLS(self.factory.options)


    if __name__ == '__main__':
        with open("keys/server.key") as keyFile:
            keyPEM = keyFile.read()
        with open("keys/server.crt") as certFile:
            certPEM = certFile.read()
        cert = PrivateCertificate.loadPEM(keyPEM + certPEM)

        factory = Factory.forProtocol(TLSServer)
        factory.options = cert.options()
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
                self.transport.startTLS(self.factory.settings)
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
        with open("keys/server.crt") as certFile:
            certPEM = certFile.read()
        factory.settings = ssl.settingsForClientTLS(
            u"example.com", ssl.Certificate.loadPEM(certPEM)
        )
        reactor.connectTCP('localhost', 8000, factory)
        reactor.run()

``startTLS`` is a transport method that gets passed a ``contextFactory``.
It is invoked at an agreed-upon time in the data reception method of the client
and server protocols.
The server uses ``PrivateCertificate.options`` to create a ``contextFactory`` which will use a particular certificate and private key (a common requirement for SSL servers).

The client creates an uncustomized ``CertificateOptions`` which is all that's necessary for an SSL client to interact with an SSL server.


Client authentication
---------------------

Server and client-side changes to require client authentication fall
largely under the dominion of pyOpenSSL, but few examples seem to exist on
the web so for completeness a sample server and client are provided here.


TLS server with client authentication via client certificate verification
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

When one or more certificates are passed to ``PrivateCertificate.options`` , the resulting ``contextFactory`` will use those certificates as trusted authorities and require that the peer present a certificate with a valid chain anchored by one of those authorities.

Here is a server that does just such a thing.

:download:`echoserv_ssl.py <../examples/ssl_clientauth_server.py>`

.. literalinclude:: ../examples/ssl_clientauth_server.py

Client with certificates
~~~~~~~~~~~~~~~~~~~~~~~~

The following client then supplies such a certificate, while still validating the server's identity.

:download:`ssl_clientauth_client.py <../examples/ssl_clientauth_client.py>`

.. literalinclude:: ../examples/ssl_clientauth_client.py


SSL Protocol Options
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
``CertificateOptions`` also supports the older SSLv3 protocol (which may be required interoperate with an existing service or piece of software), just pass ``OpenSSL.SSL.SSLv3_METHOD`` to its initializer:

.. code-block:: python
    from twisted.internet.ssl import CertificateOptions
    from OpenSSL.SSL import SSLv3_METHOD
    options = CertificateOptions(..., method=SSLv3_METHOD)

The somewhat confusingly-named ``OpenSSL.SSL.SSLv23_METHOD`` is also supported (to enable SSLv3 or better, based on negotiation).
SSLv2 is insecure; it is explicitly not supported and will be disabled in all configurations.

Additionally, it is possible to limit the acceptable ciphers for your connection by passing an :api:`twisted.internet.interfaces.IAcceptableCiphers <IAcceptableCiphers>` object to ``CertificateOptions``.
Since Twisted uses a secure cipher configuration by default, it is discouraged to do so unless absolutely necessary.


Related facilities
------------------

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
