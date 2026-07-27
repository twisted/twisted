# -*- test-case-name: twisted.internet.test.test_endpoints -*-

from __future__ import annotations

from dataclasses import dataclass
from functools import cached_property, partial
from typing import Callable

from zope.interface import implementer

from OpenSSL.crypto import FILETYPE_PEM
from OpenSSL.SSL import Connection, Context

from cryptography.x509 import DNSName, ExtensionOID, load_pem_x509_certificate

from twisted.internet.defer import Deferred
from twisted.internet.interfaces import (
    IListeningPort,
    IOpenSSLServerConnectionCreator,
    IProtocolFactory,
    IReactorTime,
    IStreamServerEndpoint,
)
from twisted.internet.ssl import (
    DN,
    Certificate,
    CertificateOptions,
    KeyPair,
    PrivateCertificate,
)
from twisted.logger import Logger
from twisted.protocols._tls_legacy import SomeConnectionCreator
from twisted.protocols.tls import TLSMemoryBIOFactory, TLSMemoryBIOProtocol
from twisted.python.filepath import FilePath

log = Logger()


def lookupWithWildcard(
    flatLookup: Callable[[bytes | None], Context | None], name: bytes | None
) -> Context | None:
    """
    Look up an OpenSSL context for the given domain name, or construct a
    default one suitable for bootstrapping the connection.
    """
    candidate = flatLookup(name)
    if candidate is None:
        if name is not None:
            segments = name.split(b".")
            segments[0] = b"*"
            wildcardName = b".".join(segments)
            candidate = flatLookup(wildcardName)
    if candidate is None:
        log.warn("no server certificate for name {name!r}", name=name)
    return candidate


@implementer(IOpenSSLServerConnectionCreator)
@dataclass
class SNIConnectionCreator:
    """
    (Private) L{IOpenSSLServerConnectionCreator} implementation that creates an
    OpenSSL connection with a context that will switch to the appropriate one.
    """

    _contextLookup: Callable[[bytes | None], Context | None]
    """
    This method should look up an OpenSSL Context object for the given DNS
    name, or one that is suitable for unidentified clients.  The lookup may
    fail and return None.
    """

    @cached_property
    def defaultContext(self) -> Context:
        """
        Create and cache the OpenSSL context that connections will initially be
        using.  This constructs a default context which doesn't know its domain
        name by delegating to C{self._contextLookup} with None, then sets the
        TLS extension servername callback to get invoked to I{switch} contexts
        by doing another lookup when the client sends its servername.

        @note: The client I{might} never send a servername at all, in which
            case it will be stuck.  This edge case is not handled particularly
            well right now.  Handling it better would involve some changes in
            this code (to hook the handshake completion callback rather than
            just the servername callback) as well as better ability to
            customize which certificate produces the default context in the
            implementation of C{_contextLookup}, which is to say, mostly
            L{PEMObjects}.
        """
        lookedUp = lookupWithWildcard(self._contextLookup, None)
        if lookedUp is None:
            blankOptions = CertificateOptions(
                contextForServerName=partial(
                    lookupWithWildcard,
                    self._contextLookup,
                )
            )
            return blankOptions.getContext()

        return lookedUp

    def serverConnectionForTLS(self, protocol: TLSMemoryBIOProtocol) -> Connection:
        """
        Construct an OpenSSL server connection that can react to the TLS
        servername callback to select an appropriate certificate based on a
        mapping.

        @param protocol: The protocol initiating a TLS connection.

        @return: a newly-created connection.
        """
        return Connection(self.defaultContext)


@implementer(IStreamServerEndpoint)
class TLSServerEndpoint:
    """
    A wrapper L{IStreamServerEndpoint} that can run TLS over an arbitrary other
    L{IStreamServerEndpoint} (most commonly, TCP).
    """

    def __init__(
        self,
        endpoint: IStreamServerEndpoint,
        connectionCreator: SomeConnectionCreator,
        clock: IReactorTime | None = None,
    ) -> None:
        """
        @param endpoint: the endpoint to run over.

        @param connectionCreator: The object that will construct OpenSSL
            connections (or Contexts).

        @param clock: The clock which will be used to schedule buffer flushes.
        """
        self.endpoint = endpoint
        self.connectionCreator = connectionCreator
        self.clock = clock

    def listen(self, factory: IProtocolFactory) -> Deferred[IListeningPort]:
        """
        Begin listening with the given factory.
        """
        return self.endpoint.listen(
            TLSMemoryBIOFactory(
                self.connectionCreator, False, factory, clock=self.clock
            )
        )


def _getSubjectAltNames(c: Certificate) -> list[str]:
    """
    Get all the DNSName SANs for a given certificate.
    """
    return [
        value
        for extension in load_pem_x509_certificate(c.dumpPEM()).extensions
        if extension.oid == ExtensionOID.SUBJECT_ALTERNATIVE_NAME
        for value in extension.value.get_values_for_type(DNSName)
    ]


