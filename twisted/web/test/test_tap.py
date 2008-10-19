# Copyright (c) 2008 Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.web.tap}.
"""

import os, stat

from twisted.python.usage import UsageError
from twisted.internet.interfaces import IReactorUNIX
from twisted.internet import reactor
from twisted.python.threadpool import ThreadPool
from twisted.trial.unittest import TestCase
from twisted.application import strports

from twisted.web.server import Site
from twisted.web.static import Data
from twisted.web.distrib import ResourcePublisher, UserDirectory
from twisted.web.wsgi import WSGIResource
from twisted.web.tap import Options, makePersonalServerFactory, makeService

from twisted.spread.pb import PBServerFactory

application = object()

class ServiceTests(TestCase):
    """
    Tests for the service creation APIs in L{twisted.web.tap}.
    """
    def test_makePersonalServerFactory(self):
        """
        L{makePersonalServerFactory} returns a PB server factory which has
        as its root object a L{ResourcePublisher}.
        """
        # The fact that this pile of objects can actually be used somehow is
        # verified by twisted.web.test.test_distrib.
        site = Site(Data("foo bar", "text/plain"))
        serverFactory = makePersonalServerFactory(site)
        self.assertIsInstance(serverFactory, PBServerFactory)
        self.assertIsInstance(serverFactory.root, ResourcePublisher)
        self.assertIdentical(serverFactory.root.site, site)


    def test_personalServer(self):
        """
        The I{--personal} option to L{makeService} causes it to return a
        service which will listen on the server address given by the I{--port}
        option.
        """
        port = self.mktemp()
        options = Options()
        options.parseOptions(['--port', 'unix:' + port, '--personal'])
        service = makeService(options)
        service.startService()
        self.addCleanup(service.stopService)
        self.assertTrue(os.path.exists(port))
        self.assertTrue(stat.S_ISSOCK(os.stat(port).st_mode))

    if not IReactorUNIX.providedBy(reactor):
        test_personalServer.skip = (
            "The reactor does not support UNIX domain sockets")


    def test_defaultPersonalPath(self):
        """
        If the I{--port} option not specified but the I{--personal} option is,
        L{Options} defaults the port to C{UserDirectory.userSocketName} in the
        user's home directory.
        """
        options = Options()
        options.parseOptions(['--personal'])
        path = os.path.expanduser(
            os.path.join('~', UserDirectory.userSocketName))
        self.assertEqual(
            strports.parse(options['port'], None)[:2],
            ('UNIX', (path, None)))

    if not IReactorUNIX.providedBy(reactor):
        test_defaultPersonalPath.skip = (
            "The reactor does not support UNIX domain sockets")


    def test_defaultPort(self):
        """
        If the I{--port} option is not specified, L{Options} defaults the port
        to C{8080}.
        """
        options = Options()
        options.parseOptions([])
        self.assertEqual(
            strports.parse(options['port'], None)[:2],
            ('TCP', (8080, None)))


    def test_wsgi(self):
        """
        The I{--wsgi} option takes the fully-qualifed Python name of a WSGI
        application object and creates a L{WSGIResource} at the root which
        serves that application.
        """
        options = Options()
        options.parseOptions(['--wsgi', __name__ + '.application'])
        root = options['root']
        self.assertTrue(root, WSGIResource)
        self.assertIdentical(root._reactor, reactor)
        self.assertTrue(isinstance(root._threadpool, ThreadPool))
        self.assertIdentical(root._application, application)

        # The threadpool should start and stop with the reactor.
        self.assertFalse(root._threadpool.started)
        reactor.fireSystemEvent('startup')
        self.assertTrue(root._threadpool.started)
        self.assertFalse(root._threadpool.joined)
        reactor.fireSystemEvent('shutdown')
        self.assertTrue(root._threadpool.joined)


    def test_invalidApplication(self):
        """
        If I{--wsgi} is given an invalid name, L{Options.parseOptions}
        raises L{UsageError}.
        """
        options = Options()
        for name in [__name__ + '.nosuchthing', 'foo.']:
            exc = self.assertRaises(
                UsageError, options.parseOptions, ['--wsgi', name])
            self.assertEqual(str(exc), "No such WSGI application: %r" % (name,))
