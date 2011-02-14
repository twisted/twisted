# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.web.tap}.
"""

import os, stat

from twisted.python.usage import UsageError
from twisted.python.filepath import FilePath
from twisted.internet.interfaces import IReactorUNIX
from twisted.internet import reactor
from twisted.python.threadpool import ThreadPool
from twisted.trial.unittest import TestCase
from twisted.application import strports

from twisted.web.server import Site
from twisted.web.static import Data, File
from twisted.web.distrib import ResourcePublisher, UserDirectory
from twisted.web.wsgi import WSGIResource
from twisted.web.tap import Options, makePersonalServerFactory, makeService
from twisted.web.twcgi import CGIScript, PHP3Script, PHPScript
from twisted.web.script import PythonScript


from twisted.spread.pb import PBServerFactory

application = object()

class ServiceTests(TestCase):
    """
    Tests for the service creation APIs in L{twisted.web.tap}.
    """
    def _pathOption(self):
        """
        Helper for the I{--path} tests which creates a directory and creates
        an L{Options} object which uses that directory as its static
        filesystem root.

        @return: A two-tuple of a L{FilePath} referring to the directory and
            the value associated with the C{'root'} key in the L{Options}
            instance after parsing a I{--path} option.
        """
        path = FilePath(self.mktemp())
        path.makedirs()
        options = Options()
        options.parseOptions(['--path', path.path])
        root = options['root']
        return path, root


    def test_path(self):
        """
        The I{--path} option causes L{Options} to create a root resource
        which serves responses from the specified path.
        """
        path, root = self._pathOption()
        self.assertIsInstance(root, File)
        self.assertEqual(root.path, path.path)


    def test_cgiProcessor(self):
        """
        The I{--path} option creates a root resource which serves a
        L{CGIScript} instance for any child with the C{".cgi"} extension.
        """
        path, root = self._pathOption()
        path.child("foo.cgi").setContent("")
        self.assertIsInstance(root.getChild("foo.cgi", None), CGIScript)


    def test_php3Processor(self):
        """
        The I{--path} option creates a root resource which serves a
        L{PHP3Script} instance for any child with the C{".php3"} extension.
        """
        path, root = self._pathOption()
        path.child("foo.php3").setContent("")
        self.assertIsInstance(root.getChild("foo.php3", None), PHP3Script)


    def test_phpProcessor(self):
        """
        The I{--path} option creates a root resource which serves a
        L{PHPScript} instance for any child with the C{".php"} extension.
        """
        path, root = self._pathOption()
        path.child("foo.php").setContent("")
        self.assertIsInstance(root.getChild("foo.php", None), PHPScript)


    def test_epyProcessor(self):
        """
        The I{--path} option creates a root resource which serves a
        L{PythonScript} instance for any child with the C{".epy"} extension.
        """
        path, root = self._pathOption()
        path.child("foo.epy").setContent("")
        self.assertIsInstance(root.getChild("foo.epy", None), PythonScript)


    def test_rpyProcessor(self):
        """
        The I{--path} option creates a root resource which serves the
        C{resource} global defined by the Python source in any child with
        the C{".rpy"} extension.
        """
        path, root = self._pathOption()
        path.child("foo.rpy").setContent(
            "from twisted.web.static import Data\n"
            "resource = Data('content', 'major/minor')\n")
        child = root.getChild("foo.rpy", None)
        self.assertIsInstance(child, Data)
        self.assertEqual(child.data, 'content')
        self.assertEqual(child.type, 'major/minor')


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
