#!/usr/bin/env python
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.
"""
https_http_redirect_server
~~~~~~~~~~~~~~~~~~~

This test script demonstrates the usage of the HTTP to HTTPS same port
redirect.

It detect an HTTP request over an HTTPS port and return an HTTP redirection.

Before using this, you should generate a new RSA private key and an associated
X.509 certificate and place it in the working directory as `server-key.pem`
and `server-cert.pem`.

You can generate a self signed certificate using OpenSSL:

    openssl req -new -newkey rsa:2048 -days 3 -nodes -x509 \
        -keyout server-key.pem -out server-cert.pem

To test this, use curl. For example:

    # See HTTP to HTTPS redirection.
    curl -v http://localhost:8443
    # See that HTTPS works
    curl -kv https://localhost:8443
"""

from OpenSSL import crypto

from twisted.internet.endpoints import HTTPSServerEndpoint
from twisted.internet import reactor, ssl
from twisted.python.filepath import FilePath
from twisted.web import static, server

# The port that the server will listen on.
LISTEN_PORT = 8443

privateKeyData = FilePath("server-key.pem").getContent()
privateKey = crypto.load_privatekey(crypto.FILETYPE_PEM, privateKeyData)
certData = FilePath("server-cert.pem").getContent()
certificate = crypto.load_certificate(crypto.FILETYPE_PEM, certData)

options = ssl.CertificateOptions(
    privateKey=privateKey,
    certificate=certificate,
)

site = server.Site(static.File("."))

endpoint = HTTPSServerEndpoint(reactor, LISTEN_PORT, options)
endpoint.listen(site)
reactor.run()
