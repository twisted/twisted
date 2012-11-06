# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.
"""
Test the C{I...Endpoint} implementations that wrap the L{IReactorTCP},
L{IReactorSSL}, and L{IReactorUNIX} interfaces found in
L{twisted.internet.endpoints}.
"""
from socket import AF_INET, AF_INET6
from errno import EPERM
from zope.interface.verify import verifyObject

from twisted.trial import unittest
from twisted.internet import error, interfaces
from twisted.internet import endpoints
from twisted.internet.address import IPv4Address, UNIXAddress
from twisted.test.proto_helpers import MemoryReactor
from twisted.python.systemd import ListenFDs
from twisted.plugin import getPlugins

from twisted import plugins
from twisted.python.modules import getModule
from twisted.python.filepath import FilePath
from twisted.protocols import basic
from twisted.internet import protocol, reactor, stdio
from twisted.internet.stdio import PipeAddress
from twisted.internet.test.test_endpointspy3 import (
    EndpointTestCaseMixin, ServerEndpointTestCaseMixin, skipSSL,
    pemPath)

casPath = getModule(__name__).filePath.sibling("fake_CAs")
escapedPEMPathName = endpoints.quoteStringArgument(pemPath.path)
escapedCAsPathName = endpoints.quoteStringArgument(casPath.path)

if not skipSSL:
    from OpenSSL.SSL import ContextType
    from twisted.internet.ssl import CertificateOptions, Certificate, \
        KeyPair, PrivateCertificate
    from twisted.internet.test.test_endpointspy3 import (testCertificate,
                                                         testPrivateCertificate)


class StdioFactory(protocol.Factory):
    protocol = basic.LineReceiver



class StandardIOEndpointsTestCase(unittest.TestCase):
    """
    Tests for Standard I/O Endpoints
    """
    def setUp(self):
        self.ep = endpoints.StandardIOEndpoint(reactor)


    def test_standardIOInstance(self):
        """
        The endpoint creates an L{endpoints.StandardIO} instance.
        """
        self.d = self.ep.listen(StdioFactory())
        def checkInstanceAndLoseConnection(stdioOb):
            self.assertIsInstance(stdioOb, stdio.StandardIO)
            stdioOb.loseConnection()
        self.d.addCallback(checkInstanceAndLoseConnection)
        return self.d


    def test_reactor(self):
        """
        The reactor passed to the endpoint is set as its _reactor attribute.
        """
        self.assertEqual(self.ep._reactor, reactor)


    def test_protocol(self):
        """
        The protocol used in the endpoint is a L{basic.LineReceiver} instance.
        """
        self.d = self.ep.listen(StdioFactory())
        def checkProtocol(stdioOb):
            from twisted.python.runtime import platform
            if platform.isWindows():
                self.assertIsInstance(stdioOb.proto, basic.LineReceiver)
            else:
                self.assertIsInstance(stdioOb.protocol, basic.LineReceiver)
            stdioOb.loseConnection()
        self.d.addCallback(checkProtocol)
        return self.d


    def test_address(self):
        """
        The address passed to the factory's buildProtocol in the endpoint
        should be a PipeAddress instance.
        """
        class TestAddrFactory(protocol.Factory):
            protocol = basic.LineReceiver
            _address = None
            def buildProtocol(self, addr):
                self._address = addr
                p = self.protocol()
                p.factory = self
                return p
            def getAddress(self):
                return self._address

        myFactory = TestAddrFactory()
        self.d = self.ep.listen(myFactory)
        def checkAddress(stdioOb):
            self.assertIsInstance(myFactory.getAddress(), PipeAddress)
            stdioOb.loseConnection()
        self.d.addCallback(checkAddress)
        return self.d



