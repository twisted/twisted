# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.names.tap}.
"""

from io import BytesIO
import sys

from twisted.trial.unittest import TestCase
from twisted.python.usage import UsageError
from twisted.names.tap import makeService, Options, _buildResolvers
from twisted.names.dns import PORT
from twisted.names.secondary import SecondaryAuthorityService
from twisted.names.resolve import ResolverChain
from twisted.names.client import Resolver

class OptionsTests(TestCase):
    """
    Tests for L{Options}, defining how command line arguments for the
    DNS server are parsed.
    """
    def test_operatingModeOptionsExist(self):
        """
        The option names listed in L{Options._operatingModeOptions}
        must all be valid command line options. This test guards
        against accidental removal of an operating mode related
        option, without also updating the _operatingModeOptions list.
        """
        options = Options()
        availableOptionNames = options.synonyms.values()
        for optionName in options._operatingModeOptions:
            self.assertTrue(
                optionName in availableOptionNames,
                msg="%r option not found." % (optionName,))


    def test_unknownOperatingMode(self):
        """
        At least one of the DNS operating mode options must be given
        ie --recursive, --secondary, --{py,bind}zone or --hosts-file,
        or an error message is printed to stderr and L{SystemExit} is
        raised.
        """
        options = Options()
        options.parseOptions([])
        fakeStderr = BytesIO()
        self.patch(sys, 'stderr', fakeStderr)
        self.assertRaises(
            SystemExit, makeService, options)
        self.assertNotEqual(fakeStderr.getvalue(), '')


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


    def test_recursiveConfiguration(self):
        """
        Recursive DNS lookups, if enabled, should be a last-resort option.
        Any other lookup method (cache, local lookup, etc.) should take
        precedence over recursive lookups
        """
        options = Options()
        options.parseOptions(['--hosts-file', 'hosts.txt', '--recursive'])
        ca, cl = _buildResolvers(options)

        # Extra cleanup, necessary on POSIX because client.Resolver doesn't know
        # when to stop parsing resolv.conf.  See #NNN for improving this.
        for x in cl:
            if isinstance(x, ResolverChain):
                recurser = x.resolvers[-1]
                if isinstance(recurser, Resolver):
                    recurser._parseCall.cancel()

        self.assertIsInstance(cl[-1], ResolverChain)
