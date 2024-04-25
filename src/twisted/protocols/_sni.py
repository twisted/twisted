from __future__ import annotations

from dataclasses import dataclass
from functools import cached_property
from typing import Callable, Dict, Iterable, List, Optional, Tuple

from zope.interface import implementer

from OpenSSL.crypto import FILETYPE_PEM
from OpenSSL.SSL import Connection, Context

import attr

from twisted.internet.defer import Deferred
from twisted.internet.interfaces import (
    IListeningPort,
    IOpenSSLServerConnectionCreator,
    IOpenSSLServerConnectionCreatorFactory,
    IProtocolFactory,
    IStreamServerEndpoint,
)
from twisted.internet.ssl import (
    DN,
    Certificate,
    CertificateOptions,
    KeyPair,
    PrivateCertificate,
)
from twisted.protocols._tls_legacy import SomeConnectionCreator
from twisted.protocols.tls import TLSMemoryBIOFactory, TLSMemoryBIOProtocol
from twisted.python.filepath import FilePath


@implementer(IOpenSSLServerConnectionCreator)
@dataclass
class SNIConnectionCreator(object):
    _configForSNI: ServerNameIndictionConfiguration
    _connectionSetupHook: Callable[[Connection], None]
    _contextSetupHook: Callable[[Context], None]

    def _lookupContext(self, name: Optional[bytes]) -> Context:
        ctxLookup = self._configForSNI._contextLookup
        candidate = ctxLookup(name)
        if candidate is None:
            if name is not None:
                # coverage v
                segments = name.split(b".")
                segments[0] = b"*"
                wildcardName = b".".join(segments)
                candidate = ctxLookup(wildcardName)
                # coverage ^

        if candidate is None:
            # coverage v
            raise KeyError(f"no certificate for domain {name!r}")
            # coverage ^

        self._contextSetupHook(candidate)
        return candidate

    @cached_property
    def defaultContext(self) -> Context:
        defaultContext = self._lookupContext(None)

        def selectContext(connection: Connection) -> None:
            connection.set_context(self._lookupContext(connection.get_servername()))

        defaultContext.set_tlsext_servername_callback(selectContext)
        return defaultContext

    def serverConnectionForTLS(
        self,
        protocol: TLSMemoryBIOProtocol,
    ) -> Connection:
        """
        Construct an OpenSSL server connection.

        @param protocol: The protocol initiating a TLS connection.

        @return: a newly-created connection.
        """
        newConnection = Connection(self.defaultContext)
        self._connectionSetupHook(newConnection)
        return newConnection


@implementer(IOpenSSLServerConnectionCreatorFactory)
@dataclass
class ServerNameIndictionConfiguration:
    """
    L{ServerNameIndictionConfiguration} is an
    L{IOpenSSLServerConnectionCreatorFactory} that creates server connections
    according to a lookup function that can translate a server name specified
    by a client into a L{Context}.
    """

    _contextLookup: Callable[[Optional[bytes]], Optional[Context]]

    def createServerCreator(
        self,
        connectionSetupHook: Callable[[Connection], None],
        contextSetupHook: Callable[[Context], None],
    ) -> IOpenSSLServerConnectionCreator:
        """
        Create an L{SNIConnectionCreator} configured with the C{contextLookup}
        passed to this L{ServerNameIndictionConfiguration} when it was
        constructed.
        """
        return SNIConnectionCreator(self, connectionSetupHook, contextSetupHook)


@implementer(IStreamServerEndpoint)
class TLSServerEndpoint(object):
    def __init__(
        self, endpoint: IStreamServerEndpoint, contextFactory: SomeConnectionCreator
    ) -> None:
        self.endpoint = endpoint
        self.contextFactory = contextFactory

    def listen(self, factory: IProtocolFactory) -> Deferred[IListeningPort]:
        return self.endpoint.listen(
            TLSMemoryBIOFactory(self.contextFactory, False, factory)
        )


def _getSubjectAltNames(c: Certificate) -> List[str]:
    """
    get all the SAN names for a given cert
    """
    from cryptography.x509 import DNSName, ExtensionOID, load_pem_x509_certificate

    return [
        value
        for extension in load_pem_x509_certificate(c.dumpPEM()).extensions
        if extension.oid == ExtensionOID.SUBJECT_ALTERNATIVE_NAME
        for value in extension.value.get_values_for_type(DNSName)
    ]


@attr.s(auto_attribs=True)
class PEMObjects:
    """
    A collection of objects loaded from a PEM encoded file.
    """

    certificates: List[Certificate]
    keyPairs: List[KeyPair]

    @classmethod
    def fromDirectory(cls, directory: FilePath[str]) -> PEMObjects:
        """
        Load a single PEMObjects from all the PEMs in a big directory.
        """
        self = PEMObjects([], [])
        for fp in directory.walk():
            if fp.basename().endswith(".pem") and fp.isfile():
                with fp.open() as f:
                    subself = cls.fromLines(f)
                    self.certificates.extend(subself.certificates)
                    self.keyPairs.extend(subself.keyPairs)
        return self

    @classmethod
    def fromLines(cls, pemlines: Iterable[bytes]) -> PEMObjects:
        """
        Load some objects from the lines of a PEM binary file.
        """
        certBlobs: List[bytes] = []
        keyBlobs: List[bytes] = []
        blobs = [b""]
        for line in pemlines:
            if line.startswith(b"-----BEGIN"):
                blobs = certBlobs if b"CERTIFICATE" in line else keyBlobs
                blobs.append(b"")
            blobs[-1] += line
        return cls(
            keyPairs=[KeyPair.load(keyBlob, FILETYPE_PEM) for keyBlob in keyBlobs],
            certificates=[Certificate.loadPEM(certBlob) for certBlob in certBlobs],
        )

    def inferDomainMapping(self) -> Dict[str, CertificateOptions]:
        """
        Return a mapping of DNS name to L{OpenSSLCertificateOptions}.
        """

        privateCerts = []

        certificatesByFingerprint = dict(
            [
                (certificate.getPublicKey().keyHash(), certificate)
                for certificate in self.certificates
            ]
        )

        for keyPair in self.keyPairs:
            matchingCertificate = certificatesByFingerprint.pop(keyPair.keyHash(), None)
            if matchingCertificate is None:
                # log something?
                continue
            privateCerts.append(
                (
                    _getSubjectAltNames(matchingCertificate),
                    PrivateCertificate.fromCertificateAndKeyPair(
                        matchingCertificate, keyPair
                    ),
                )
            )

        noPrivateKeys = [
            Certificate.load(dumped)
            for dumped in set(
                each.dump() for each in certificatesByFingerprint.values()
            )
        ]

        def hashDN(dn: DN) -> Tuple[Tuple[str, bytes], ...]:
            return tuple(sorted(dn.items()))

        bySubject = {
            hashDN(eachIntermediate.getSubject()): eachIntermediate
            for eachIntermediate in noPrivateKeys
        }

        result = {}
        for names, privateCert in privateCerts:
            chain = []
            chained = privateCert
            while hashDN(chained.getIssuer()) in bySubject:
                chained = bySubject[hashDN(chained.getIssuer())]
                chain.append(chained.original)
            options = CertificateOptions(
                certificate=privateCert.original,
                privateKey=privateCert.privateKey.original,
                extraCertChain=chain,
            )
            for dnsName in names:
                result[dnsName] = options
        return result
