from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from .tls import TLSMemoryBIOProtocol


class TLSConnection(Protocol):
    def bio_read(self, /, bufsiz: int) -> bytes:
        ...

    def bio_write(self, /, data: bytes) -> int:
        ...

    def bio_shutdown(self) -> None:
        ...

    def do_handshake(self) -> None:
        ...

    def send(self, /, data: bytes) -> int:
        ...

    def recv(self, /, bufsiz: int) -> bytes:
        ...

    def shutdown(self) -> bool:
        ...

    def get_peer_certificate(self) -> object:
        ...

    def get_servername(self) -> bytes | None:
        ...

    def get_alpn_proto_negotiated(self) -> bytes | None:
        ...

    def get_context(self) -> object:
        ...


class TLSBackend(Protocol):
    @property
    def Error(self) -> type[Exception]:
        ...

    @property
    def WantReadError(self) -> type[Exception]:
        ...

    @property
    def WantWriteError(self) -> type[Exception]:
        ...

    @property
    def SysCallError(self) -> type[Exception]:
        ...

    @property
    def ZeroReturnError(self) -> type[Exception]:
        ...

    def createConnection(self, protocol: TLSMemoryBIOProtocol[Any]) -> TLSConnection:
        ...