class UNIXEndpointsTestCase(EndpointTestCaseMixin,
                            unittest.TestCase):
    """
    Tests for UnixSocket Endpoints.
    """

    def retrieveConnectedFactory(self, reactor):
        """
        Override L{EndpointTestCaseMixin.retrieveConnectedFactory} to account
        for different index of 'factory' in C{connectUNIX} args.
        """
        return self.expectedClients(reactor)[0][1]

    def expectedServers(self, reactor):
        """
        @return: List of calls to L{IReactorUNIX.listenUNIX}
        """
        return reactor.unixServers


    def expectedClients(self, reactor):
        """
        @return: List of calls to L{IReactorUNIX.connectUNIX}
        """
        return reactor.unixClients


    def assertConnectArgs(self, receivedArgs, expectedArgs):
        """
        Compare path, timeout, checkPID in C{receivedArgs} to C{expectedArgs}.
        We ignore the factory because we don't only care what protocol comes
        out of the C{IStreamClientEndpoint.connect} call.

        @param receivedArgs: C{tuple} of (C{path}, C{timeout}, C{checkPID})
            that was passed to L{IReactorUNIX.connectUNIX}.
        @param expectedArgs: C{tuple} of (C{path}, C{timeout}, C{checkPID})
            that we expect to have been passed to L{IReactorUNIX.connectUNIX}.
        """

        (path, ignoredFactory, timeout, checkPID) = receivedArgs

        (expectedPath, _ignoredFactory, expectedTimeout,
         expectedCheckPID) = expectedArgs

        self.assertEqual(path, expectedPath)
        self.assertEqual(timeout, expectedTimeout)
        self.assertEqual(checkPID, expectedCheckPID)


    def connectArgs(self):
        """
        @return: C{dict} of keyword arguments to pass to connect.
        """
        return {'timeout': 10, 'checkPID': 1}


    def listenArgs(self):
        """
        @return: C{dict} of keyword arguments to pass to listen
        """
        return {'backlog': 100, 'mode': 0600, 'wantPID': 1}


    def createServerEndpoint(self, reactor, factory, **listenArgs):
        """
        Create an L{UNIXServerEndpoint} and return the tools to verify its
        behaviour.

        @param reactor: A fake L{IReactorUNIX} that L{UNIXServerEndpoint} can
            call L{IReactorUNIX.listenUNIX} on.
        @param factory: The thing that we expect to be passed to our
            L{IStreamServerEndpoint.listen} implementation.
        @param listenArgs: Optional dictionary of arguments to
            L{IReactorUNIX.listenUNIX}.
        """
        address = UNIXAddress(self.mktemp())

        return (endpoints.UNIXServerEndpoint(reactor, address.name,
                                             **listenArgs),
                (address.name, factory,
                 listenArgs.get('backlog', 50),
                 listenArgs.get('mode', 0666),
                 listenArgs.get('wantPID', 0)),
                address)


    def createClientEndpoint(self, reactor, clientFactory, **connectArgs):
        """
        Create an L{UNIXClientEndpoint} and return the values needed to verify
        its behaviour.

        @param reactor: A fake L{IReactorUNIX} that L{UNIXClientEndpoint} can
            call L{IReactorUNIX.connectUNIX} on.
        @param clientFactory: The thing that we expect to be passed to our
            L{IStreamClientEndpoint.connect} implementation.
        @param connectArgs: Optional dictionary of arguments to
            L{IReactorUNIX.connectUNIX}
        """
        address = UNIXAddress(self.mktemp())

        return (endpoints.UNIXClientEndpoint(reactor, address.name,
                                             **connectArgs),
                (address.name, clientFactory,
                 connectArgs.get('timeout', 30),
                 connectArgs.get('checkPID', 0)),
                address)



