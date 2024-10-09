from __future__ import annotations

from datetime import datetime, timedelta
from typing import Tuple

from cryptography.hazmat.primitives.asymmetric.rsa import (
    RSAPrivateKey,
    generate_private_key,
)
from cryptography.hazmat.primitives.hashes import SHA256
from cryptography.x509 import (
    BasicConstraints,
    Certificate,
    CertificateBuilder,
    DNSName,
    Name,
    NameAttribute,
    SubjectAlternativeName,
    random_serial_number,
)
from cryptography.x509.oid import NameOID


def buildNew(validAround: datetime) -> CertificateBuilder:
    """
    Common boilerplate necessary for all CertificateBuilders
    """
    return (
        CertificateBuilder()
        .serial_number(random_serial_number())
        .not_valid_before(validAround - timedelta(seconds=300))
        .not_valid_after(validAround + timedelta(seconds=60 * 60 * 24 * 90))
    )


def boilerplate(cn: str, ca: bool) -> Tuple[Name, RSAPrivateKey, CertificateBuilder]:
    """
    Common boilerplate for any certificate.
    """
    nameExt = Name([NameAttribute(NameOID.COMMON_NAME, cn)])
    pk = generate_private_key(key_size=2048, public_exponent=65537)
    return (
        nameExt,
        pk,
        buildNew(datetime.now())
        .add_extension(
            BasicConstraints(ca=ca, path_length=9 if ca else None), critical=True
        )
        .subject_name(nameExt)
        .public_key(pk.public_key()),
    )


def createCA(caName: str) -> Tuple[RSAPrivateKey, Certificate]:
    """
    Create a CA certificate.
    """
    nameExt, pk, builder = boilerplate(caName, True)
    return pk, builder.issuer_name(nameExt).sign(private_key=pk, algorithm=SHA256())


def createIntermediate(
    intermediateName: str, caCert: Certificate, caKey: RSAPrivateKey
) -> Tuple[RSAPrivateKey, Certificate]:
    """
    Create an intermediate CA certificate.
    """
    _, pk, cb = boilerplate(intermediateName, True)
    return pk, cb.issuer_name(caCert.subject).sign(
        private_key=caKey, algorithm=SHA256()
    )


def createLeaf(
    host: str, caCert: Certificate, caKey: RSAPrivateKey
) -> Tuple[RSAPrivateKey, Certificate]:
    """
    Create a leaf certificate for use by a server.
    """
    _, pk, cb = boilerplate(f"leaf for {host}", False)
    return pk, cb.add_extension(
        SubjectAlternativeName([DNSName(host)]), False
    ).issuer_name(caCert.subject).sign(private_key=caKey, algorithm=SHA256())
