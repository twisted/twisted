from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar

import OpenSSL

if TYPE_CHECKING:
    from ._tls_backend_abstract import TLSBackend, TLSConnection
    from .tls import TLSMemoryBIOProtocol


@dataclass(frozen=True)
class PyOpenSSLBackend:
    createConnection: Callable[[TLSMemoryBIOProtocol], TLSConnection]

    Error: ClassVar[type[Exception]] = OpenSSL.SSL.Error
    WantReadError: ClassVar[type[Exception]] = OpenSSL.SSL.WantReadError
    WantWriteError: ClassVar[type[Exception]] = OpenSSL.SSL.WantWriteError
    SysCallError: ClassVar[type[Exception]] = OpenSSL.SSL.SysCallError
    ZeroReturnError: ClassVar[type[Exception]] = OpenSSL.SSL.ZeroReturnError


if TYPE_CHECKING:
    _: type[TLSBackend] = PyOpenSSLBackend
