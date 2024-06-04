# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Benchmarks for the C{twisted.web} server.
"""

from twisted.internet.testing import StringTransport
from twisted.web import resource, server


class Data(resource.Resource):
    """
    This is a static, in-memory resource.
    """

    # Being a leaf, we will not have getChild called on this resource.
    isLeaf = True

    def __init__(self, data, type):
        resource.Resource.__init__(self)
        self.data = data
        self.data_len = b"%d" % (len(self.data),)
        self.type = type

    def render_GET(self, request):
        request.setHeader(b"content-type", self.type)
        request.setHeader(b"content-length", self.data_len)
        return self.data


class ComplexData(Data):
    """
    Interact more with the request.
    """

    def render_GET(self, request):
        request.setLastModified(123)
        request.setETag(b"xykjlk")
        _ = request.getRequestHostname()
        request.setHost(b"example.com")
        return Data.render_GET(self, request)


def http11_server_empty_request(resource, benchmark):
    """Benchmark of handling an bodyless HTTP/1.1 request."""
    data = Data(b"This is a result hello hello" * 4, b"text/plain")
    factory = server.Site(data)

    def go():
        transport = StringTransport()
        protocol = factory.buildProtocol(None)
        protocol.makeConnection(transport)
        protocol.dataReceived(
            b"""\
GET / HTTP/1.1
Host: example.com
User-Agent: XXX
Time: XXXX
Content-Length: 0

""".replace(b"\n", b"\r\n")
        )
        assert b"200 OK" in transport.io.getvalue()

    benchmark(go)


def test_http1_server_empty_request(benchmark):
    """Benchmark just returning some data."""
    data = Data(b"This is a result hello hello" * 4, b"text/plain")
    http11_server_empty_request(data, benchmark)


def test_bit_more_complex_response(benchmark):
    """Benchmark that also involves calling more request methods."""
    data = ComplexData(b"This is a result hello hello" * 4, b"text/plain")
    http11_server_empty_request(data, benchmark)


def test_http11_server_many_headers(benchmark):
    """Benchmark handling of an HTTP/1.1 request with many headers."""
    request = b"\r\n".join(
        [
            b"GET / HTTP/1.1",
            b"Host: example.com",
        ]
        + [f"X-{name}: {name}".encode() for name in ("foo", "bar", "Baz", "biff")]
        + [f"x-tab:   {name}\t{name}".encode() for name in ("x", "y", "z", "q")]
        + [
            f"Cookie:   {c}={c * 26}".encode()
            for c in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
        ]
        + [b"", b""]
    )
    data = Data(b"...\n", b"text/plain")
    factory = server.Site(data)

    def go():
        transport = StringTransport()
        protocol = factory.buildProtocol(None)
        protocol.makeConnection(transport)
        protocol.dataReceived(request)
        assert b"200 OK" in transport.io.getvalue()

    benchmark(go)


def test_http11_server_chunked_request(benchmark):
    """
    Benchmark receipt of a largeish chunked request.
    """
    request = (
        b"""\
GET / HTTP/1.1
Host: example.com
user-agent: XXX
Transfer-encoding: chunked

""".replace(b"\n", b"\r\n")
        + b"d\r\nHello, world!\r\n" * 100
        + b"0\r\n\r\n"
    )
    data = Data(b"Goodbye!\n", b"text/plain")
    factory = server.Site(data)

    def go():
        transport = StringTransport()
        protocol = factory.buildProtocol(None)
        protocol.makeConnection(transport)
        protocol.dataReceived(request)
        assert transport.io.getvalue().startswith(b"HTTP/1.1 200 ")

    benchmark(go)


class Chunker(resource.Resource):
    """
    Static data that is written out in chunks.
    """

    isLeaf = True  # no getChild

    def __init__(self, chunks, type):
        resource.Resource.__init__(self)
        self.chunks = chunks
        self.type = type

    def render_GET(self, request):
        request.setHeader(b"Content-Type", self.type)
        for chunk in self.chunks:
            request.write(chunk)
        request.finish()
        return server.NOT_DONE_YET


def test_http11_server_chunked_response(benchmark):
    """
    Benchmark generation of a largeish chunked response.
    """
    data = Chunker(
        [
            bytes([c]) * 1024
            for c in b"abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
        ],
        b"application/octet-stream",
    )
    factory = server.Site(data)

    def go():
        transport = StringTransport()
        protocol = factory.buildProtocol(None)
        protocol.makeConnection(transport)
        protocol.dataReceived(
            b"""\
GET / HTTP/1.1
host: example.com
accept: *

""".replace(b"\n", b"\r\n")
        )
        response = transport.io.getvalue()
        assert response.startswith(b"HTTP/1.1 200 ")
        assert b"Transfer-Encoding: chunked" in response[:1024]

    benchmark(go)
