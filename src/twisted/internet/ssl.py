# -*- test-case-name: twisted.test.test_ssl -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
This module implements Transport Layer Security (TLS) support for Twisted.  It
requires U{PyOpenSSL <https://pypi.python.org/pypi/pyOpenSSL>}.

If you wish to establish a TLS connection, please use one of the following
APIs:

    - SSL endpoints for L{servers
      <twisted.internet.endpoints.SSL4ServerEndpoint>} and L{clients
      <twisted.internet.endpoints.SSL4ClientEndpoint>}

    - L{startTLS <twisted.internet.interfaces.ITLSTransport.startTLS>}

    - L{connectSSL <twisted.internet.interfaces.IReactorSSL.connectSSL>}

    - L{listenSSL <twisted.internet.interfaces.IReactorSSL.listenSSL>}

These APIs all require a C{contextFactory} argument that specifies their
security properties, such as certificate, private key, certificate authorities
to verify the peer, allowed TLS protocol versions, cipher suites, and so on.
The recommended value for this argument is a L{CertificateOptions} instance;
see its documentation for an explanation of the available options.

The C{contextFactory} name is a bit of an anachronism now, as context factories
have been replaced with "connection creators", but these objects serve the same
role.

Be warned that implementing your own connection creator (i.e.: value for the
C{contextFactory}) is both difficult and dangerous; the Twisted team has worked
hard to make L{CertificateOptions}' API comprehensible and unsurprising, and
the Twisted team is actively maintaining it to ensure that it becomes more
secure over time.

If you are really absolutely sure that you want to take on the risk of
implementing your own connection creator based on the pyOpenSSL API, see the
L{server connection creator
<twisted.internet.interfaces.IOpenSSLServerConnectionCreator>} and L{client
connection creator
<twisted.internet.interfaces.IOpenSSLServerConnectionCreator>} interfaces.

Developers using Twisted, please ignore the L{Port}, L{Connector}, and
L{Client} classes defined here, as these are details of certain reactors' TLS
implementations, exposed by accident (and remaining here only for compatibility
reasons).  If you wish to establish a TLS connection, please use one of the
APIs listed above.

@note: "SSL" (Secure Sockets Layer) is an antiquated synonym for "TLS"
    (Transport Layer Security).  You may see these terms used interchangeably
    throughout the documentation.
"""

from __future__ import annotations

from zope.interface import implementedBy, implementer, implementer_only

# System imports
from OpenSSL import SSL

from constantly import FlagConstant, Flags
from incremental import Version

# Twisted imports
from twisted.internet import interfaces, tcp
from twisted.python.deprecate import deprecated, deprecatedModuleAttribute

supported = True


@implementer(interfaces.IOpenSSLContextFactory)
class ContextFactory:
    """A factory for SSL context objects, for server SSL connections."""

    isClient = 0

    def getContext(self):
        """Return a SSL.Context object. override in subclasses."""
        raise NotImplementedError


class DefaultOpenSSLContextFactory(ContextFactory):
    """
    L{DefaultOpenSSLContextFactory} is a factory for server-side SSL context
    objects.  These objects define certain parameters related to SSL
    handshakes and the subsequent connection.

    @ivar _contextFactory: A callable which will be used to create new
        context objects.  This is typically L{OpenSSL.SSL.Context}.
    """

    _context = None

    def __init__(
        self,
        privateKeyFileName,
        certificateFileName,
        sslmethod=SSL.TLS_METHOD,
        _contextFactory=SSL.Context,
    ):
        """
        @param privateKeyFileName: Name of a file containing a private key
        @param certificateFileName: Name of a file containing a certificate
        @param sslmethod: The SSL method to use
        """
        self.privateKeyFileName = privateKeyFileName
        self.certificateFileName = certificateFileName
        self.sslmethod = sslmethod
        self._contextFactory = _contextFactory

        # Create a context object right now.  This is to force validation of
        # the given parameters so that errors are detected earlier rather
        # than later.
        self.cacheContext()

    def cacheContext(self):
        if self._context is None:
            ctx = self._contextFactory(self.sslmethod)
            # Disallow SSLv2!  It's insecure!  SSLv3 has been around since
            # 1996.  It's time to move on.
            ctx.set_options(SSL.OP_NO_SSLv2)
            ctx.use_certificate_file(self.certificateFileName)
            ctx.use_privatekey_file(self.privateKeyFileName)
            self._context = ctx

    def __getstate__(self):
        d = self.__dict__.copy()
        del d["_context"]
        return d

    def __setstate__(self, state):
        self.__dict__ = state

    def getContext(self):
        """
        Return an SSL context.
        """
        return self._context


@implementer(interfaces.IOpenSSLContextFactory)
class ClientContextFactory:
    """A context factory for SSL clients."""

    isClient = 1

    # TLS_METHOD allows negotiation of multiple TLS versions.
    method = SSL.TLS_METHOD

    _contextFactory = SSL.Context

    def getContext(self):
        ctx = self._contextFactory(self.method)
        ctx.set_options(
            SSL.OP_NO_SSLv2 | SSL.OP_NO_SSLv3 | SSL.OP_NO_TLSv1 | SSL.OP_NO_TLSv1_1
        )
        return ctx


@implementer_only(
    interfaces.ISSLTransport,
    *(i for i in implementedBy(tcp.Client) if i != interfaces.ITLSTransport),
)
class Client(tcp.Client):
    """
    I am an SSL client.
    """

    def __init__(self, host, port, bindAddress, ctxFactory, connector, reactor=None):
        # tcp.Client.__init__ depends on self.ctxFactory being set
        self.ctxFactory = ctxFactory
        tcp.Client.__init__(self, host, port, bindAddress, connector, reactor)

    def _connectDone(self):
        self.startTLS(self.ctxFactory)
        self.startWriting()
        tcp.Client._connectDone(self)


@implementer(interfaces.ISSLTransport)
class Server(tcp.Server):
    """
    I am an SSL server.
    """

    server: Port

    def __init__(self, *args, **kwargs):
        tcp.Server.__init__(self, *args, **kwargs)
        self.startTLS(self.server.ctxFactory)

    def getPeerCertificate(self):
        # ISSLTransport.getPeerCertificate
        raise NotImplementedError("Server.getPeerCertificate")


class Port(tcp.Port):
    """
    I am an SSL port.
    """

    transport = Server

    _type = "TLS"

    def __init__(
        self, port, factory, ctxFactory, backlog=50, interface="", reactor=None
    ):
        tcp.Port.__init__(self, port, factory, backlog, interface, reactor)
        self.ctxFactory = ctxFactory

    def _getLogPrefix(self, factory):
        """
        Override the normal prefix to include an annotation indicating this is a
        port for TLS connections.
        """
        return tcp.Port._getLogPrefix(self, factory) + " (TLS)"


class Connector(tcp.Connector):
    def __init__(
        self, host, port, factory, contextFactory, timeout, bindAddress, reactor=None
    ):
        self.contextFactory = contextFactory
        tcp.Connector.__init__(self, host, port, factory, timeout, bindAddress, reactor)

        # Force some parameter checking in pyOpenSSL.  It's better to fail now
        # than after we've set up the transport.
        contextFactory.getContext()

    def _makeTransport(self):
        return Client(
            self.host,
            self.port,
            self.bindAddress,
            self.contextFactory,
            self,
            self.reactor,
        )


from twisted.internet._sslverify import (
    DN,
    Certificate,
    CertificateRequest,
    DistinguishedName,
    KeyPair,
    OpenSSLAcceptableCiphers as AcceptableCiphers,
    OpenSSLCertificateOptions as CertificateOptions,
    OpenSSLDefaultPaths,
    OpenSSLDiffieHellmanParameters as DiffieHellmanParameters,
    PrivateCertificate,
    TLSVersion,
    VerificationError,
    optionsForClientTLS,
    platformTrust,
    trustRootFromCertificates,
)


class ProtocolNegotiationSupport(Flags):
    """
    L{ProtocolNegotiationSupport} defines flags which are used to indicate the
    level of ALPN support provided by the TLS backend.

    @cvar NOSUPPORT: There is no support for ALPN.  This is exclusive with
        L{ALPN}.

    @cvar NPN: The implementation supports Next Protocol Negotiation.  (This
        flag is provided for compatibility only; Twisted no longer supports
        Next Protocol Negotiation)

    @cvar ALPN: The implementation supports Application Layer Protocol
        Negotiation.
    """

    NPN = FlagConstant(0x0001)
    ALPN = FlagConstant(0x0002)


# FIXME: https://twistedmatrix.com/trac/ticket/8074
# Currently flags with literal zero values behave incorrectly. However,
# creating a flag by NOTing a flag with itself appears to work totally fine, so
# do that instead.
ProtocolNegotiationSupport.NOSUPPORT = (
    ProtocolNegotiationSupport.NPN ^ ProtocolNegotiationSupport.NPN
)


@deprecated(Version("Twisted", 26, 10, 0, release_candidate=1))
def protocolNegotiationMechanisms() -> FlagConstant:
    """
    Check whether the installed versions of pyOpenSSL and OpenSSL are recent
    enough to support ALPN.

    @return: A combination of flags from L{ProtocolNegotiationSupport} that
        indicate which mechanisms for protocol negotiation are supported.
    """
    support = ProtocolNegotiationSupport.NOSUPPORT
    ctx = SSL.Context(SSL.SSLv23_METHOD)

    try:
        ctx.set_alpn_select_callback(lambda connection, protocols: protocols[0])
    except (AttributeError, NotImplementedError):  # pragma: no cover
        # All supported versions pyOpenSSL and OpenSSL support ALPN.
        # Keep this legacy fallback until this deprecated function is removed.
        pass
    else:
        support |= ProtocolNegotiationSupport.ALPN

    return support


deprecatedModuleAttribute(
    Version("Twisted", 26, 10, 0, release_candidate=1),
    "All supported TLS backends provide ALPN. There is no need to check for support.",
    __name__,
    ProtocolNegotiationSupport.__name__,
)

__all__ = [
    "ContextFactory",
    "DefaultOpenSSLContextFactory",
    "ClientContextFactory",
    "DistinguishedName",
    "DN",
    "Certificate",
    "CertificateRequest",
    "PrivateCertificate",
    "KeyPair",
    "AcceptableCiphers",
    "CertificateOptions",
    "DiffieHellmanParameters",
    "platformTrust",
    "OpenSSLDefaultPaths",
    "TLSVersion",
    "VerificationError",
    "optionsForClientTLS",
    "ProtocolNegotiationSupport",
    "protocolNegotiationMechanisms",
    "trustRootFromCertificates",
]
