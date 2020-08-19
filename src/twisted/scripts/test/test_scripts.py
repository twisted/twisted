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
import types
from typing import Optional, TYPE_CHECKING

from twisted.trial.unittest import TestCase
from twisted.python.filepath import FilePath
from twisted.python.test.test_shellcomp import ZshScriptTestMixin
from twisted.scripts import htmlizer, trial, twistd


def _stdoutFromPythonModule(
    module: types.ModuleType, *args: str, check: bool = True, cwd: Optional[str] = None
) -> str:
    return subprocess.run(
        [sys.executable, "-m", module.__name__, *args],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        stdin=subprocess.DEVNULL,
        check=check,
        cwd=cwd,
    ).stdout.decode()


if TYPE_CHECKING:
    from typing_extensions import Protocol

    class _HasAssertIn(Protocol):
        def assertIn(self, left: str, right: str) -> None:
            ...


class ScriptTestsMixin:
    """
    Mixin for L{TestCase} subclasses which defines a helper function for testing
    a Twisted-using script.
    """

    def scriptTest(self: "_HasAssertIn", module: types.ModuleType) -> None:
        from twisted.copyright import version

        scriptVersion = _stdoutFromPythonModule(module, "--version")

        self.assertIn(str(version), scriptVersion)


class ScriptTests(TestCase, ScriptTestsMixin):
    """
    Tests for the core scripts.
    """

    def test_twistd(self) -> None:
        self.scriptTest(twistd)

    def test_twistdPathInsert(self) -> None:
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
            _stdoutFromPythonModule(
                twistd, "-ny", "bar.tac", cwd=testDir.path, check=False
            )
        )
        self.assertIn(testDir.path, output)

    def test_twistdAtExit(self) -> None:
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
            assert process.stdout
            self.assertTrue(
                any(
                    line.endswith(b"test_twistdAtExit started\n")
                    for line in process.stdout
                )
            )
            process.send_signal(signal.SIGINT)

        self.assertEqual(process.returncode, -signal.SIGINT)
        self.assertEqual(testDir.child("didexit").getContent(), b"didexit")

    def test_trial(self) -> None:
        self.scriptTest(trial)

    def test_trialPathInsert(self) -> None:
        """
        The trial script adds the current working directory to sys.path so that
        it's able to import modules from it.
        """
        testDir = FilePath(self.mktemp())
        testDir.makedirs()
        testDir.child("foo.py").setContent(b"")
        output = _stdoutFromPythonModule(trial, "foo", cwd=testDir.path)
        self.assertIn("PASSED", output)

    def test_pyhtmlizer(self) -> None:
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