def autoReloadingDirectoryOfPEMs(
    path: FilePath[str],
) -> Callable[[bytes | None], Context | None]:
    """
    Construct a callable that can look up a HTTPS certificate based on their
    DNS names, by inspecting a directory full of PEM objects.  When
    encountering a lookup failure, the directory will be reloaded, so that if
    new certificates are added they will be picked up.
    """
    # TODO: some flaws with this approach

    """
        1. too much re-scanning; re-reading full file contents for every single
           certificate even if only one has changed.  a mtime/length cache
           would be a good place to start with this

        2. too trusting; we get a network request for a billion certificate
           names per second, we go ahead and do a bunch of work every single
           time (and, see point 1, re-scan and re-parse every single file)

        3. not *enough* re-scanning on the happy path; if certificates go
           stale, we just let them sit there until we get an unknown hostname

        4. we don't look at notAfter/notBefore, so if we find multiple certs,
           we may end up using the wrong one

    """

    certMap: dict[str, CertificateOptions]

    def doReload() -> None:
        nonlocal certMap
        certMap = PEMObjects.fromDirectory(path).inferDomainMapping()

    def lookup(name: bytes | None, shouldReload: bool = True) -> Context | None:
        name = next(iter(certMap.keys()), "").encode() if name in (None, b"") else name
        assert name is not None
        if (options := certMap.get(name.decode())) is not None:
            return options.getContext()
        if not shouldReload:
            return None
        msg = "could not find domain {name}, re-loading {path}"
        log.warn(msg, name=name, path=path)
        doReload()
        return lookup(name, False)

    doReload()
    return lookup


@dataclass
class PEMObjects:
    """
    A collection of objects loaded from a collection of PEM-encoded files.
    """

    _certificates: list[tuple[FilePath[str], Certificate]]
    """
    A list of pairs of (FilePath, Certificate) that indicates what files
    contain what certificates.
    """
    _keyPairs: list[tuple[FilePath[str], KeyPair]]
    """
    A list of pairs of (FilePath, KeyPair) that indicates what pairs contain
    what certificates.
    """

    @classmethod
    def fromDirectory(cls, directory: FilePath[str]) -> PEMObjects:
        """
        Walk through the given directory looking for files with a `.pem`
        extension, and instantiate a L{PEMObjects} containing all certificates
        and key pairs from those files.

        @param directory: a L{FilePath} pointing at a directory in the
            filesystem which may contain some PEM files.
        """
        self = PEMObjects([], [])
        for fp in directory.walk():
            if fp.basename().endswith(".pem") and fp.isfile():
                subself = cls.fromFile(fp)
                self._certificates.extend(subself._certificates)
                self._keyPairs.extend(subself._keyPairs)
        return self

    @classmethod
    def fromFile(cls, fp: FilePath[str]) -> PEMObjects:
        """
        Load some objects from the lines of a single PEM file.

        @param fp: A L{FilePath} pointing at a file on the filesystem whose
            contents should be PEM data.
        """
        certBlobs: list[bytes] = []
        keyBlobs: list[bytes] = []
        blobs = [b""]
        with fp.open() as pemlines:
            for line in pemlines:
                if line.startswith(b"-----BEGIN"):
                    blobs = certBlobs if b"CERTIFICATE" in line else keyBlobs
                    blobs.append(b"")
                blobs[-1] += line
        return cls(
            _keyPairs=[
                (fp, KeyPair.load(keyBlob, FILETYPE_PEM)) for keyBlob in keyBlobs
            ],
            _certificates=[
                (fp, Certificate.loadPEM(certBlob)) for certBlob in certBlobs
            ],
        )

    def inferDomainMapping(self) -> dict[str, CertificateOptions]:
        """
        Return a mapping of DNS name to L{CertificateOptions}.
        """

        privateCerts = []

        certificatesByFingerprint = {
            certificate.getPublicKey().keyHash(): certificate
            for (_, certificate) in self._certificates
        }

        for pairPath, keyPair in self._keyPairs:
            keyHash = keyPair.keyHash()
            matchingCertificate = certificatesByFingerprint.pop(keyHash, None)
            if matchingCertificate is None:
                # log something?
                log.warn(
                    "unused private key at {path} with hash {hash}",
                    path=pairPath.path,
                    hash=keyHash,
                )
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
            for dumped in {each.dump() for each in certificatesByFingerprint.values()}
        ]

        def hashDN(dn: DN) -> tuple[tuple[str, bytes], ...]:
            return tuple(sorted(dn.items()))

        bySubject = {
            hashDN(eachIntermediate.getSubject()): eachIntermediate
            for eachIntermediate in noPrivateKeys
        }

        result: dict[str, CertificateOptions] = {}

        def flatLookup(servername: bytes | None) -> Context | None:
            if servername is None:
                return None
            options = result.get(servername.decode("ascii"))
            if options is not None:
                return options.getContext()
            return None

        def nameToContext(servername: bytes | None) -> Context | None:
            return lookupWithWildcard(flatLookup, servername)

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
                contextForServerName=nameToContext,
            )
            for dnsName in names:
                result[dnsName] = options
        return result
