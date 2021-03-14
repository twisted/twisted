# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
General helpers for L{twisted.web} unit tests.
"""


from twisted.internet.defer import succeed
from twisted.web import server
from twisted.trial.unittest import TestCase
from twisted.python.failure import Failure

from twisted.web._flatten import flattenString
from twisted.web.error import FlattenerError


def _render(resource, request):
    result = resource.render(request)
    if isinstance(result, bytes):
        request.write(result)
        request.finish()
        return succeed(None)
    elif result is server.NOT_DONE_YET:
        if request.finished:
            return succeed(None)
        else:
            return request.notifyFinish()
    else:
        raise ValueError(f"Unexpected return value: {result!r}")


class FlattenTestCase(TestCase):
    """
    A test case that assists with testing L{twisted.web._flatten}.
    """

    def assertFlattensTo(self, root, target):
        """
        Assert that a root element, when flattened, is equal to a string.
        """
        d = flattenString(None, root)
        d.addCallback(lambda s: self.assertEqual(s, target))
        return d

    def assertFlattensImmediately(self, root, target):
        """
        Assert that a root element, when flattened, is equal to a string, and
        performs no asynchronus Deferred anything.

        This version is more convenient in tests which wish to make multiple
        assertions about flattening, since it can be called multiple times
        without having to add multiple callbacks.

        @return: the result of rendering L{root}, which should be equivalent to
            L{target}.
        @rtype: L{bytes}
        """
        results = []
        it = self.assertFlattensTo(root, target)
        it.addBoth(results.append)
        # Do our best to clean it up if something goes wrong.
        self.addCleanup(it.cancel)
        if not results:
            self.fail("Rendering did not complete immediately.")
        result = results[0]
        if isinstance(result, Failure):
            result.raiseException()
        return results[0]

    def assertFlatteningRaises(self, root, exn):
        """
        Assert flattening a root element raises a particular exception.
        """
        d = self.assertFailure(self.assertFlattensTo(root, b""), FlattenerError)
        d.addCallback(lambda exc: self.assertIsInstance(exc._exception, exn))
        return d


def assertIsFilesystemTemporary(case, fileObj):
    """
    Assert that C{fileObj} is a temporary file on the filesystem.

    @param case: A C{TestCase} instance to use to make the assertion.

    @raise: C{case.failureException} if C{fileObj} is not a temporary file on
        the filesystem.
    """
    # The tempfile API used to create content returns an instance of a
    # different type depending on what platform we're running on.  The point
    # here is to verify that the request body is in a file that's on the
    # filesystem.  Having a fileno method that returns an int is a somewhat
    # close approximation of this. -exarkun
    case.assertIsInstance(fileObj.fileno(), int)


__all__ = ["_render", "FlattenTestCase", "assertIsFilesystemTemporary"]
