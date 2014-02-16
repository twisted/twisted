# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.python.dist3}.
"""

from __future__ import division

import os
from twisted.trial.unittest import TestCase

from twisted.python.dist3 import modulesToInstall


class ModulesToInstallTests(TestCase):
    """
    Tests for L{modulesToInstall}.
    """
    def test_sanityCheck(self):
        """
        L{modulesToInstall} includes some obvious module names.
        """
        self.assertIn("twisted.internet.reactor", modulesToInstall)
        self.assertIn("twisted.python.test.test_dist3", modulesToInstall)


    def test_exist(self):
        """
        All modules listed in L{modulesToInstall} exist.
        """
        import twisted
        root = os.path.dirname(os.path.dirname(twisted.__file__))
        for module in modulesToInstall:
            segments = module.split(".")
            segments[-1] += ".py"
            path = os.path.join(root, *segments)
            alternateSegments = module.split(".") + ["__init__.py"]
            packagePath = os.path.join(root, *alternateSegments)
            self.assertTrue(os.path.exists(path) or
                            os.path.exists(packagePath),
                            "Module {0} does not exist".format(module))
