# Copyright (c) 2008 Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.mail.tap}.
"""

from twisted.trial.unittest import TestCase

from twisted.python.usage import UsageError
from twisted.mail.tap import Options


class OptionsTestCase(TestCase):
    """
    Tests for the command line option parser used for C{twistd mail}.
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

