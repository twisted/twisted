# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.mail.tap}.
"""

from twisted.trial.unittest import TestCase

from twisted.python.usage import UsageError
from twisted.mail.tap import Options
from twisted.python import deprecate
from twisted.python import versions


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


    def testPasswordfileDeprecation(self):
        """
        Test that the --passwordfile option will emit a correct warning.
        """
        options = Options()
        options.opt_passwordfile('/dev/null')
        warnings = self.flushWarnings([self.testPasswordfileDeprecation])
        self.assertEquals(warnings[0]['category'], DeprecationWarning)
        self.assertEquals(len(warnings), 1)
        msg = deprecate.getDeprecationWarningString(options.opt_passwordfile,
                             versions.Version('twisted.mail', 11, 0, 0))
        self.assertEquals(warnings[0]['message'], msg)


