# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for the command-line interfaces to conch.
"""
import importlib
from twisted.python.test.test_shellcomp import ZshScriptTestMixin
from twisted.scripts.test.test_scripts import ScriptTestsMixin
from twisted.trial.unittest import TestCase, SkipTest


def _importOrSkip(name):
    try:
        return importlib.import_module(name)
    except ImportError:
        raise SkipTest("Cannot run without {name}".format(name=name))


def _importsOrSkip(module_names=("pyasn1", "cryptography", "tty")):
    for module_name in module_names:
        _importOrSkip(module_name)


class ScriptTests(TestCase, ScriptTestsMixin):
    """
    Tests for the Conch scripts.
    """

    def test_conch(self):
        _importsOrSkip()
        from twisted.conch.scripts import conch

        self.scriptTest(conch)

    def test_cftp(self):
        _importsOrSkip()
        from twisted.conch.scripts import cftp

        self.scriptTest(cftp)

    def test_ckeygen(self):
        _importsOrSkip()
        from twisted.conch.scripts import ckeygen

        self.scriptTest(ckeygen)

    def test_tkconch(self):
        _importsOrSkip()
        tkinter = _importOrSkip("tkinter")
        from twisted.conch.scripts import tkconch

        try:
            tkinter.Tk().destroy()
        except tkinter.TclError as e:
            raise SkipTest("Can't test Tkinter: " + str(e))

        self.scriptTest(tkconch)


class ZshIntegrationTests(TestCase, ZshScriptTestMixin):
    """
    Test that zsh completion functions are generated without error
    """

    generateFor = [
        ("conch", "twisted.conch.scripts.conch.ClientOptions"),
        ("cftp", "twisted.conch.scripts.cftp.ClientOptions"),
        ("ckeygen", "twisted.conch.scripts.ckeygen.GeneralOptions"),
        ("tkconch", "twisted.conch.scripts.tkconch.GeneralOptions"),
    ]
