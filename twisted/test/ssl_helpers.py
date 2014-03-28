# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Helper classes for TLS test cases in L{twisted.test.test_ssl},
L{twisted.test.test_sslverify}, L{twisted.protocols.test.test_tls}, et.  al.

They are in a separate module so they will not prevent test_ssl importing if
pyOpenSSL is unavailable.
"""
from __future__ import division, absolute_import

import itertools

from twisted.python.compat import nativeString
from twisted.internet import ssl, protocol
from twisted.python.filepath import FilePath
from twisted.test.iosim import connectedServerAndClient
from twisted.protocols.tls import TLSMemoryBIOFactory


from OpenSSL import SSL
from OpenSSL.crypto import PKey, X509, TYPE_RSA, FILETYPE_PEM
from twisted.internet.protocol import ClientFactory, Protocol, ServerFactory

certPath = nativeString(FilePath(__file__.encode("utf-8")
                    ).sibling(b"server.pem").path)



def counter(counter=itertools.count()):
    """
    Each time we're called, return the next integer in the natural numbers.
    """
    return next(counter)



class ClientTLSContext(ssl.ClientContextFactory):
    isClient = 1
    def getContext(self):
        return SSL.Context(SSL.TLSv1_METHOD)

class ServerTLSContext:
    isClient = 0

    def __init__(self, filename=certPath):
        self.filename = filename

    def getContext(self):
        ctx = SSL.Context(SSL.TLSv1_METHOD)
        ctx.use_certificate_file(self.filename)
        ctx.use_privatekey_file(self.filename)
        return ctx


def makeCertificate(**kw):
    """
    Create a certificate.
    """
    keypair = PKey()
    keypair.generate_key(TYPE_RSA, 768)

    certificate = X509()
    certificate.gmtime_adj_notBefore(0)
    certificate.gmtime_adj_notAfter(60 * 60 * 24 * 365) # One year
    for xname in certificate.get_issuer(), certificate.get_subject():
        for (k, v) in kw.items():
            setattr(xname, k, nativeString(v))

    certificate.set_serial_number(counter())
    certificate.set_pubkey(keypair)
    certificate.sign(keypair, "md5")

    return keypair, certificate



def certificatesForAuthorityAndServer():
    """
    Create a self-signed CA certificate and server certificate signed by the
    CA.

    @return: a 2-tuple of C{(certificate_authority_certificate,
        server_certificate)}
    @rtype: L{tuple} of (L{ssl.Certificate}, L{ssl.PrivateCertificate})
    """
    serverDN = ssl.DistinguishedName(commonName='example.com')
    serverKey = ssl.KeyPair.generate()
    serverCertReq = serverKey.certificateRequest(serverDN)

    caDN = ssl.DistinguishedName(commonName='CA')
    caKey= ssl.KeyPair.generate()
    caCertReq = caKey.certificateRequest(caDN)
    caSelfCertData = caKey.signCertificateRequest(
            caDN, caCertReq, lambda dn: True, 516)
    caSelfCert = caKey.newCertificate(caSelfCertData)

    serverCertData = caKey.signCertificateRequest(
            caDN, serverCertReq, lambda dn: True, 516)
    serverCert = serverKey.newCertificate(serverCertData)
    return caSelfCert, serverCert



def loopbackTLSConnection(trustRoot, privateKeyFile, chainedCertFile=None):
    """
    Create a loopback TLS connection with the given trust and keys.

    @param trustRoot: the C{trustRoot} argument for the client connection's
        context.
    @type trustRoot: L{twisted.internet._sslverify.IOpenSSLTrustRoot} or
        something adaptable to it.

    @param privateKeyFile: The name of the file containing the private key.
    @type privateKeyFile: L{str} (native string; file name)

    @param chainedCertFile: The name of the chained certificate file.
    @type chainedCertFile: L{str} (native string; file name)

    @return: 3-tuple of server-protocol, client-protocol, and L{IOPump}
    @rtype: L{tuple}
    """
    class ContextFactory(object):
        def getContext(self):
            """
            Create a context for the server side of the connection.

            @return: an SSL context using a certificate and key.
            @rtype: C{OpenSSL.SSL.Context}
            """
            ctx = SSL.Context(SSL.TLSv1_METHOD)
            if chainedCertFile is not None:
                ctx.use_certificate_chain_file(chainedCertFile)
            ctx.use_privatekey_file(privateKeyFile)
            # Let the test author know if they screwed something up.
            ctx.check_privatekey()
            return ctx

    class GreetingServer(protocol.Protocol):
        greeting = b"greetings!"
        def connectionMade(self):
            self.transport.write(self.greeting)

    class ListeningClient(protocol.Protocol):
        data = b''
        lostReason = None
        def dataReceived(self, data):
            self.data += data
        def connectionLost(self, reason):
            self.lostReason = reason

    serverOpts = ContextFactory()
    clientOpts = ssl.CertificateOptions(trustRoot=trustRoot)

    clientFactory = TLSMemoryBIOFactory(
        clientOpts, isClient=True,
        wrappedFactory=protocol.Factory.forProtocol(GreetingServer)
    )
    serverFactory = TLSMemoryBIOFactory(
        serverOpts, isClient=False,
        wrappedFactory=protocol.Factory.forProtocol(ListeningClient)
    )

    return connectedServerAndClient(
        lambda: serverFactory.buildProtocol(None),
        lambda: clientFactory.buildProtocol(None)
    )



def pathContainingDumpOf(testCase, *dumpables):
    """
    Create a temporary file to store some serializable-as-PEM objects in, and
    return its name.

    @param testCase: a test case to use for generating a temporary directory.
    @type testCase: L{twisted.trial.unittest.TestCase}

    @param dumpables: arguments are objects from pyOpenSSL with a C{dump}
        method, taking a pyOpenSSL file-type constant, such as
        L{OpenSSL.crypto.FILETYPE_PEM} or L{OpenSSL.crypto.FILETYPE_ASN1}.
    @type dumpables: L{tuple} of L{object} with C{dump} method taking L{int}
        returning L{bytes}

    @return: the path to a file where all of the dumpables were dumped in PEM
        format.
    @rtype: L{str}
    """
    fname = testCase.mktemp()
    with open(fname, "wb") as f:
        for dumpable in dumpables:
            f.write(dumpable.dump(FILETYPE_PEM))
    return fname


def handshakeProtocols():
    """
    Start handshake between TLS client and server.
    """
    clientFactory = ClientFactory()
    clientFactory.protocol = Protocol

    clientContextFactory = ssl.CertificateOptions(method=SSL.TLSv1_METHOD)
    wrapperFactory = TLSMemoryBIOFactory(
        clientContextFactory, True, clientFactory)
    sslClientProtocol = wrapperFactory.buildProtocol(None)
    handshakeDeferred = sslClientProtocol.whenHandshakeDone()

    serverFactory = ServerFactory()
    serverFactory.protocol = Protocol

    serverContextFactory = ServerTLSContext()
    wrapperFactory = TLSMemoryBIOFactory(
        serverContextFactory, False, serverFactory)
    sslServerProtocol = wrapperFactory.buildProtocol(None)



