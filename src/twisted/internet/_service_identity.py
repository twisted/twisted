"""
Conditional imports to enable support for the L{service_identity} module back
to version 18.1.0.
"""

from service_identity import VerificationError

try:
    __import__("service_identity.hazmat")
except ImportError:
    from sys import modules

    for _oldAlias in "common", "_common":
        try:
            import service_identity

            service_identity.hazmat = modules["service_identity.hazmat"] = getattr(
                __import__(f"service_identity.{_oldAlias}"), _oldAlias
            )
        except ImportError:
            pass
from service_identity.hazmat import DNS_ID, IPAddress_ID, verify_service_identity

try:
    from service_identity.hazmat import ServiceID
except ImportError:
    ServiceID = object  # type:ignore[assignment,misc]
try:
    from service_identity.pyopenssl import extract_patterns
except ImportError:
    from service_identity.pyopenssl import extract_ids as extract_patterns
__all__ = [
    "DNS_ID",
    "IPAddress_ID",
    "extract_patterns",
    "ServiceID",
    "VerificationError",
    "verify_service_identity",
]
