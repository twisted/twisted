"""
Tests for twisted.protocols._sni.
"""
from __future__ import annotations

from twisted.python.filepath import FilePath
from twisted.python.reflect import requireModule
from twisted.trial.unittest import SynchronousTestCase

skipSSL = ""

if requireModule("OpenSSL"):
    pass

    from cryptography.hazmat.primitives.serialization import (
        Encoding,
        NoEncryption,
        PrivateFormat,
    )

    from twisted.protocols._sni import PEMObjects
    from ._ca_with_intermediate import createCA, createIntermediate, createLeaf
else:
    skipSSL = "OpenSSL is required for SSL tests."

if not skipSSL:
    from twisted.internet import _sslverify as sslverify


class PEMCollectionTests(SynchronousTestCase):
    """
    Tests for collecting PEMs into collections of L{PrivateCertificate}
    objects.
    """

    if skipSSL:
        skip = skipSSL

    def test_inferCertificates(self) -> None:
        """
        Create certificates with different intermediates and verify that
        they're loaded into a single certificate mapping.
        """
        fp = FilePath(self.mktemp())
        rootKey, rootCert = createCA("example CA")
        im1Key, im1Cert = createIntermediate(
            "example intermediate 1", rootCert, rootKey
        )
        im2Key, im2Cert = createIntermediate(
            "example intermediate 2", rootCert, rootKey
        )
        im3Key, im3Cert = createIntermediate("example intermediate 3", im2Cert, im2Key)
        leaf1Key, leaf1Cert = createLeaf("domain1.example.com", im1Cert, im1Key)
        leaf2Key, leaf2Cert = createLeaf("domain2.example.net", im3Cert, im3Key)
        leaf3Key, leaf3Cert = createLeaf("domain3.example.org", rootCert, rootKey)
        fp.makedirs(ignoreExistingDirectory=True)
        randomSubdirectory = fp.child("xyz")
        randomSubdirectory.makedirs()

        im1bytes = im1Cert.public_bytes(Encoding.PEM)
        im2bytes = im2Cert.public_bytes(Encoding.PEM)
        im3bytes = im3Cert.public_bytes(Encoding.PEM)

        l1kbytes = leaf1Key.private_bytes(
            Encoding.PEM, PrivateFormat.PKCS8, NoEncryption()
        )
        l2kbytes = leaf2Key.private_bytes(
            Encoding.PEM, PrivateFormat.PKCS8, NoEncryption()
        )
        l3kbytes = leaf3Key.private_bytes(
            Encoding.PEM, PrivateFormat.PKCS8, NoEncryption()
        )

        l1cbytes = leaf1Cert.public_bytes(Encoding.PEM)
        l2cbytes = leaf2Cert.public_bytes(Encoding.PEM)
        l3cbytes = leaf3Cert.public_bytes(Encoding.PEM)

        everything = [
            im1bytes,
            im2bytes,
            im3bytes,
            l1cbytes,
            l2cbytes,
            l1kbytes,
            l2kbytes,
            l3kbytes,
            l3cbytes,
        ]

        # spray the files somewhat randomly across the hierarchy
        for i, obj in enumerate(everything):
            (fp if (i % 2) else randomSubdirectory).child(f"object-{i}.pem").setContent(
                obj
            )

        objs = PEMObjects.fromDirectory(fp)
        mapping = objs.inferDomainMapping()
        self.assertEqual(
            set(mapping.keys()),
            {"domain1.example.com", "domain2.example.net", "domain3.example.org"},
        )
        domain1 = mapping["domain1.example.com"]
        domain2 = mapping["domain2.example.net"]
        domain3 = mapping["domain3.example.org"]
        self.maxDiff = 9999

        def certBytesCompare(
            twistedCert: sslverify.Certificate, someBytes: bytes
        ) -> None:
            self.assertEqual(twistedCert.dumpPEM().decode(), someBytes.decode())

        self.assertEqual(len(domain1.extraCertChain), 1)
        self.assertEqual(len(domain2.extraCertChain), 2)
        self.assertEqual(len(domain3.extraCertChain), 0)

        certBytesCompare(sslverify.Certificate(domain1.extraCertChain[0]), im1bytes)
        certBytesCompare(sslverify.Certificate(domain2.extraCertChain[1]), im2bytes)
        certBytesCompare(sslverify.Certificate(domain2.extraCertChain[0]), im3bytes)
