# Copyright (c) 2008 Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.web.tap}.
"""

from twisted.python.usage import UsageError
from twisted.internet import reactor
from twisted.python.threadpool import ThreadPool
from twisted.trial.unittest import TestCase

from twisted.web.server import Site
from twisted.web.static import Data
from twisted.web.distrib import ResourcePublisher
from twisted.web.wsgi import WSGIResource
from twisted.web.tap import Options, makePersonalServerFactory

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
