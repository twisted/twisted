"""This module intentionally fails to import.

See twisted.trial.test.test_adapters.TestFailureFormatting.testImportError
"""
import Supercalifragilisticexpialidocious

from twisted.trial.test import common

class ThisTestWillNeverSeeTheLightOfDay(common.BaseTest, unittest.TestCase):
    pass


