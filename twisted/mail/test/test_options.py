# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.mail.tap}.
"""

from twisted.trial.unittest import TestCase

from twisted.python.usage import UsageError
from twisted.mail import protocols
from twisted.mail.tap import Options, makeService
from twisted.python.filepath import FilePath
from twisted.python.reflect import requireModule
from twisted.internet import endpoints, defer

if requireModule('OpenSSL') is None:
    sslSkip = 'Missing OpenSSL package.'
else:
    sslSkip = None


class OptionsTests(TestCase):
    """
    Tests for the command line option parser used for I{twistd mail}.
    """
    def setUp(self):
        self.aliasFilename = self.mktemp()
        aliasFile = file(self.aliasFilename, 'w')
        aliasFile.write('someuser:\tdifferentuser\n')
        aliasFile.close()


    def testAliasesWithoutDomain(self):
        """
        Test that adding an aliases(5) file before adding a domain raises a
        UsageError.
        """
        self.assertRaises(
            UsageError,
            Options().parseOptions,
            ['--aliases', self.aliasFilename])


    def testAliases(self):
        """
        Test that adding an aliases(5) file to an IAliasableDomain at least
        doesn't raise an unhandled exception.
        """
        Options().parseOptions([
            '--maildirdbmdomain', 'example.com=example.com',
            '--aliases', self.aliasFilename])


    def test_barePort(self):
        """
        A bare port passed to I{--pop3} results in deprecation warning in
        addition to a TCP4ServerEndpoint.
        """
        options = Options()
        options.parseOptions(['--pop3', '8110'])
        self.assertEqual(len(options['pop3']), 1)
        self.assertIsInstance(
            options['pop3'][0], endpoints.TCP4ServerEndpoint)
        warnings = self.flushWarnings([options.opt_pop3])
        self.assertEqual(len(warnings), 1)
        self.assertEqual(warnings[0]['category'], DeprecationWarning)
        self.assertEqual(
            warnings[0]['message'],
            "Specifying plain ports and/or a certificate is deprecated since "
            "Twisted 11.0; use endpoint descriptions instead.")


    def _endpointTest(self, service):
        """
        Use L{Options} to parse a single service configuration parameter and
        verify that an endpoint of the correct type is added to the list for
        that service.
        """
        options = Options()
        options.parseOptions(['--' + service, 'tcp:1234'])
        self.assertEqual(len(options[service]), 1)
        self.assertIsInstance(
            options[service][0], endpoints.TCP4ServerEndpoint)


    def test_endpointSMTP(self):
        """
        When I{--smtp} is given a TCP endpoint description as an argument, a
        TCPServerEndpoint is added to the list of SMTP endpoints.
        """
        self._endpointTest('smtp')


    def test_endpointPOP3(self):
        """
        When I{--pop3} is given a TCP endpoint description as an argument, a
        TCPServerEndpoint is added to the list of POP3 endpoints.
        """
        self._endpointTest('pop3')


    def test_protoDefaults(self):
        """
        POP3 and SMTP each listen on a TCP4ServerEndpoint by default.
        """
        options = Options()
        options.parseOptions([])

        self.assertEqual(len(options['pop3']), 1)
        self.assertIsInstance(
            options['pop3'][0], endpoints.TCP4ServerEndpoint)

        self.assertEqual(len(options['smtp']), 1)
        self.assertIsInstance(
            options['smtp'][0], endpoints.TCP4ServerEndpoint)


    def test_protoDisable(self):
        """
        The I{--no-pop3} and I{--no-smtp} options disable POP3 and SMTP
        respectively.
        """
        options = Options()
        options.parseOptions(['--no-pop3'])
        self.assertEqual(options._getEndpoints(None, 'pop3'), [])
        self.assertNotEquals(options._getEndpoints(None, 'smtp'), [])

        options = Options()
        options.parseOptions(['--no-smtp'])
        self.assertNotEquals(options._getEndpoints(None, 'pop3'), [])
        self.assertEqual(options._getEndpoints(None, 'smtp'), [])


    def test_allProtosDisabledError(self):
        """
        If all protocols are disabled, L{UsageError} is raised.
        """
        options = Options()
        self.assertRaises(
            UsageError, options.parseOptions, (['--no-pop3', '--no-smtp']))


    def test_pop3sBackwardCompatibility(self):
        """
        The deprecated I{--pop3s} and I{--certificate} options set up a POP3 SSL
        server.
        """
        cert = FilePath(__file__).sibling("server.pem")
        options = Options()
        options.parseOptions(['--pop3s', '8995',
                              '--certificate', cert.path])
        self.assertEqual(len(options['pop3']), 2)
        self.assertIsInstance(
            options['pop3'][0], endpoints.SSL4ServerEndpoint)
        self.assertIsInstance(
            options['pop3'][1], endpoints.TCP4ServerEndpoint)

        warnings = self.flushWarnings([options.postOptions])
        self.assertEqual(len(warnings), 1)
        self.assertEqual(warnings[0]['category'], DeprecationWarning)
        self.assertEqual(
            warnings[0]['message'],
            "Specifying plain ports and/or a certificate is deprecated since "
            "Twisted 11.0; use endpoint descriptions instead.")
    if sslSkip is not None:
        test_pop3sBackwardCompatibility.skip = sslSkip


    def test_esmtpWithoutHostname(self):
        """
        If I{--esmtp} is given without I{--hostname}, L{Options.parseOptions}
        raises L{UsageError}.
        """
        options = Options()
        exc = self.assertRaises(UsageError, options.parseOptions, ['--esmtp'])
        self.assertEqual("--esmtp requires --hostname", str(exc))


    def test_auth(self):
        """
        Tests that the --auth option registers a checker.
        """
        options = Options()
        options.parseOptions(['--auth', 'memory:admin:admin:bob:password'])
        self.assertEqual(len(options['credCheckers']), 1)
        checker = options['credCheckers'][0]
        interfaces = checker.credentialInterfaces
        registered_checkers = options.service.smtpPortal.checkers
        for iface in interfaces:
            self.assertEqual(checker, registered_checkers[iface])



class SpyEndpoint(object):
    """
    SpyEndpoint remembers what factory it is told to listen with.
    """
    listeningWith = None
    def listen(self, factory):
        self.listeningWith = factory
        return defer.succeed(None)



class MakeServiceTests(TestCase):
    """
    Tests for L{twisted.mail.tap.makeService}
    """
    def _endpointServerTest(self, key, factoryClass):
        """
        Configure a service with two endpoints for the protocol associated with
        C{key} and verify that when the service is started a factory of type
        C{factoryClass} is used to listen on each of them.
        """
        cleartext = SpyEndpoint()
        secure = SpyEndpoint()
        config = Options()
        config[key] = [cleartext, secure]
        service = makeService(config)
        service.privilegedStartService()
        service.startService()
        self.addCleanup(service.stopService)
        self.assertIsInstance(cleartext.listeningWith, factoryClass)
        self.assertIsInstance(secure.listeningWith, factoryClass)


    def test_pop3(self):
        """
        If one or more endpoints is included in the configuration passed to
        L{makeService} for the C{"pop3"} key, a service for starting a POP3
        server is constructed for each of them and attached to the returned
        service.
        """
        self._endpointServerTest("pop3", protocols.POP3Factory)


    def test_smtp(self):
        """
        If one or more endpoints is included in the configuration passed to
        L{makeService} for the C{"smtp"} key, a service for starting an SMTP
        server is constructed for each of them and attached to the returned
        service.
        """
        self._endpointServerTest("smtp", protocols.SMTPFactory)
