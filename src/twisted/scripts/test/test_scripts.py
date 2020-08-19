# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for the command-line scripts in the top-level I{bin/} directory.

Tests for actual functionality belong elsewhere, written in a way that doesn't
involve launching child processes.
"""
import json
import signal
import subprocess
import sys
import textwrap

from twisted.trial.unittest import TestCase
from twisted.python.filepath import FilePath
from twisted.python.test.test_shellcomp import ZshScriptTestMixin
from twisted.scripts import htmlizer, trial, twistd


def outputFromPythonModule(module, *args, check=True, **kwargs):
    """
    Synchronously run a Python module, with the same Python interpreter that
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
    return subprocess.run(
        [sys.executable, "-m", module.__name__, *args],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        stdin=subprocess.DEVNULL,
        check=check,
        **kwargs,
    ).stdout


class ScriptTestsMixin:
    """
    Mixin for L{TestCase} subclasses which defines a helper function for testing
    a Twisted-using script.
    """

    def scriptTest(self, module):
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
        """

        from twisted.copyright import version

        scriptVersion = outputFromPythonModule(module, "--version")

        self.assertIn(str(version), scriptVersion.decode())


class ScriptTests(TestCase, ScriptTestsMixin):
    """
    Tests for the core scripts.
    """

    def test_twistd(self):
        self.scriptTest(twistd)

    def test_twistdPathInsert(self):
        """
        The twistd script adds the current working directory to sys.path so
        that it's able to import modules from it.
        """
        testDir = FilePath(self.mktemp())
        testDir.makedirs()
        testDir.child("bar.tac").setContent(
            textwrap.dedent(
                """\
                import json
                import sys

                print(json.dumps(sys.path))
                """
            ).encode()
        )
        output = json.loads(
            outputFromPythonModule(
                twistd, "-ny", "bar.tac", cwd=testDir.path, check=False
            )
        )
        self.assertIn(testDir.path, output)

    def test_twistdAtExit(self):
        testDir = FilePath(self.mktemp())
        testDir.makedirs()
        testDir.child("bar.tac").setContent(
            textwrap.dedent(
                """\
                import atexit
                import os
                import pathlib

                from twisted.application import service

                @atexit.register
                def _():
                    pathlib.Path("didexit").write_text("didexit")

                class Service(service.Service):
                    def startService(self):
                        from twisted.internet import reactor

                        reactor.callWhenRunning(print, "test_twistdAtExit started")

                application = service.Application("Demo application")
                Service().setServiceParent(application)
                """
            ).encode()
        )
        with subprocess.Popen(
            [sys.executable, "-m", twistd.__name__, "-ny", "bar.tac"],
            cwd=testDir.path,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        ) as process:
            self.assertTrue(
                any(
                    line.endswith(b"test_twistdAtExit started\n")
                    for line in process.stdout
                )
            )
            process.send_signal(signal.SIGINT)

        self.assertEqual(process.returncode, -signal.SIGINT)
        self.assertEqual(testDir.child("didexit").getContent(), b"didexit")

    def test_trial(self):
        self.scriptTest(trial)

    def test_trialPathInsert(self):
        """
        The trial script adds the current working directory to sys.path so that
        it's able to import modules from it.
        """
        testDir = FilePath(self.mktemp())
        testDir.makedirs()
        testDir.child("foo.py").setContent(b"")
        output = outputFromPythonModule(trial, "foo", cwd=testDir.path).decode()
        self.assertIn("PASSED", output)

    def test_pyhtmlizer(self):
        self.scriptTest(htmlizer)


class ZshIntegrationTests(TestCase, ZshScriptTestMixin):
    """
    Test that zsh completion functions are generated without error
    """

    generateFor = [
        ("twistd", "twisted.scripts.twistd.ServerOptions"),
        ("trial", "twisted.scripts.trial.Options"),
        ("pyhtmlizer", "twisted.scripts.htmlizer.Options"),
    ]
