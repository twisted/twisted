# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Test L{twisted.web.pages}
"""

from twisted.trial.unittest import SynchronousTestCase
from twisted.web.http_headers import Headers
from twisted.web.pages import ErrorPage, forbidden, notFound
from twisted.web.test.requesthelper import DummyRequest


def _render(resource: ErrorPage) -> DummyRequest:
    """
    Render a response using the given resource.

    @param resource: The resource to use to handle the request.

    @returns: The request that the resource handled,
    """
    request = DummyRequest([b""])
    resource.render(request)
    return request


class ErrorPageTests(SynchronousTestCase):
    """
    Test L{twisted.web.pages.ErrorPage} and its convencience helpers
    L{notFound} and L{forbidden}.
    """

    maxDiff = None

    def assertResponse(self, request: DummyRequest, code: int, body: bytes) -> None:
        self.assertEqual(request.responseCode, code)
        self.assertEqual(
            request.responseHeaders,
            Headers({b"content-type": [b"text/html; charset=utf-8"]}),
        )
        self.assertEqual(
            # Decode to str because unittest somehow still doesn't diff bytes
            # without truncating them in 2022.
            b"".join(request.written).decode("latin-1"),
            body.decode("latin-1"),
        )

    def test_escapesHTML(self):
        """
        The I{brief} and I{detail} parameters are HTML-escaped on render.
        """
        self.assertResponse(
            _render(ErrorPage(400, "A & B", "<script>alert('oops!')")),
            400,
            (
                b"<!DOCTYPE html>\n"
                b"<html><head><title>400 - A &amp; B</title></head>"
                b"<body><h1>A &amp; B</h1><p>&lt;script&gt;alert('oops!')"
                b"</p></body></html>"
            ),
        )

    def test_getChild(self):
        """
        The C{getChild} method of L{ErrorPage} returns the L{ErrorPage} it is
        called on.
        """
        page = ErrorPage(404, "foo", "bar")
        self.assertIs(
            page.getChild(b"name", DummyRequest([b""])),
            page,
        )

    def test_notFoundDefaults(self):
        """
        The default arguments to L{twisted.web.pages.notFound} produce
        a reasonable error page.
        """
        self.assertResponse(
            _render(notFound()),
            404,
            (
                b"<!DOCTYPE html>\n"
                b"<html><head><title>404 - No Such Resource</title></head>"
                b"<body><h1>No Such Resource</h1>"
                b"<p>Sorry. No luck finding that resource.</p>"
                b"</body></html>"
            ),
        )

    def test_forbiddenDefaults(self):
        """
        The default arguments to L{twisted.web.pages.forbidden} produce
        a reasonable error page.
        """
        self.assertResponse(
            _render(forbidden()),
            403,
            (
                b"<!DOCTYPE html>\n"
                b"<html><head><title>403 - Forbidden Resource</title></head>"
                b"<body><h1>Forbidden Resource</h1>"
                b"<p>Sorry, resource is forbidden.</p>"
                b"</body></html>"
            ),
        )
