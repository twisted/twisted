# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.scripts.mktap}.
"""

import sys
try:
    import pwd, grp
except ImportError:
    pwd = None

from twisted.trial.unittest import TestCase

from twisted.scripts.mktap import run, getid, loadPlugins
from twisted.application.service import IProcess, loadApplication
from twisted.test.test_twistd import patchUserDatabase
from twisted.plugins.twisted_ftp import TwistedFTP


class RunTests(TestCase):
    """
    Tests for L{twisted.scripts.mktap.run}.
    """
    def setUp(self):
        """
        Save the original value of L{sys.argv} so that tests can change it
        as necessary.
        """
        self.argv = sys.argv[:]


    def tearDown(self):
        """
        Restore the original value of L{sys.argv}.
        """
        sys.argv[:] = self.argv


    def _saveConfiguredIDTest(self, argv, uid, gid):
        """
        Test that when L{run} is invoked and L{sys.argv} has the given
        value, the resulting application has the specified UID and GID.

        @type argv: C{list} of C{str}
        @param argv: The value to which to set L{sys.argv} before calling L{run}.

        @type uid: C{int}
        @param uid: The expected value for the resulting application's
            L{IProcess.uid}.

        @type gid: C{int}
        @param gid: The expected value for the resulting application's
            L{IProcess.gid}.
        """
        sys.argv = argv
        run()
        app = loadApplication("ftp.tap", "pickle", None)
        process = IProcess(app)
        self.assertEqual(process.uid, uid)
        self.assertEqual(process.gid, gid)


    def test_getNumericID(self):
        """
        L{run} extracts numeric UID and GID information from the command
        line and persists it with the application object.
        """
        uid = 1234
        gid = 4321
        self._saveConfiguredIDTest(
            ["mktap", "--uid", str(uid), "--gid", str(gid), "ftp"],
            uid, gid)


    def test_getNameID(self):
        """
        L{run} extracts name UID and GID information from the command
        line and persists it with the application object.
        """
        user = "foo"
        uid = 1234
        group = "bar"
        gid = 4321
        patchUserDatabase(self.patch, user, uid, group, gid)
        self._saveConfiguredIDTest(
            ["mktap", "--uid", user, "--gid", group, "ftp"],
            uid, gid)
    if pwd is None:
        test_getNameID.skip = (
            "Username/UID Group name/GID translation requires pwd and grp "
            "modules.")



class HelperTests(TestCase):
    """
    Tests for miscellaneous utility functions related to mktap.
    """
    def test_getid(self):
        """
        L{getid} returns a two-tuple of integers giving the numeric values of
        the strings it is passed.
        """
        uid = 1234
        gid = 4321
        self.assertEqual(getid(str(uid), str(gid)), (uid, gid))


    def test_loadPlugins(self):
        """
        L{loadPlugins} returns a C{dict} mapping tap names to tap plugins.
        """
        plugins = loadPlugins()
        self.assertTrue(plugins, "There should be at least one plugin.")
        # Make sure the mapping is set up properly.
        for k, v in plugins.iteritems():
            self.assertEqual(k, v.tapname)

        # Make sure one of the always-available builtin plugins is there. 
        self.assertIdentical(plugins['ftp'], TwistedFTP)