class ParserTestCase(unittest.TestCase):
    """
    Tests for L{endpoints._parseServer}, the low-level parsing logic.
    """

    f = "Factory"

    def parse(self, *a, **kw):
        """
        Provide a hook for test_strports to substitute the deprecated API.
        """
        return endpoints._parseServer(*a, **kw)


    def test_simpleTCP(self):
        """
        Simple strings with a 'tcp:' prefix should be parsed as TCP.
        """
        self.assertEqual(self.parse('tcp:80', self.f),
                         ('TCP', (80, self.f), {'interface':'', 'backlog':50}))


    def test_interfaceTCP(self):
        """
        TCP port descriptions parse their 'interface' argument as a string.
        """
        self.assertEqual(
             self.parse('tcp:80:interface=127.0.0.1', self.f),
             ('TCP', (80, self.f), {'interface':'127.0.0.1', 'backlog':50}))


    def test_backlogTCP(self):
        """
        TCP port descriptions parse their 'backlog' argument as an integer.
        """
        self.assertEqual(self.parse('tcp:80:backlog=6', self.f),
                         ('TCP', (80, self.f),
                                 {'interface':'', 'backlog':6}))


    def test_simpleUNIX(self):
        """
        L{endpoints._parseServer} returns a C{'UNIX'} port description with
        defaults for C{'mode'}, C{'backlog'}, and C{'wantPID'} when passed a
        string with the C{'unix:'} prefix and no other parameter values.
        """
        self.assertEqual(
            self.parse('unix:/var/run/finger', self.f),
            ('UNIX', ('/var/run/finger', self.f),
             {'mode': 0666, 'backlog': 50, 'wantPID': True}))


    def test_modeUNIX(self):
        """
        C{mode} can be set by including C{"mode=<some integer>"}.
        """
        self.assertEqual(
            self.parse('unix:/var/run/finger:mode=0660', self.f),
            ('UNIX', ('/var/run/finger', self.f),
             {'mode': 0660, 'backlog': 50, 'wantPID': True}))


    def test_wantPIDUNIX(self):
        """
        C{wantPID} can be set to false by included C{"lockfile=0"}.
        """
        self.assertEqual(
            self.parse('unix:/var/run/finger:lockfile=0', self.f),
            ('UNIX', ('/var/run/finger', self.f),
             {'mode': 0666, 'backlog': 50, 'wantPID': False}))


    def test_escape(self):
        """
        Backslash can be used to escape colons and backslashes in port
        descriptions.
        """
        self.assertEqual(
            self.parse(r'unix:foo\:bar\=baz\:qux\\', self.f),
            ('UNIX', ('foo:bar=baz:qux\\', self.f),
             {'mode': 0666, 'backlog': 50, 'wantPID': True}))


    def test_quoteStringArgument(self):
        """
        L{endpoints.quoteStringArgument} should quote backslashes and colons
        for interpolation into L{endpoints.serverFromString} and
        L{endpoints.clientFactory} arguments.
        """
        self.assertEqual(endpoints.quoteStringArgument("some : stuff \\"),
                         "some \\: stuff \\\\")


    def test_impliedEscape(self):
        """
        In strports descriptions, '=' in a parameter value does not need to be
        quoted; it will simply be parsed as part of the value.
        """
        self.assertEqual(
            self.parse(r'unix:address=foo=bar', self.f),
            ('UNIX', ('foo=bar', self.f),
             {'mode': 0666, 'backlog': 50, 'wantPID': True}))


    def test_nonstandardDefault(self):
        """
        For compatibility with the old L{twisted.application.strports.parse},
        the third 'mode' argument may be specified to L{endpoints.parse} to
        indicate a default other than TCP.
        """
        self.assertEqual(
            self.parse('filename', self.f, 'unix'),
            ('UNIX', ('filename', self.f),
             {'mode': 0666, 'backlog': 50, 'wantPID': True}))


    def test_unknownType(self):
        """
        L{strports.parse} raises C{ValueError} when given an unknown endpoint
        type.
        """
        self.assertRaises(ValueError, self.parse, "bogus-type:nothing", self.f)



