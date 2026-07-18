"""
Internal platform-integration fakes that are not mature enough for
L{twisted.internet.testing} just yet.
"""

import socket
from dataclasses import dataclass, field

from twisted.trial.unittest import SynchronousTestCase


@dataclass
class SocketState:
    """
    State associated with a L{FakeSocket} for manipulation and inspection by
    tests.
    """

    receiveBuffer: bytes = b""
    sendBuffer: list[bytes] = field(default_factory=list)
    blocking: bool = True


@dataclass
class FakeSocket:
    """
    A fake for L{socket.socket} objects.

    @ivar data: A C{str} giving the data which will be returned from
        L{FakeSocket.recv}.

    @ivar sendBuffer: A C{list} of the objects passed to L{FakeSocket.send}.
    """

    _state: SocketState

    def setblocking(self, blocking: bool) -> None:
        self._state.blocking = blocking

    def recv(self, size: int) -> bytes:
        return self._state.receiveBuffer

    def send(self, data: bytes) -> int:
        """
        I{Send} all of C{bytes} by accumulating it into the associated L{SocketState.sendBuffer}.

        @return: The length of C{bytes}, indicating all the data has been
            accepted.
        """
        self._state.sendBuffer.append(data)
        return len(data)

    def shutdown(self, how: int) -> None:
        """
        Shutdown is not implemented.  The method is provided since real sockets
        have it and some code expects it.  No behavior of L{FakeSocket} is
        affected by a call to it.
        """

    def close(self) -> None:
        """
        Close is not implemented.  The method is provided since real sockets
        have it and some code expects it.  No behavior of L{FakeSocket} is
        affected by a call to it.
        """

    def setsockopt(
        self, level: int, optname: int, value: int | bytes | None, optlen: int = 0
    ) -> None:
        """
        Setsockopt is not implemented.  The method is provided since
        real sockets have it and some code expects it.  No behavior of
        L{FakeSocket} is affected by a call to it.
        """

    def fileno(self) -> int:
        """
        Return a fake file descriptor.  If actually used, this will have no
        connection to this L{FakeSocket} and will probably cause surprising
        results.
        """
        return 1


def newFakeSocket(recvBuf: bytes = b"") -> tuple[SocketState, socket.socket]:
    state = SocketState(receiveBuffer=recvBuf)
    fake: socket.socket = FakeSocket(state)  # type:ignore[assignment]
    return state, fake


class FakeSocketTests(SynchronousTestCase):
    """
    Test that the FakeSocket can be used by the doRead method of L{Connection}
    """

    def test_blocking(self) -> None:
        state, skt = newFakeSocket(b"someData")
        skt.setblocking(False)
        self.assertEqual(state.blocking, False)

    def test_recv(self) -> None:
        state, skt = newFakeSocket(b"someData")
        self.assertEqual(skt.recv(10), b"someData")

    def test_send(self) -> None:
        """
        L{FakeSocket.send} accepts the entire string passed to it, adds it to
        its send buffer, and returns its length.
        """
        state, skt = newFakeSocket(b"")
        count = skt.send(b"foo")
        self.assertEqual(count, 3)
        self.assertEqual(state.sendBuffer, [b"foo"])
