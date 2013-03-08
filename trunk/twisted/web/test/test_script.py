# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.web.script}.
"""

import os

from twisted.trial.unittest import TestCase
from twisted.web.http import NOT_FOUND
from twisted.web.script import ResourceScriptDirectory, PythonScript
from twisted.web.test._util import _render
from twisted.web.test.test_web import DummyRequest


class ResourceScriptDirectoryTests(TestCase):
    """
    Tests for L{ResourceScriptDirectory}.
    """
    def test_render(self):
        """
        L{ResourceScriptDirectory.render} sets the HTTP response code to I{NOT
        FOUND}.
        """
        resource = ResourceScriptDirectory(self.mktemp())
        request = DummyRequest([''])
        d = _render(resource, request)
        def cbRendered(ignored):
            self.assertEqual(request.responseCode, NOT_FOUND)
        d.addCallback(cbRendered)
        return d


    def test_notFoundChild(self):
        """
        L{ResourceScriptDirectory.getChild} returns a resource which renders an
        response with the HTTP I{NOT FOUND} status code if the indicated child
        does not exist as an entry in the directory used to initialized the
        L{ResourceScriptDirectory}.
        """
        path = self.mktemp()
        os.makedirs(path)
        resource = ResourceScriptDirectory(path)
        request = DummyRequest(['foo'])
        child = resource.getChild("foo", request)
        d = _render(child, request)
        def cbRendered(ignored):
            self.assertEqual(request.responseCode, NOT_FOUND)
        d.addCallback(cbRendered)
        return d



class PythonScriptTests(TestCase):
    """
    Tests for L{PythonScript}.
    """
    def test_notFoundRender(self):
        """
        If the source file a L{PythonScript} is initialized with doesn't exist,
        L{PythonScript.render} sets the HTTP response code to I{NOT FOUND}.
        """
        resource = PythonScript(self.mktemp(), None)
        request = DummyRequest([''])
        d = _render(resource, request)
        def cbRendered(ignored):
            self.assertEqual(request.responseCode, NOT_FOUND)
        d.addCallback(cbRendered)
        return d
