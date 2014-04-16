# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for the command-line scripts in the top-level I{bin/} directory.

Tests for actual functionality belong elsewhere, written in a way that doesn't
involve launching child processes.
"""

from os import devnull, getcwd, chdir
from sys import executable
from subprocess import PIPE, Popen

from twisted.trial.unittest import SkipTest, TestCase
from twisted.python.modules import getModule
from twisted.python.filepath import FilePath
from twisted.python.test.test_shellcomp import ZshScriptTestMixin



def outputFromPythonScript(script, *args):
    """
    Synchronously run a Python script, with the same Python interpreter that
    ran the process calling this function, using L{Popen}, using the given
    command-line arguments, with standard input and standard error both
    redirected to L{os.devnull}, and return its output as a string.

    @param script: The path to the script.
    @type script: L{FilePath}

    @param args: The command-line arguments to follow the script in its
        invocation (the desired C{sys.argv[1:]}).
    @type args: L{tuple} of L{str}

    @return: the output passed to the proces's C{stdout}, without any messages
        from C{stderr}.
    @rtype: L{bytes}
    """
    nullInput = file(devnull, "rb")
    nullError = file(devnull, "wb")
    stdout = Popen([executable, script.path] + list(args),
                   stdout=PIPE, stderr=nullError, stdin=nullInput).stdout.read()
    nullInput.close()
    nullError.close()
    return stdout



class ScriptTestsMixin:
    """
    Mixin for L{TestCase} subclasses which defines a helper function for testing
    a Twisted-using script.
    """
    bin = getModule("twisted").pathEntry.filePath.child("bin")

    def scriptTest(self, name):
        """
        Verify that the given script runs and uses the version of Twisted
        currently being tested.

        This only works when running tests against a vcs checkout of Twisted,
        since it relies on the scripts being in the place they are kept in
        version control, and exercises their logic for finding the right version
        of Twisted to use in that situation.

        @param name: A path fragment, relative to the I{bin} directory of a
            Twisted source checkout, identifying a script to test.
        @type name: C{str}

        @raise SkipTest: if the script is not where it is expected to be.
        """
        script = self.bin.preauthChild(name)
        if not script.exists():
            raise SkipTest(
                "Script tests do not apply to installed configuration.")

        from twisted.copyright import version
        scriptVersion = outputFromPythonScript(script, '--version')

        self.assertIn(str(version), scriptVersion)



class ScriptTests(TestCase, ScriptTestsMixin):
    """
    Tests for the core scripts.
    """
    def test_twistd(self):
        self.scriptTest("twistd")


    def test_twistdPathInsert(self):
        """
        The twistd script adds the current working directory to sys.path so
        that it's able to import modules from it.
        """
        script = self.bin.child("twistd")
        if not script.exists():
            raise SkipTest(
                "Script tests do not apply to installed configuration.")
        cwd = getcwd()
        self.addCleanup(chdir, cwd)
        testDir = FilePath(self.mktemp())
        testDir.makedirs()
        chdir(testDir.path)
        testDir.child("bar.tac").setContent(
            "import sys\n"
            "print sys.path\n")
        output = outputFromPythonScript(script, '-ny', 'bar.tac')
        self.assertIn(repr(testDir.path), output)


    def test_manhole(self):
        self.scriptTest("manhole")


    def test_trial(self):
        self.scriptTest("trial")


    def test_trialPathInsert(self):
        """
        The trial script adds the current working directory to sys.path so that
        it's able to import modules from it.
        """
        script = self.bin.child("trial")
        if not script.exists():
            raise SkipTest(
                "Script tests do not apply to installed configuration.")
        cwd = getcwd()
        self.addCleanup(chdir, cwd)
        testDir = FilePath(self.mktemp())
        testDir.makedirs()
        chdir(testDir.path)
        testDir.child("foo.py").setContent("")
        output = outputFromPythonScript(script, 'foo')
        self.assertIn("PASSED", output)


    def test_pyhtmlizer(self):
        self.scriptTest("pyhtmlizer")


    def test_tap2rpm(self):
        self.scriptTest("tap2rpm")


    def test_tap2deb(self):
        self.scriptTest("tap2deb")


    def test_tapconvert(self):
        self.scriptTest("tapconvert")


    def test_deprecatedTkunzip(self):
        """
        The entire L{twisted.scripts.tkunzip} module, part of the old Windows
        installer tool chain, is deprecated.
        """
        from twisted.scripts import tkunzip
        warnings = self.flushWarnings(
            offendingFunctions=[self.test_deprecatedTkunzip])
        self.assertEqual(DeprecationWarning, warnings[0]['category'])
        self.assertEqual(
            "twisted.scripts.tkunzip was deprecated in Twisted 11.1.0: "
            "Seek unzipping software outside of Twisted.",
            warnings[0]['message'])
        self.assertEqual(1, len(warnings))


    def test_deprecatedTapconvert(self):
        """
        The entire L{twisted.scripts.tapconvert} module is deprecated.
        """
        from twisted.scripts import tapconvert
        warnings = self.flushWarnings(
            offendingFunctions=[self.test_deprecatedTapconvert])
        self.assertEqual(DeprecationWarning, warnings[0]['category'])
        self.assertEqual(
            "twisted.scripts.tapconvert was deprecated in Twisted 12.1.0: "
            "tapconvert has been deprecated.",
            warnings[0]['message'])
        self.assertEqual(1, len(warnings))



class ZshIntegrationTestCase(TestCase, ZshScriptTestMixin):
    """
    Test that zsh completion functions are generated without error
    """
    generateFor = [('twistd', 'twisted.scripts.twistd.ServerOptions'),
                   ('trial', 'twisted.scripts.trial.Options'),
                   ('pyhtmlizer', 'twisted.scripts.htmlizer.Options'),
                   ('tap2rpm', 'twisted.scripts.tap2rpm.MyOptions'),
                   ('tap2deb', 'twisted.scripts.tap2deb.MyOptions'),
                   ('tapconvert', 'twisted.scripts.tapconvert.ConvertOptions'),
                   ('manhole', 'twisted.scripts.manhole.MyOptions')
                   ]

