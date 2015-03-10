# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.web.vhost}.
"""

from twisted.internet.defer import gatherResults
from twisted.trial.unittest import TestCase
from twisted.web.http import NOT_FOUND
from twisted.web.static import Data
from twisted.web.vhost import NameVirtualHost
from twisted.web.test.test_web import DummyRequest
from twisted.web.test._util import _render

class NameVirtualHostTests(TestCase):
    """
    Tests for L{NameVirtualHost}.
    """
    def test_renderWithoutHost(self):
        """
        L{NameVirtualHost.render} returns the result of rendering the
        instance's C{default} if it is not C{None} and there is no I{Host}
        header in the request.
        """
        virtualHostResource = NameVirtualHost()
        virtualHostResource.default = Data("correct result", "")
        request = DummyRequest([''])
        self.assertEqual(
            virtualHostResource.render(request), "correct result")


    def test_renderWithoutHostNoDefault(self):
        """
        L{NameVirtualHost.render} returns a response with a status of I{NOT
        FOUND} if the instance's C{default} is C{None} and there is no I{Host}
        header in the request.
        """
        virtualHostResource = NameVirtualHost()
        request = DummyRequest([''])
        d = _render(virtualHostResource, request)
        def cbRendered(ignored):
            self.assertEqual(request.responseCode, NOT_FOUND)
        d.addCallback(cbRendered)
        return d


    def test_renderWithHost(self):
        """
        L{NameVirtualHost.render} returns the result of rendering the resource
        which is the value in the instance's C{host} dictionary corresponding
        to the key indicated by the value of the I{Host} header in the request.
        """
        virtualHostResource = NameVirtualHost()
        virtualHostResource.addHost('example.org', Data("winner", ""))

        request = DummyRequest([''])
        request.headers['host'] = 'example.org'
        d = _render(virtualHostResource, request)
        def cbRendered(ignored, request):
            self.assertEqual(''.join(request.written), "winner")
        d.addCallback(cbRendered, request)

        # The port portion of the Host header should not be considered.
        requestWithPort = DummyRequest([''])
        requestWithPort.headers['host'] = 'example.org:8000'
        dWithPort = _render(virtualHostResource, requestWithPort)
        def cbRendered(ignored, requestWithPort):
            self.assertEqual(''.join(requestWithPort.written), "winner")
        dWithPort.addCallback(cbRendered, requestWithPort)

        return gatherResults([d, dWithPort])


    def test_renderWithUnknownHost(self):
        """
        L{NameVirtualHost.render} returns the result of rendering the
        instance's C{default} if it is not C{None} and there is no host
        matching the value of the I{Host} header in the request.
        """
        virtualHostResource = NameVirtualHost()
        virtualHostResource.default = Data("correct data", "")
        request = DummyRequest([''])
        request.headers['host'] = 'example.com'
        d = _render(virtualHostResource, request)
        def cbRendered(ignored):
            self.assertEqual(''.join(request.written), "correct data")
        d.addCallback(cbRendered)
        return d


    def test_renderWithUnknownHostNoDefault(self):
        """
        L{NameVirtualHost.render} returns a response with a status of I{NOT
        FOUND} if the instance's C{default} is C{None} and there is no host
        matching the value of the I{Host} header in the request.
        """
        virtualHostResource = NameVirtualHost()
        request = DummyRequest([''])
        request.headers['host'] = 'example.com'
        d = _render(virtualHostResource, request)
        def cbRendered(ignored):
            self.assertEqual(request.responseCode, NOT_FOUND)
        d.addCallback(cbRendered)
        return d
