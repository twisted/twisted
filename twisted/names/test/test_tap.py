# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.names.tap}.
"""

from twisted.trial.unittest import TestCase
from twisted.python.usage import UsageError
from twisted.names.tap import Options
from twisted.names.dns import PORT
from twisted.names.secondary import SecondaryAuthorityService


class OptionsTests(TestCase):
    """
    Tests for L{Options}, defining how command line arguments for the DNS server
    are parsed.
    """
    def test_malformedSecondary(self):
        """
        If the value supplied for an I{--secondary} option does not provide a
        server IP address, optional port number, and domain name,
        L{Options.parseOptions} raises L{UsageError}.
        """
        options = Options()
        self.assertRaises(
            UsageError, options.parseOptions, ['--secondary', ''])
        self.assertRaises(
            UsageError, options.parseOptions, ['--secondary', '1.2.3.4'])
        self.assertRaises(
            UsageError, options.parseOptions, ['--secondary', '1.2.3.4:hello'])
        self.assertRaises(
            UsageError, options.parseOptions,
            ['--secondary', '1.2.3.4:hello/example.com'])


    def test_secondary(self):
        """
        An argument of the form C{"ip/domain"} is parsed by L{Options} for the
        I{--secondary} option and added to its list of secondaries, using the
        default DNS port number.
        """
        options = Options()
        options.parseOptions(['--secondary', '1.2.3.4/example.com'])
        self.assertEqual(
            [(('1.2.3.4', PORT), ['example.com'])], options.secondaries)


    def test_secondaryExplicitPort(self):
        """
        An argument of the form C{"ip:port/domain"} can be used to specify an
        alternate port number for for which to act as a secondary.
        """
        options = Options()
        options.parseOptions(['--secondary', '1.2.3.4:5353/example.com'])
        self.assertEqual(
            [(('1.2.3.4', 5353), ['example.com'])], options.secondaries)


    def test_secondaryAuthorityServices(self):
        """
        After parsing I{--secondary} options, L{Options} constructs a
        L{SecondaryAuthorityService} instance for each configured secondary.
        """
        options = Options()
        options.parseOptions(['--secondary', '1.2.3.4:5353/example.com',
                              '--secondary', '1.2.3.5:5354/example.com'])
        self.assertEqual(len(options.svcs), 2)
        secondary = options.svcs[0]
        self.assertIsInstance(options.svcs[0], SecondaryAuthorityService)
        self.assertEqual(secondary.primary, '1.2.3.4')
        self.assertEqual(secondary._port, 5353)
        secondary = options.svcs[1]
        self.assertIsInstance(options.svcs[1], SecondaryAuthorityService)
        self.assertEqual(secondary.primary, '1.2.3.5')
        self.assertEqual(secondary._port, 5354)
