# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for the command-line interface to lore.
"""

from twisted.trial.unittest import TestCase
from twisted.scripts.test.test_scripts import ScriptTestsMixin
from twisted.python.test.test_shellcomp import ZshScriptTestMixin



class ScriptTests(TestCase, ScriptTestsMixin):
    """
    Tests for all one of lore's scripts.
    """
    def test_lore(self):
        self.scriptTest("lore/lore")



class ZshIntegrationTestCase(TestCase, ZshScriptTestMixin):
    """
    Test that zsh completion functions are generated without error
    """
    generateFor = [('lore', 'twisted.lore.scripts.lore.Options')]