class ServerStringTests(unittest.TestCase):
    """
    Tests for L{twisted.internet.endpoints.serverFromString}.
    """

    def test_tcp(self):
        """
        When passed a TCP strports description, L{endpoints.serverFromString}
        returns a L{TCP4ServerEndpoint} instance initialized with the values
        from the string.
        """
        reactor = object()
        server = endpoints.serverFromString(
            reactor, "tcp:1234:backlog=12:interface=10.0.0.1")
        self.assertIsInstance(server, endpoints.TCP4ServerEndpoint)
        self.assertIdentical(server._reactor, reactor)
        self.assertEqual(server._port, 1234)
        self.assertEqual(server._backlog, 12)
        self.assertEqual(server._interface, "10.0.0.1")


    def test_ssl(self):
        """
        When passed an SSL strports description, L{endpoints.serverFromString}
        returns a L{SSL4ServerEndpoint} instance initialized with the values
        from the string.
        """
        reactor = object()
        server = endpoints.serverFromString(
            reactor,
            "ssl:1234:backlog=12:privateKey=%s:"
            "certKey=%s:interface=10.0.0.1" % (escapedPEMPathName,
                                               escapedPEMPathName))
        self.assertIsInstance(server, endpoints.SSL4ServerEndpoint)
        self.assertIdentical(server._reactor, reactor)
        self.assertEqual(server._port, 1234)
        self.assertEqual(server._backlog, 12)
        self.assertEqual(server._interface, "10.0.0.1")
        ctx = server._sslContextFactory.getContext()
        self.assertIsInstance(ctx, ContextType)

    if skipSSL:
        test_ssl.skip = skipSSL


    def test_unix(self):
        """
        When passed a UNIX strports description, L{endpoint.serverFromString}
        returns a L{UNIXServerEndpoint} instance initialized with the values
        from the string.
        """
        reactor = object()
        endpoint = endpoints.serverFromString(
            reactor,
            "unix:/var/foo/bar:backlog=7:mode=0123:lockfile=1")
        self.assertIsInstance(endpoint, endpoints.UNIXServerEndpoint)
        self.assertIdentical(endpoint._reactor, reactor)
        self.assertEqual(endpoint._address, "/var/foo/bar")
        self.assertEqual(endpoint._backlog, 7)
        self.assertEqual(endpoint._mode, 0123)
        self.assertEqual(endpoint._wantPID, True)


    def test_implicitDefaultNotAllowed(self):
        """
        The older service-based API (L{twisted.internet.strports.service})
        allowed an implicit default of 'tcp' so that TCP ports could be
        specified as a simple integer, but we've since decided that's a bad
        idea, and the new API does not accept an implicit default argument; you
        have to say 'tcp:' now.  If you try passing an old implicit port number
        to the new API, you'll get a C{ValueError}.
        """
        value = self.assertRaises(
            ValueError, endpoints.serverFromString, None, "4321")
        self.assertEqual(
            str(value),
            "Unqualified strport description passed to 'service'."
            "Use qualified endpoint descriptions; for example, 'tcp:4321'.")


    def test_unknownType(self):
        """
        L{endpoints.serverFromString} raises C{ValueError} when given an
        unknown endpoint type.
        """
        value = self.assertRaises(
            # faster-than-light communication not supported
            ValueError, endpoints.serverFromString, None,
            "ftl:andromeda/carcosa/hali/2387")
        self.assertEqual(
            str(value),
            "Unknown endpoint type: 'ftl'")


    def test_typeFromPlugin(self):
        """
        L{endpoints.serverFromString} looks up plugins of type
        L{IStreamServerEndpoint} and constructs endpoints from them.
        """
        # Set up a plugin which will only be accessible for the duration of
        # this test.
        addFakePlugin(self)
        # Plugin is set up: now actually test.
        notAReactor = object()
        fakeEndpoint = endpoints.serverFromString(
            notAReactor, "fake:hello:world:yes=no:up=down")
        from twisted.plugins.fakeendpoint import fake
        self.assertIdentical(fakeEndpoint.parser, fake)
        self.assertEqual(fakeEndpoint.args, (notAReactor, 'hello', 'world'))
        self.assertEqual(fakeEndpoint.kwargs, dict(yes='no', up='down'))



def addFakePlugin(testCase, dropinSource="fakeendpoint.py"):
    """
    For the duration of C{testCase}, add a fake plugin to twisted.plugins which
    contains some sample endpoint parsers.
    """
    import sys
    savedModules = sys.modules.copy()
    savedPluginPath = plugins.__path__
    def cleanup():
        sys.modules.clear()
        sys.modules.update(savedModules)
        plugins.__path__[:] = savedPluginPath
    testCase.addCleanup(cleanup)
    fp = FilePath(testCase.mktemp())
    fp.createDirectory()
    getModule(__name__).filePath.sibling(dropinSource).copyTo(
        fp.child(dropinSource))
    plugins.__path__.append(fp.path)



