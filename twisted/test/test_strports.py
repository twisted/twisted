# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.application.strports}.
"""

from twisted.trial.unittest import TestCase
from twisted.application import strports
from twisted.application import internet
from twisted.internet.protocol import Factory
from twisted.internet.endpoints import TCP4ServerEndpoint
from twisted.internet.test.test_endpoints import addFakePlugin



class ServiceTestCase(TestCase):
    """
    Tests for L{strports.service}.
    """

    def test_service(self):
        """
        L{strports.service} returns a L{StreamServerEndpointService}
        constructed with an endpoint produced from
        L{endpoint.serverFromString}, using the same syntax.
        """
        reactor = object() # the cake is a lie
        aFactory = Factory()
        aGoodPort = 1337
        svc = strports.service(
            'tcp:'+str(aGoodPort), aFactory, reactor=reactor)
        self.assertIsInstance(svc, internet.StreamServerEndpointService)

        # See twisted.application.test.test_internet.TestEndpointService.
        # test_synchronousRaiseRaisesSynchronously
        self.assertEqual(svc._raiseSynchronously, True)
        self.assertIsInstance(svc.endpoint, TCP4ServerEndpoint)
        # Maybe we should implement equality for endpoints.
        self.assertEqual(svc.endpoint._port, aGoodPort)
        self.assertIdentical(svc.factory, aFactory)
        self.assertIdentical(svc.endpoint._reactor, reactor)


    def test_serviceDefaultReactor(self):
        """
        L{strports.service} will use the default reactor when none is provided
        as an argument.
        """
        from twisted.internet import reactor as globalReactor
        aService = strports.service("tcp:80", None)
        self.assertIdentical(aService.endpoint._reactor, globalReactor)



class ListenTestCase(TestCase):
    """
    Tests for L{strports.listen}.
    """

    def setUp(self):
        addFakePlugin(self)


    def test_listen(self):
        """
        L{strports.listen} returns an L{IListeningPort} provider which wraps
        the service produced from L{service}, using the same syntax as
        L{endpoint.serverFromString}.
        """
        reactor = object()
        aFactory = Factory()
        port = strports.listen(
            'fake:spam:eggs=spam', aFactory, reactor=reactor)
        endpoint = port.service.endpoint
        self.assertEqual(endpoint.args, (reactor, 'spam'))
        self.assertEqual(endpoint.kwargs, {'eggs': 'spam'})
        self.assertEqual(endpoint.listener.args, (aFactory,))
        self.assertEqual(endpoint.listener.kwargs, {})
        self.assertIdentical(endpoint.args[0], reactor)
        self.assertIdentical(endpoint.listener.args[0], aFactory)
        self.assertIdentical(port.service.factory, aFactory)


    def test_listenDefaultReactor(self):
        """
        L{strports.listen} will use the default reactor when none is provided
        as an argument.
        """
        from twisted.internet import reactor as globalReactor
        aFactory = Factory()
        port = strports.listen("fake:spam", aFactory)
        self.assertIdentical(port.service.endpoint.args[0], globalReactor)


    def test_getHost(self):
        """
        The port provided by L{strports.listen} will give the same host as the
        underlying endpoint's port.
        """
        aFactory = Factory()
        port = strports.listen("fake:spam", aFactory)
        self.assertIdentical(port.getHost(),
                             port.service.endpoint.listener.getHost())


    def test_defaultGetHost(self):
        """
        If the port provided by L{strports.listen} has stopped listening, its
        getHost will give a L{_NullAddress}.
        """
        aFactory = Factory()
        port = strports.listen("fake:spam", aFactory)
        port.stopListening()
        self.assertIsInstance(port.getHost(), strports._NullAddress)
