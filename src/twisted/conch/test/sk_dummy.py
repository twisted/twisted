# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Helper classes for testing security key related features.

Code is based on https://github.com/openssh/openssh-portable/blob/master/regress/misc/sk-dummy/sk-dummy.c
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from enum import Enum

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, ed25519, utils

SK_FLAGS_USER_PRESENCE = 0x01


class SKAlgorithm(Enum):
    """Supported Security Key algorithms."""

    ECDSA = 1
    ED25519 = 2


@dataclass
class EnrollResponse:
    """Structured response for an enrollment operation."""

    public_key: bytes
    key_handle: bytes
    signature: bytes
    attestation_cert: bytes | None = None
    flags: int = 0


@dataclass
class SignResponse:
    """Structured response for a signing operation."""

    flags: int
    counter: int
    signature_r: bytes
    signature_s: bytes | None  # None for Ed25519 algorithm


class SKError(Exception):
    """Custom exception for Security Key errors."""

    pass


class DummySK:
    """
    A dummy software-based implementation of the OpenSSH Security Key API.

    This class mimics the behavior of the `sk-dummy.c` library for testing
    purposes. It simulates a hardware key entirely in software.

    WARNING: This is insecure. The 'key_handle' produced by enroll() is the
    actual private key. Do NOT use this for anything other than testing.
    """

    def enroll(
        self,
        alg: SKAlgorithm,
        challenge: bytes,
        application: str,
        flags: int,
        pin: str | None = None,
    ) -> EnrollResponse:
        """
        Simulates the enrollment of a new security key credential.

        Args:
            alg: The algorithm for the new key (ECDSA or ED25519).
            challenge: The challenge data from the server (unused in dummy).
            application: The application identifier (e.g., "ssh:").
            flags: User presence/verification flags.
            pin: The user's PIN (unused in dummy).

        Returns:
            An EnrollResponse containing the public key and a key_handle.
            The key_handle is the insecurely stored private key.
        """
        if alg == SKAlgorithm.ECDSA:
            ec_private_key = ec.generate_private_key(ec.SECP256R1())

            public_key = ec_private_key.public_key().public_bytes(
                encoding=serialization.Encoding.X962,
                format=serialization.PublicFormat.UncompressedPoint,
            )

            key_handle = ec_private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption(),
            )
        elif alg == SKAlgorithm.ED25519:
            ed_private_key = ed25519.Ed25519PrivateKey.generate()

            public_key = ed_private_key.public_key().public_bytes(
                encoding=serialization.Encoding.Raw,
                format=serialization.PublicFormat.Raw,
            )

            key_handle = ed_private_key.private_bytes(
                encoding=serialization.Encoding.Raw,
                format=serialization.PrivateFormat.Raw,
                encryption_algorithm=serialization.NoEncryption(),
            )
        else:  # pragma: no cover
            raise AssertionError("Unsuported algorithm.")

        return EnrollResponse(
            public_key=public_key,
            key_handle=key_handle,
            signature=b"",
            flags=flags,
        )

    def sign(
        self,
        alg: SKAlgorithm,
        data: bytes,
        application: str,
        key_handle: bytes,
        flags: int,
        pin: str | None = None,
    ) -> SignResponse:
        """
        Simulates signing data with a previously enrolled key.

        Args:
            alg: The signing algorithm.
            data: The data to be signed (typically a session ID or challenge).
            application: The application identifier (e.g., "ssh:").
            key_handle: The key handle returned from the enroll() method.
            flags: User presence/verification flags.
            pin: The user's PIN (unused in dummy).

        Returns:
            A SignResponse containing the signature components.
        """
        message_hash = hashlib.sha256(data).digest()

        counter = 0x12345678

        app_hash = hashlib.sha256(application.encode("utf-8")).digest()
        payload_to_sign = (
            app_hash
            + flags.to_bytes(1, "big")
            + counter.to_bytes(4, "big")
            + message_hash
        )

        if alg == SKAlgorithm.ECDSA:
            private_key = serialization.load_pem_private_key(key_handle, password=None)
            assert isinstance(private_key, ec.EllipticCurvePrivateKey)

            der_signature = private_key.sign(payload_to_sign, ec.ECDSA(hashes.SHA256()))

            r, s = utils.decode_dss_signature(der_signature)

            byte_length = (private_key.curve.key_size + 7) // 8
            sig_r = r.to_bytes(byte_length, "big")
            sig_s = s.to_bytes(byte_length, "big")

            return SignResponse(
                flags=flags, counter=counter, signature_r=sig_r, signature_s=sig_s
            )

        elif alg == SKAlgorithm.ED25519:
            private_key = ed25519.Ed25519PrivateKey.from_private_bytes(key_handle)

            signature = private_key.sign(payload_to_sign)

            return SignResponse(
                flags=flags, counter=counter, signature_r=signature, signature_s=None
            )
        else:  # pragma: no cover
            raise AssertionError("Unsuported algorithm.")