class ClientStringTests(unittest.TestCase):
    """
    Tests for L{twisted.internet.endpoints.clientFromString}.
    """

    def test_tcp(self):
        """
        When passed a TCP strports description, L{endpoints.clientFromString}
        returns a L{TCP4ClientEndpoint} instance initialized with the values
        from the string.
        """
        reactor = object()
        client = endpoints.clientFromString(
            reactor,
            "tcp:host=example.com:port=1234:timeout=7:bindAddress=10.0.0.2")
        self.assertIsInstance(client, endpoints.TCP4ClientEndpoint)
        self.assertIdentical(client._reactor, reactor)
        self.assertEqual(client._host, "example.com")
        self.assertEqual(client._port, 1234)
        self.assertEqual(client._timeout, 7)
        self.assertEqual(client._bindAddress, "10.0.0.2")


    def test_tcpPositionalArgs(self):
        """
        When passed a TCP strports description using positional arguments,
        L{endpoints.clientFromString} returns a L{TCP4ClientEndpoint} instance
        initialized with the values from the string.
        """
        reactor = object()
        client = endpoints.clientFromString(
            reactor,
            "tcp:example.com:1234:timeout=7:bindAddress=10.0.0.2")
        self.assertIsInstance(client, endpoints.TCP4ClientEndpoint)
        self.assertIdentical(client._reactor, reactor)
        self.assertEqual(client._host, "example.com")
        self.assertEqual(client._port, 1234)
        self.assertEqual(client._timeout, 7)
        self.assertEqual(client._bindAddress, "10.0.0.2")


    def test_tcpHostPositionalArg(self):
        """
        When passed a TCP strports description specifying host as a positional
        argument, L{endpoints.clientFromString} returns a L{TCP4ClientEndpoint}
        instance initialized with the values from the string.
        """
        reactor = object()

        client = endpoints.clientFromString(
            reactor,
            "tcp:example.com:port=1234:timeout=7:bindAddress=10.0.0.2")
        self.assertEqual(client._host, "example.com")
        self.assertEqual(client._port, 1234)


    def test_tcpPortPositionalArg(self):
        """
        When passed a TCP strports description specifying port as a positional
        argument, L{endpoints.clientFromString} returns a L{TCP4ClientEndpoint}
        instance initialized with the values from the string.
        """
        reactor = object()
        client = endpoints.clientFromString(
            reactor,
            "tcp:host=example.com:1234:timeout=7:bindAddress=10.0.0.2")
        self.assertEqual(client._host, "example.com")
        self.assertEqual(client._port, 1234)


    def test_tcpDefaults(self):
        """
        A TCP strports description may omit I{timeout} or I{bindAddress} to
        allow the default to be used.
        """
        reactor = object()
        client = endpoints.clientFromString(
            reactor,
            "tcp:host=example.com:port=1234")
        self.assertEqual(client._timeout, 30)
        self.assertEqual(client._bindAddress, None)


    def test_unix(self):
        """
        When passed a UNIX strports description, L{endpoints.clientFromString}
        returns a L{UNIXClientEndpoint} instance initialized with the values
        from the string.
        """
        reactor = object()
        client = endpoints.clientFromString(
            reactor,
            "unix:path=/var/foo/bar:lockfile=1:timeout=9")
        self.assertIsInstance(client, endpoints.UNIXClientEndpoint)
        self.assertIdentical(client._reactor, reactor)
        self.assertEqual(client._path, "/var/foo/bar")
        self.assertEqual(client._timeout, 9)
        self.assertEqual(client._checkPID, True)


    def test_unixDefaults(self):
        """
        A UNIX strports description may omit I{lockfile} or I{timeout} to allow
        the defaults to be used.
        """
        client = endpoints.clientFromString(object(), "unix:path=/var/foo/bar")
        self.assertEqual(client._timeout, 30)
        self.assertEqual(client._checkPID, False)


    def test_unixPathPositionalArg(self):
        """
        When passed a UNIX strports description specifying path as a positional
        argument, L{endpoints.clientFromString} returns a L{UNIXClientEndpoint}
        instance initialized with the values from the string.
        """
        reactor = object()
        client = endpoints.clientFromString(
            reactor,
            "unix:/var/foo/bar:lockfile=1:timeout=9")
        self.assertIsInstance(client, endpoints.UNIXClientEndpoint)
        self.assertIdentical(client._reactor, reactor)
        self.assertEqual(client._path, "/var/foo/bar")
        self.assertEqual(client._timeout, 9)
        self.assertEqual(client._checkPID, True)


    def test_typeFromPlugin(self):
        """
        L{endpoints.clientFromString} looks up plugins of type
        L{IStreamClientEndpoint} and constructs endpoints from them.
        """
        addFakePlugin(self)
        notAReactor = object()
        clientEndpoint = endpoints.clientFromString(
            notAReactor, "cfake:alpha:beta:cee=dee:num=1")
        from twisted.plugins.fakeendpoint import fakeClient
        self.assertIdentical(clientEndpoint.parser, fakeClient)
        self.assertEqual(clientEndpoint.args, ('alpha', 'beta'))
        self.assertEqual(clientEndpoint.kwargs, dict(cee='dee', num='1'))


    def test_unknownType(self):
        """
        L{endpoints.serverFromString} raises C{ValueError} when given an
        unknown endpoint type.
        """
        value = self.assertRaises(
            # faster-than-light communication not supported
            ValueError, endpoints.clientFromString, None,
            "ftl:andromeda/carcosa/hali/2387")
        self.assertEqual(
            str(value),
            "Unknown endpoint type: 'ftl'")



