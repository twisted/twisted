# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.scripts.tap2deb}.
"""

import os

from twisted.scripts import tap2deb
from twisted.python import usage
from twisted.python import procutils
from twisted.python.filepath import FilePath

from twisted.trial.unittest import TestCase, SkipTest



class TestTap2DEB(TestCase):
    """
    Tests for the L{tap2deb} script.
    """
    maintainer = "Jane Doe <janedoe@example.com>"

    def setUp(self):
        """
        The L{tap2deb} script requires C{dpkg-buildpackage}; skip tests if
        C{dpkg-buildpackage} is not present.
        """
        if not procutils.which("dpkg-buildpackage"):
            raise SkipTest("dpkg-buildpackage must be present to test tap2deb")


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


    def test_basicOperation(self):
        """
        Running the L{tap2deb} script produces a bunch of files.
        """
        basedir = FilePath(self.mktemp())
        basedir.makedirs()
        self.addCleanup(os.chdir, os.getcwd())
        os.chdir(basedir.path)

        # Make a temporary .tap file
        version = '1.0'
        tapName = 'lemon'
        tapFile = basedir.child("%s.tap" % tapName)
        tapFile.setContent("# Dummy .tap file")
        buildDir = basedir.child('.build')
        inputDir = buildDir.child('twisted-%s-%s' % (tapName, version))
        inputName = 'twisted-%s_%s' % (tapName, version)

        # Run
        args = ["--tapfile", tapFile.path, "--maintainer", self.maintainer]
        tap2deb.run(args)

        # Verify input files were created
        self.assertEqual(len(inputDir.listdir()), 4)
        self.assertTrue(inputDir.child('lemon.tap').exists())

        debianDir = inputDir.child('debian')
        self.assertTrue(debianDir.exists())
        self.assertTrue(debianDir.child('source').child('format').exists())

        for name in ['README.Debian', 'conffiles', 'default', 'init.d',
                     'postinst', 'prerm', 'postrm', 'changelog', 'control',
                     'compat', 'copyright', 'dirs', 'rules']:
            self.assertTrue(debianDir.child(name).exists())

        # Verify 4 output files were created
        output = buildDir.globChildren(inputName + "*")
        self.assertEqual(len(output), 4)
        for ext in ['.deb', '.dsc', '.tar.gz', '.changes']:
            self.assertEqual(len(buildDir.globChildren('*' + ext)), 1)

