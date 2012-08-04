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

    maintainer = "Jane Doe <janedoe@example.com>"

    def setUp(self):
        return self._checkForDebBuild()

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
        Running tap2deb should produce a bunch of files.
        """
        basedir = FilePath(self.mktemp())
        basedir.makedirs()
        self.addCleanup(os.chdir, os.getcwd())
        os.chdir(basedir.path)

        # make a temporary .tap file
        version = '1.0'
        tap_name = 'lemon'
        tap_file = basedir.child("%s.tap" % tap_name)
        tap_file.setContent("# Dummy .tap file")
        build_dir = basedir.child('.build')
        input_dir = build_dir.child('twisted-%s-%s' % (tap_name, version))
        input_name = 'twisted-%s_%s' % (tap_name, version)

        # run
        args = ["--tapfile", tap_file.path, "--maintainer", self.maintainer]
        tap2deb.run(args)

        # verify input files were created
        self.assertEqual(len(input_dir.listdir()), 4)
        self.assertTrue(input_dir.child('lemon.tap').exists())

        debian_dir = input_dir.child('debian')
        self.assertTrue(debian_dir.exists())
        self.assertTrue(debian_dir.child('source').child('format').exists())

        for name in ['README.Debian', 'conffiles', 'default', 'init.d',
                     'postinst', 'prerm', 'postrm', 'changelog', 'control',
                     'compat', 'copyright', 'dirs', 'rules']:
            self.assertTrue(debian_dir.child(name).exists())

        # verify 4 output files were created
        output = build_dir.globChildren(input_name + "*")
        self.assertEqual(len(output), 4)
        for ext in ['.deb', '.dsc', '.tar.gz', '.changes']:
            self.assertEqual(len(build_dir.globChildren('*' + ext)), 1)

