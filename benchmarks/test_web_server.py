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

    isLeaf = True

    def getChild(self, name):
        return self

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

""".replace(
                b"\n", b"\r\n"
            )
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
