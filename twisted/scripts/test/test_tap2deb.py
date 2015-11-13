# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.scripts.tap2deb}.
"""

import warnings

from twisted.python import usage, procutils
from twisted.python.filepath import FilePath

from twisted.trial.unittest import TestCase, SkipTest

with warnings.catch_warnings():
    warnings.simplefilter("ignore", category=DeprecationWarning)
    from twisted.scripts import tap2deb


class TestTap2DEB(TestCase):
    """
    Tests for the L{tap2deb} script.
    """
    maintainer = "Jane Doe <janedoe@example.com>"

    def test_maintainerOption(self):
        """
        The C{--maintainer} option must be specified on the commandline or
        passed to L{tap2deb.run}.
        """
        config = tap2deb.MyOptions()
        self.assertRaises(usage.UsageError, config.parseOptions, [])
        self.assertRaises(SystemExit, tap2deb.run, [])


    def test_optionDefaults(self):
        """
        Commandline options default to sensible values.
        """
        config = tap2deb.MyOptions()
        config.parseOptions(['--maintainer', self.maintainer])

        self.assertEqual(config['tapfile'], 'twistd.tap')
        self.assertEqual(config['maintainer'], self.maintainer)
        self.assertEqual(config['protocol'], '')
        self.assertEqual(config['description'], '')
        self.assertEqual(config['long_description'], '')
        self.assertEqual(config['set-version'], '1.0')
        self.assertEqual(config['debfile'], None)
        self.assertEqual(config['type'], 'tap')


    def test_missingMaintainer(self):
        """
        Omitting the maintainer argument results in L{tap2deb.run} raising
        C{SystemExit}.
        """
        error = self.assertRaises(SystemExit, tap2deb.run,
            ["--tapfile", "foo"])
        self.assertTrue(str(error).endswith('maintainer must be specified.'))


    def test_basicOperation(self):
        """
        Running the L{tap2deb} script produces a bunch of files using
        C{dpkg-buildpackage}.
        """
        # Skip tests if dpkg-buildpackage is not present
        if not procutils.which("dpkg-buildpackage"):
            raise SkipTest("dpkg-buildpackage must be present to test tap2deb")

        baseDir = FilePath(self.mktemp())
        baseDir.makedirs()

        # Make a temporary .tap file
        version = '1.0'
        tapName = 'lemon'
        tapFile = baseDir.child("%s.tap" % (tapName,))
        tapFile.setContent("# Dummy .tap file")

        buildDir = FilePath('.build')
        outputDir = buildDir.child('twisted-%s-%s' % (tapName, version))

        # Run
        args = ["--tapfile", tapFile.path, "--maintainer", self.maintainer]
        tap2deb.run(args)

        # Verify input files were created
        self.assertEqual(sorted(outputDir.listdir()),
            ['build-stamp', 'debian', 'install-stamp', 'lemon.tap'])

        debianDir = outputDir.child('debian')
        for name in ['README.Debian', 'conffiles', 'default', 'init.d',
                     'postinst', 'prerm', 'postrm', 'changelog', 'control',
                     'copyright', 'dirs', 'rules']:
            self.assertTrue(debianDir.child(name).exists())

        # Verify 4 output files were created
        self.assertTrue(buildDir.child('twisted-lemon_1.0_all.deb').exists())
        self.assertTrue(buildDir.child('twisted-lemon_1.0.tar.gz').exists())
        self.assertTrue(buildDir.child('twisted-lemon_1.0.dsc').exists())
        self.assertEqual(
            len(buildDir.globChildren('twisted-lemon_1.0_*.changes')), 1)
