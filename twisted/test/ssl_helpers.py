
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.


from twisted.internet import ssl
from twisted.python.util import sibpath

from OpenSSL import SSL

class ClientTLSContext(ssl.ClientContextFactory):
    isClient = 1
    def getContext(self):
        return SSL.Context(SSL.TLSv1_METHOD)

class ServerTLSContext:
    isClient = 0
    
    def __init__(self, filename = sibpath(__file__, 'server.pem')):
        self.filename = filename

    def getContext(self):
        ctx = SSL.Context(SSL.TLSv1_METHOD)
        ctx.use_certificate_file(self.filename)
        ctx.use_privatekey_file(self.filename)
        return ctx