class SSLClientStringTests(unittest.TestCase):
    """
    Tests for L{twisted.internet.endpoints.clientFromString} which require SSL.
    """

    if skipSSL:
        skip = skipSSL

    def test_ssl(self):
        """
        When passed an SSL strports description, L{clientFromString} returns a
        L{SSL4ClientEndpoint} instance initialized with the values from the
        string.
        """
        reactor = object()
        client = endpoints.clientFromString(
            reactor,
            "ssl:host=example.net:port=4321:privateKey=%s:"
            "certKey=%s:bindAddress=10.0.0.3:timeout=3:caCertsDir=%s" %
             (escapedPEMPathName,
              escapedPEMPathName,
              escapedCAsPathName))
        self.assertIsInstance(client, endpoints.SSL4ClientEndpoint)
        self.assertIdentical(client._reactor, reactor)
        self.assertEqual(client._host, "example.net")
        self.assertEqual(client._port, 4321)
        self.assertEqual(client._timeout, 3)
        self.assertEqual(client._bindAddress, "10.0.0.3")
        certOptions = client._sslContextFactory
        self.assertIsInstance(certOptions, CertificateOptions)
        ctx = certOptions.getContext()
        self.assertIsInstance(ctx, ContextType)
        self.assertEqual(Certificate(certOptions.certificate),
                          testCertificate)
        privateCert = PrivateCertificate(certOptions.certificate)
        privateCert._setPrivateKey(KeyPair(certOptions.privateKey))
        self.assertEqual(privateCert, testPrivateCertificate)
        expectedCerts = [
            Certificate.loadPEM(x.getContent()) for x in
                [casPath.child("thing1.pem"), casPath.child("thing2.pem")]
            if x.basename().lower().endswith('.pem')
        ]
        self.assertEqual(sorted((Certificate(x) for x in certOptions.caCerts),
                                key=lambda cert: cert.digest()),
                         sorted(expectedCerts,
                                key=lambda cert: cert.digest()))


    def test_sslPositionalArgs(self):
        """
        When passed an SSL strports description, L{clientFromString} returns a
        L{SSL4ClientEndpoint} instance initialized with the values from the
        string.
        """
        reactor = object()
        client = endpoints.clientFromString(
            reactor,
            "ssl:example.net:4321:privateKey=%s:"
            "certKey=%s:bindAddress=10.0.0.3:timeout=3:caCertsDir=%s" %
             (escapedPEMPathName,
              escapedPEMPathName,
              escapedCAsPathName))
        self.assertIsInstance(client, endpoints.SSL4ClientEndpoint)
        self.assertIdentical(client._reactor, reactor)
        self.assertEqual(client._host, "example.net")
        self.assertEqual(client._port, 4321)
        self.assertEqual(client._timeout, 3)
        self.assertEqual(client._bindAddress, "10.0.0.3")


    def test_unreadableCertificate(self):
        """
        If a certificate in the directory is unreadable,
        L{endpoints._loadCAsFromDir} will ignore that certificate.
        """
        class UnreadableFilePath(FilePath):
            def getContent(self):
                data = FilePath.getContent(self)
                # There is a duplicate of thing2.pem, so ignore anything that
                # looks like it.
                if data == casPath.child("thing2.pem").getContent():
                    raise IOError(EPERM)
                else:
                    return data
        casPathClone = casPath.child("ignored").parent()
        casPathClone.clonePath = UnreadableFilePath
        self.assertEqual(
            [Certificate(x) for x in endpoints._loadCAsFromDir(casPathClone)],
            [Certificate.loadPEM(casPath.child("thing1.pem").getContent())])


    def test_sslSimple(self):
        """
        When passed an SSL strports description without any extra parameters,
        L{clientFromString} returns a simple non-verifying endpoint that will
        speak SSL.
        """
        reactor = object()
        client = endpoints.clientFromString(
            reactor, "ssl:host=simple.example.org:port=4321")
        certOptions = client._sslContextFactory
        self.assertIsInstance(certOptions, CertificateOptions)
        self.assertEqual(certOptions.verify, False)
        ctx = certOptions.getContext()
        self.assertIsInstance(ctx, ContextType)



