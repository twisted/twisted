# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.web.resource}.
"""

from twisted.trial.unittest import TestCase
from twisted.web import error
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



class DeprecatedErrorPageTests(ErrorPageTests):
    """
    Tests for L{error.ErrorPage}, L{error.NoResource}, and
    L{error.ForbiddenResource}.
    """
    def errorPage(self, *args):
        return error.ErrorPage(*args)


    def noResource(self, *args):
        return error.NoResource(*args)


    def forbiddenResource(self, *args):
        return error.ForbiddenResource(*args)


    def _assertWarning(self, name, offendingFunction):
        warnings = self.flushWarnings([offendingFunction])
        self.assertEqual(len(warnings), 1)
        self.assertEqual(warnings[0]['category'], DeprecationWarning)
        self.assertEqual(
            warnings[0]['message'],
            'twisted.web.error.%s is deprecated since Twisted 9.0.  '
            'See twisted.web.resource.%s.' % (name, name))


    def test_getChild(self):
        """
        Like L{ErrorPageTests.test_getChild}, but flush the deprecation warning
        emitted by instantiating L{error.ErrorPage}.
        """
        ErrorPageTests.test_getChild(self)
        self._assertWarning('ErrorPage', self.errorPage)


    def test_errorPageRendering(self):
        """
        Like L{ErrorPageTests.test_errorPageRendering}, but flush the
        deprecation warning emitted by instantiating L{error.ErrorPage}.
        """
        ErrorPageTests.test_errorPageRendering(self)
        self._assertWarning('ErrorPage', self.errorPage)


    def test_noResourceRendering(self):
        """
        Like L{ErrorPageTests.test_noResourceRendering}, but flush the
        deprecation warning emitted by instantiating L{error.NoResource}.
        """
        ErrorPageTests.test_noResourceRendering(self)
        self._assertWarning('NoResource', self.noResource)


    def test_forbiddenResourceRendering(self):
        """
        Like L{ErrorPageTests.test_forbiddenResourceRendering}, but flush the
        deprecation warning emitted by instantiating
        L{error.ForbiddenResource}.
        """
        ErrorPageTests.test_forbiddenResourceRendering(self)
        self._assertWarning('ForbiddenResource', self.forbiddenResource)
