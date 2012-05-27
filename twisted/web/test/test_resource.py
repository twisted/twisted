# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.web.resource}.
"""

from twisted.trial.unittest import TestCase
from twisted.web.http import NOT_FOUND, FORBIDDEN
from twisted.web.resource import ErrorPage, NoResource, ForbiddenResource
from twisted.web.test.test_web import DummyRequest


class ErrorPageTests(TestCase):
    """
    Tests for L{ErrorPage}, L{NoResource}, and L{ForbiddenResource}.
    """

    errorPage = ErrorPage
    noResource = NoResource
    forbiddenResource = ForbiddenResource

    def test_getChild(self):
        """
        The C{getChild} method of L{ErrorPage} returns the L{ErrorPage} it is
        called on.
        """
        page = self.errorPage(321, "foo", "bar")
        self.assertIdentical(page.getChild("name", object()), page)


    def _pageRenderingTest(self, page, code, brief, detail):
        request = DummyRequest([''])
        self.assertEqual(
            page.render(request),
            "\n"
            "<html>\n"
            "  <head><title>%s - %s</title></head>\n"
            "  <body>\n"
            "    <h1>%s</h1>\n"
            "    <p>%s</p>\n"
            "  </body>\n"
            "</html>\n" % (code, brief, brief, detail))
        self.assertEqual(request.responseCode, code)
        self.assertEqual(
            request.outgoingHeaders,
            {'content-type': 'text/html; charset=utf-8'})


    def test_errorPageRendering(self):
        """
        L{ErrorPage.render} returns a C{str} describing the error defined by
        the response code and message passed to L{ErrorPage.__init__}.  It also
        uses that response code to set the response code on the L{Request}
        passed in.
        """
        code = 321
        brief = "brief description text"
        detail = "much longer text might go here"
        page = self.errorPage(code, brief, detail)
        self._pageRenderingTest(page, code, brief, detail)


    def test_noResourceRendering(self):
        """
        L{NoResource} sets the HTTP I{NOT FOUND} code.
        """
        detail = "long message"
        page = self.noResource(detail)
        self._pageRenderingTest(page, NOT_FOUND, "No Such Resource", detail)


    def test_forbiddenResourceRendering(self):
        """
        L{ForbiddenResource} sets the HTTP I{FORBIDDEN} code.
        """
        detail = "longer message"
        page = self.forbiddenResource(detail)
        self._pageRenderingTest(page, FORBIDDEN, "Forbidden Resource", detail)

