# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
A test harness for twisted.web2.resource.
"""

from sets import Set as set

from zope.interface import implements

from twisted.internet.defer import succeed, fail
from twisted.trial import unittest
from twisted.web2 import responsecode
from twisted.web2.iweb import IResource
from twisted.web2.http import Response
from twisted.web2.stream import MemoryStream
from twisted.web2.resource import RenderMixin, LeafResource
from twisted.web2.server import Site, StopTraversal
from twisted.web2.test.test_server import SimpleRequest

class PreconditionError (Exception):
    "Precondition Failure"

class TestResource (RenderMixin):
    implements(IResource)

    def _handler(self, request):
        if request is None:
            return responsecode.INTERNAL_SERVER_ERROR
        return responsecode.NO_CONTENT

    http_BLEARGH       = _handler
    http_HUCKHUCKBLORP = _handler
    http_SWEETHOOKUPS  = _handler
    http_HOOKUPS       = _handler

    def preconditions_BLEARGH(self, request):
        raise PreconditionError()

    def precondition_HUCKHUCKBLORP(self, request):
        return fail(None)

    def preconditions_SWEETHOOKUPS(self, request):
        return None

    def preconditions_HOOKUPS(self, request):
        return succeed(None)

    renderOutput = "Snootch to the hootch"

    def render(self, request):
        response = Response()
        response.stream = MemoryStream(self.renderOutput)
        return response

def generateResponse(method):
    resource = TestResource()
    method = getattr(resource, "http_" + method)
    return method(SimpleRequest(Site(resource), method, "/"))

class RenderMixInTestCase (unittest.TestCase):
    """
    Test RenderMixin.
    """
    _my_allowed_methods = set((
        "HEAD", "OPTIONS", "TRACE", "GET",
        "BLEARGH", "HUCKHUCKBLORP",
        "SWEETHOOKUPS", "HOOKUPS",
    ))

    def test_allowedMethods(self):
        """
        RenderMixin.allowedMethods()
        """
        self.assertEquals(
            set(TestResource().allowedMethods()),
            self._my_allowed_methods
        )

    def test_checkPreconditions_raises(self):
        """
        RenderMixin.checkPreconditions()
        Exception raised in checkPreconditions()
        """
        resource = TestResource()
        request = SimpleRequest(Site(resource), "BLEARGH", "/")

        # Check that checkPreconditions raises as expected
        self.assertRaises(PreconditionError, resource.checkPreconditions, request)

        # Check that renderHTTP calls checkPreconditions
        self.assertRaises(PreconditionError, resource.renderHTTP, request)

    def test_checkPreconditions_none(self):
        """
        RenderMixin.checkPreconditions()
        checkPreconditions() returns None
        """
        resource = TestResource()
        request = SimpleRequest(Site(resource), "SWEETHOOKUPS", "/")

        # Check that checkPreconditions without a raise doesn't barf
        self.assertEquals(resource.renderHTTP(request), responsecode.NO_CONTENT)

    def test_checkPreconditions_deferred(self):
        """
        RenderMixin.checkPreconditions()
        checkPreconditions() returns a deferred
        """
        resource = TestResource()
        request = SimpleRequest(Site(resource), "HOOKUPS", "/")

        # Check that checkPreconditions without a raise doesn't barf
        def checkResponse(response):
            self.assertEquals(response, responsecode.NO_CONTENT)

        d = resource.renderHTTP(request)
        d.addCallback(checkResponse)

    def test_OPTIONS_status(self):
        """
        RenderMixin.http_OPTIONS()
        Response code is OK
        """
        response = generateResponse("OPTIONS")
        self.assertEquals(response.code, responsecode.OK)

    def test_OPTIONS_allow(self):
        """
        RenderMixin.http_OPTIONS()
        Allow header indicates allowed methods
        """
        response = generateResponse("OPTIONS")
        self.assertEquals(
            set(response.headers.getHeader("allow")),
            self._my_allowed_methods
        )

    def test_TRACE_status(self):
        """
        RenderMixin.http_TRACE()
        Response code is OK
        """
        response = generateResponse("TRACE")
        self.assertEquals(response.code, responsecode.OK)

    def test_TRACE_body(self):
        """
        RenderMixin.http_TRACE()
        Check body for traciness
        """
        raise NotImplementedError()

    test_TRACE_body.todo = "Someone should write this test"

    def test_HEAD_status(self):
        """
        RenderMixin.http_HEAD()
        Response code is OK
        """
        response = generateResponse("HEAD")
        self.assertEquals(response.code, responsecode.OK)

    def test_HEAD_body(self):
        """
        RenderMixin.http_HEAD()
        Check body is empty
        """
        response = generateResponse("HEAD")
        self.assertEquals(response.stream.length, 0)

    test_HEAD_body.todo = (
        "http_HEAD is implemented in a goober way that "
        "relies on the server code to clean up after it."
    )

    def test_GET_status(self):
        """
        RenderMixin.http_GET()
        Response code is OK
        """
        response = generateResponse("GET")
        self.assertEquals(response.code, responsecode.OK)

    def test_GET_body(self):
        """
        RenderMixin.http_GET()
        Check body is empty
        """
        response = generateResponse("GET")
        self.assertEquals(
            str(response.stream.read()),
            TestResource.renderOutput
        )

class ResourceTestCase (unittest.TestCase):
    """
    Test Resource.
    """
    def test_addSlash(self):
        # I think this would include a test of http_GET()
        raise NotImplementedError()
    test_addSlash.todo = "Someone should write this test"

    def test_locateChild(self):
        raise NotImplementedError()
    test_locateChild.todo = "Someone should write this test"

    def test_child_nonsense(self):
        raise NotImplementedError()
    test_child_nonsense.todo = "Someone should write this test"

class PostableResourceTestCase (unittest.TestCase):
    """
    Test PostableResource.
    """
    def test_POST(self):
        raise NotImplementedError()
    test_POST.todo = "Someone should write this test"

class LeafResourceTestCase (unittest.TestCase):
    """
    Test LeafResource.
    """
    def test_locateChild(self):
        resource = LeafResource()
        child, segments = (
            resource.locateChild(
                SimpleRequest(Site(resource), "GET", "/"),
                ("", "foo"),
            )
        )
        self.assertEquals(child, resource)
        self.assertEquals(segments, StopTraversal)

class WrapperResourceTestCase (unittest.TestCase):
    """
    Test WrapperResource.
    """
    def test_hook(self):
        raise NotImplementedError()
    test_hook.todo = "Someone should write this test"
