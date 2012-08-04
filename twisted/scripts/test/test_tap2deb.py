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

    def setUp(self):
        self._checkForDebBuild()

        self.maintainer = "Jane Doe <janedoe@example.com>"
        self.basedir = FilePath(self.mktemp())
        self.basedir.makedirs()
        self.addCleanup(os.chdir, os.getcwd())
        os.chdir(self.basedir.path)


    def _checkForDebBuild(self):
        """
        tap2deb requires dpkg-buildpackage; skip tests if dpkg-buildpackage
        is not present.
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
        Commandline options should default to sensible values.
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
        Calling tap2deb should produce a DEB and DSC file.
        """
        # make a temporary .tap file
        tap = self.basedir.child("lemon.tap")
        tap.setContent("# Dummy .tap file")

        # run
        args = ["--tapfile", tap.path, "--maintainer", self.maintainer]
        tap2deb.run(args)

        build = tap.child('.build')
        for name in ['twisted-twistd_1.0_all.deb',
                     'twisted-twistd_1.0_all.dsc']:
            self.assertTrue(build.child(name).exists)

