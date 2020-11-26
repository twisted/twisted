# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Helper classes for twisted.test.test_ssl.

They are in a separate module so they will not prevent test_ssl importing if
pyOpenSSL is unavailable.
"""

from twisted.python.compat import nativeString
from twisted.internet import ssl
from twisted.python.filepath import FilePath

from OpenSSL import SSL

certPath = nativeString(FilePath(__file__.encode("utf-8")).sibling(b"server.pem").path)


class ClientTLSContext(ssl.ClientContextFactory):
    """
    SSL Context Factory for client-side connections.
    """

    isClient = 1
    _context = None

    def getContext(self):
        if self._context is None:
            self._context = SSL.Context(SSL.SSLv23_METHOD)
        return self._context


class ServerTLSContext:
    """
    SSL Context Factory for server-side connections.
    """

    isClient = 0
    _context = None

    def __init__(self, filename=certPath, method=None):
        self.filename = filename
        if method is None:
            method = SSL.SSLv23_METHOD

        self._method = method

    def getContext(self):
        if self._context is None:
            self._context = SSL.Context(self._method)
            self._context.use_certificate_file(self.filename)
            self._context.use_privatekey_file(self.filename)

        return self._context