class AdoptedStreamServerEndpointTestCase(ServerEndpointTestCaseMixin,
                                          unittest.TestCase):
    """
    Tests for adopted socket-based stream server endpoints.
    """
    def _createStubbedAdoptedEndpoint(self, reactor, fileno, addressFamily):
        """
        Create an L{AdoptedStreamServerEndpoint} which may safely be used with
        an invalid file descriptor.  This is convenient for a number of unit
        tests.
        """
        e = endpoints.AdoptedStreamServerEndpoint(reactor, fileno, addressFamily)
        # Stub out some syscalls which would fail, given our invalid file
        # descriptor.
        e._close = lambda fd: None
        e._setNonBlocking = lambda fd: None
        return e


    def createServerEndpoint(self, reactor, factory):
        """
        Create a new L{AdoptedStreamServerEndpoint} for use by a test.

        @return: A three-tuple:
            - The endpoint
            - A tuple of the arguments expected to be passed to the underlying
              reactor method
            - An IAddress object which will match the result of
              L{IListeningPort.getHost} on the port returned by the endpoint.
        """
        fileno = 12
        addressFamily = AF_INET
        endpoint = self._createStubbedAdoptedEndpoint(
            reactor, fileno, addressFamily)
        # Magic numbers come from the implementation of MemoryReactor
        address = IPv4Address("TCP", "0.0.0.0", 1234)
        return (endpoint, (fileno, addressFamily, factory), address)


    def expectedServers(self, reactor):
        """
        @return: The ports which were actually adopted by C{reactor} via calls
            to its L{IReactorSocket.adoptStreamPort} implementation.
        """
        return reactor.adoptedPorts


    def listenArgs(self):
        """
        @return: A C{dict} of additional keyword arguments to pass to the
            C{createServerEndpoint}.
        """
        return {}


    def test_singleUse(self):
        """
        L{AdoptedStreamServerEndpoint.listen} can only be used once.  The file
        descriptor given is closed after the first use, and subsequent calls to
        C{listen} return a L{Deferred} that fails with L{AlreadyListened}.
        """
        reactor = MemoryReactor()
        endpoint = self._createStubbedAdoptedEndpoint(reactor, 13, AF_INET)
        endpoint.listen(object())
        d = self.assertFailure(endpoint.listen(object()), error.AlreadyListened)
        def listenFailed(ignored):
            self.assertEqual(1, len(reactor.adoptedPorts))
        d.addCallback(listenFailed)
        return d


    def test_descriptionNonBlocking(self):
        """
        L{AdoptedStreamServerEndpoint.listen} sets the file description given to
        it to non-blocking.
        """
        reactor = MemoryReactor()
        endpoint = self._createStubbedAdoptedEndpoint(reactor, 13, AF_INET)
        events = []
        def setNonBlocking(fileno):
            events.append(("setNonBlocking", fileno))
        endpoint._setNonBlocking = setNonBlocking

        d = endpoint.listen(object())
        def listened(ignored):
            self.assertEqual([("setNonBlocking", 13)], events)
        d.addCallback(listened)
        return d


    def test_descriptorClosed(self):
        """
        L{AdoptedStreamServerEndpoint.listen} closes its file descriptor after
        adding it to the reactor with L{IReactorSocket.adoptStreamPort}.
        """
        reactor = MemoryReactor()
        endpoint = self._createStubbedAdoptedEndpoint(reactor, 13, AF_INET)
        events = []
        def close(fileno):
            events.append(("close", fileno, len(reactor.adoptedPorts)))
        endpoint._close = close

        d = endpoint.listen(object())
        def listened(ignored):
            self.assertEqual([("close", 13, 1)], events)
        d.addCallback(listened)
        return d



