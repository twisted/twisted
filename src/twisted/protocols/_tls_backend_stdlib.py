import ssl
from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable, ClassVar

if TYPE_CHECKING:
    from ._tls_backend_abstract import TLSBackend, TLSConnection
    from .tls import TLSMemoryBIOProtocol


@dataclass(frozen=True)
class StdlibSSLConnection:
    _inbio: ssl.MemoryBIO
    _outbio: ssl.MemoryBIO
    _connection: ssl.SSLObject

    def bio_read(self, /, bufsiz: int) -> bytes:
        return self._outbio.read(bufsiz)

    def bio_write(self, /, data: bytes) -> int:
        return self._inbio.write(data)

    def bio_shutdown(self) -> None:
        self._inbio.write_eof()

    def do_handshake(self) -> None:
        self._connection.do_handshake()

    def send(self, /, data: bytes) -> int:
        return self._connection.write(data)

    def recv(self, /, bufsiz: int) -> bytes:
        return self._connection.read(bufsiz)

    def shutdown(self) -> bool:
        self._connection.unwrap()
        return True

    def get_peer_certificate(self) -> object:
        return self._connection.getpeercert()

    def get_servername(self) -> bytes | None:
        name = self._connection.server_hostname
        return name.encode("ascii") if name is not None else None

    def get_alpn_proto_negotiated(self) -> bytes | None:
        name = self._connection.selected_alpn_protocol()
        return name.encode("ascii") if name is not None else None

    def get_context(self) -> object:
        return self._connection.context


@dataclass(frozen=True)
class StdlibSSLBackend:
    _stdlibMaker: Callable[[ssl.MemoryBIO, ssl.MemoryBIO], ssl.SSLObject]
    Error: ClassVar[type[Exception]] = ssl.SSLError
    WantReadError: ClassVar[type[Exception]] = ssl.SSLWantReadError
    WantWriteError: ClassVar[type[Exception]] = ssl.SSLWantWriteError
    SysCallError: ClassVar[type[Exception]] = ssl.SSLSyscallError
    ZeroReturnError: ClassVar[type[Exception]] = ssl.SSLZeroReturnError

    def createConnection(self, protocol: TLSMemoryBIOProtocol) -> TLSConnection:
        inbio = ssl.MemoryBIO()
        outbio = ssl.MemoryBIO()
        obj = self._stdlibMaker(inbio, outbio)
        return StdlibSSLConnection(inbio, outbio, obj)


if TYPE_CHECKING:
    _: type[TLSBackend] = StdlibSSLBackend
