# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.mail.tap}.
"""

from twisted.internet import defer, endpoints
from twisted.mail import protocols
from twisted.mail.tap import Options, makeService
from twisted.python.usage import UsageError
from twisted.trial.unittest import TestCase


class OptionsTests(TestCase):
    """
    Tests for the command line option parser used for I{twistd mail}.
    """

    def setUp(self):
        self.aliasFilename = self.mktemp()
        with open(self.aliasFilename, "w") as aliasFile:
            aliasFile.write("someuser:\tdifferentuser\n")

    def testAliasesWithoutDomain(self):
        """
        Test that adding an aliases(5) file before adding a domain raises a
        UsageError.
        """
        self.assertRaises(
            UsageError, Options().parseOptions, ["--aliases", self.aliasFilename]
        )

    def testAliases(self):
        """
        Test that adding an aliases(5) file to an IAliasableDomain at least
        doesn't raise an unhandled exception.
        """
        Options().parseOptions(
            [
                "--maildirdbmdomain",
                "example.com=example.com",
                "--aliases",
                self.aliasFilename,
            ]
        )

    def test_endpointSMTP(self):
        """
        When I{--smtp} is given a TCP endpoint description as an argument, a
        TCPServerEndpoint is added to the list of SMTP endpoints.
        """
        options = Options()
        options.parseOptions(["--smtp", "tcp:1234", "--no-pop3"])
        service = makeService(options)
        service.privilegedStartService()
        service.startService()
        self.addCleanup(service.stopService)
        self.assertEqual(len(options["smtp"]), 1)
        self.assertIsInstance(service.services[1].factory, protocols.SMTPFactory)
        self.assertIsInstance(
            service.services[1].endpoint, endpoints.TCP4ServerEndpoint
        )
        self.assertEqual(service.services[1].endpoint._port, 1234)

    def test_endpointPOP3(self):
        """
        When I{--pop3} is given a TCP endpoint description as an argument, a
        TCPServerEndpoint is added to the list of POP3 endpoints.
        """
        options = Options()
        options.parseOptions(["--pop3", "tcp:1234", "--no-smtp"])
        service = makeService(options)
        service.privilegedStartService()
        service.startService()
        self.addCleanup(service.stopService)
        self.assertEqual(len(options["pop3"]), 1)
        self.assertIsInstance(service.services[1].factory, protocols.POP3Factory)
        self.assertIsInstance(
            service.services[1].endpoint, endpoints.TCP4ServerEndpoint
        )
        self.assertEqual(service.services[1].endpoint._port, 1234)

    def test_protoDefaults(self):
        """
        POP3 and SMTP each listen on a TCP4ServerEndpoint by default.
        """
        options = Options()
        options.parseOptions([])
        service = makeService(options)
        service.privilegedStartService()
        service.startService()
        self.addCleanup(service.stopService)

        self.assertEqual(len(options["pop3"]), 1)
        self.assertIsInstance(
            service.services[1].endpoint, endpoints.TCP4ServerEndpoint
        )

        self.assertEqual(len(options["smtp"]), 1)
        self.assertIsInstance(
            service.services[1].endpoint, endpoints.TCP4ServerEndpoint
        )

    def test_protoDisable(self):
        """
        The I{--no-pop3} and I{--no-smtp} options disable POP3 and SMTP
        respectively.
        """
        options = Options()
        options.parseOptions(["--no-pop3"])
        self.assertEqual(options["pop3"], [])
        self.assertNotEqual(options["smtp"], [])

        options = Options()
        options.parseOptions(["--no-smtp"])
        self.assertNotEqual(options["pop3"], [])
        self.assertEqual(options["smtp"], [])

    def test_allProtosDisabledError(self):
        """
        If all protocols are disabled, L{UsageError} is raised.
        """
        options = Options()
        self.assertRaises(
            UsageError, options.parseOptions, (["--no-pop3", "--no-smtp"])
        )

    def test_esmtpWithoutHostname(self):
        """
        If I{--esmtp} is given without I{--hostname}, L{Options.parseOptions}
        raises L{UsageError}.
        """
        options = Options()
        exc = self.assertRaises(UsageError, options.parseOptions, ["--esmtp"])
        self.assertEqual("--esmtp requires --hostname", str(exc))

    def test_auth(self):
        """
        Tests that the --auth option registers a checker.
        """
        options = Options()
        options.parseOptions(["--auth", "memory:admin:admin:bob:password"])
        self.assertEqual(len(options["credCheckers"]), 1)
        checker = options["credCheckers"][0]
        interfaces = checker.credentialInterfaces
        registered_checkers = options.service.smtpPortal.checkers
        for iface in interfaces:
            self.assertEqual(checker, registered_checkers[iface])