class SystemdEndpointPluginTests(unittest.TestCase):
    """
    Unit tests for the systemd stream server endpoint and endpoint string
    description parser.

    @see: U{systemd<http://www.freedesktop.org/wiki/Software/systemd>}
    """

    _parserClass = endpoints._SystemdParser

    def test_pluginDiscovery(self):
        """
        L{endpoints._SystemdParser} is found as a plugin for
        L{interfaces.IStreamServerEndpointStringParser} interface.
        """
        parsers = list(getPlugins(
                interfaces.IStreamServerEndpointStringParser))
        for p in parsers:
            if isinstance(p, self._parserClass):
                break
        else:
            self.fail("Did not find systemd parser in %r" % (parsers,))


    def test_interface(self):
        """
        L{endpoints._SystemdParser} instances provide
        L{interfaces.IStreamServerEndpointStringParser}.
        """
        parser = self._parserClass()
        self.assertTrue(verifyObject(
                interfaces.IStreamServerEndpointStringParser, parser))


    def _parseStreamServerTest(self, addressFamily, addressFamilyString):
        """
        Helper for unit tests for L{endpoints._SystemdParser.parseStreamServer}
        for different address families.

        Handling of the address family given will be verify.  If there is a
        problem a test-failing exception will be raised.

        @param addressFamily: An address family constant, like L{socket.AF_INET}.

        @param addressFamilyString: A string which should be recognized by the
            parser as representing C{addressFamily}.
        """
        reactor = object()
        descriptors = [5, 6, 7, 8, 9]
        index = 3

        parser = self._parserClass()
        parser._sddaemon = ListenFDs(descriptors)

        server = parser.parseStreamServer(
            reactor, domain=addressFamilyString, index=str(index))
        self.assertIdentical(server.reactor, reactor)
        self.assertEqual(server.addressFamily, addressFamily)
        self.assertEqual(server.fileno, descriptors[index])


    def test_parseStreamServerINET(self):
        """
        IPv4 can be specified using the string C{"INET"}.
        """
        self._parseStreamServerTest(AF_INET, "INET")


    def test_parseStreamServerINET6(self):
        """
        IPv6 can be specified using the string C{"INET6"}.
        """
        self._parseStreamServerTest(AF_INET6, "INET6")


    def test_parseStreamServerUNIX(self):
        """
        A UNIX domain socket can be specified using the string C{"UNIX"}.
        """
        try:
            from socket import AF_UNIX
        except ImportError:
            raise unittest.SkipTest("Platform lacks AF_UNIX support")
        else:
            self._parseStreamServerTest(AF_UNIX, "UNIX")



class TCP6ServerEndpointPluginTests(unittest.TestCase):
    """
    Unit tests for the TCP IPv6 stream server endpoint string description parser.
    """
    _parserClass = endpoints._TCP6ServerParser

    def test_pluginDiscovery(self):
        """
        L{endpoints._TCP6ServerParser} is found as a plugin for
        L{interfaces.IStreamServerEndpointStringParser} interface.
        """
        parsers = list(getPlugins(
                interfaces.IStreamServerEndpointStringParser))
        for p in parsers:
            if isinstance(p, self._parserClass):
                break
        else:
            self.fail("Did not find TCP6ServerEndpoint parser in %r" % (parsers,))


    def test_interface(self):
        """
        L{endpoints._TCP6ServerParser} instances provide
        L{interfaces.IStreamServerEndpointStringParser}.
        """
        parser = self._parserClass()
        self.assertTrue(verifyObject(
                interfaces.IStreamServerEndpointStringParser, parser))


    def test_stringDescription(self):
        """
        L{serverFromString} returns a L{TCP6ServerEndpoint} instance with a 'tcp6'
        endpoint string description.
        """
        ep = endpoints.serverFromString(MemoryReactor(),
            "tcp6:8080:backlog=12:interface=\:\:1")
        self.assertIsInstance(ep, endpoints.TCP6ServerEndpoint)
        self.assertIsInstance(ep._reactor, MemoryReactor)
        self.assertEqual(ep._port, 8080)
        self.assertEqual(ep._backlog, 12)
        self.assertEqual(ep._interface, '::1')



class StandardIOEndpointPluginTests(unittest.TestCase):
    """
    Unit tests for the Standard I/O endpoint string description parser.
    """
    _parserClass = endpoints._StandardIOParser

    def test_pluginDiscovery(self):
        """
        L{endpoints._StandardIOParser} is found as a plugin for
        L{interfaces.IStreamServerEndpointStringParser} interface.
        """
        parsers = list(getPlugins(
                interfaces.IStreamServerEndpointStringParser))
        for p in parsers:
            if isinstance(p, self._parserClass):
                break
        else:
            self.fail("Did not find StandardIOEndpoint parser in %r" % (parsers,))


    def test_interface(self):
        """
        L{endpoints._StandardIOParser} instances provide
        L{interfaces.IStreamServerEndpointStringParser}.
        """
        parser = self._parserClass()
        self.assertTrue(verifyObject(
                interfaces.IStreamServerEndpointStringParser, parser))


    def test_stringDescription(self):
        """
        L{serverFromString} returns a L{StandardIOEndpoint} instance with a 'stdio'
        endpoint string description.
        """
        ep = endpoints.serverFromString(MemoryReactor(), "stdio:")
        self.assertIsInstance(ep, endpoints.StandardIOEndpoint)
        self.assertIsInstance(ep._reactor, MemoryReactor)
