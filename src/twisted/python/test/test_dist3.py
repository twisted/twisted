# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.python.dist3}.
"""


import os
import twisted

from twisted.trial.unittest import TestCase
from twisted.python._setup import notPortedModules


class ModulesToInstallTests(TestCase):
    """
    Tests for L{notPortedModules}.
    """

    def test_notexist(self):
        """
        All modules listed in L{notPortedModules} do not exist on Py3.
        """
        root = os.path.dirname(os.path.dirname(twisted.__file__))
        for module in notPortedModules:
            segments = module.split(".")
            segments[-1] += ".py"
            path = os.path.join(root, *segments)
            alternateSegments = module.split(".") + ["__init__.py"]
            packagePath = os.path.join(root, *alternateSegments)
            self.assertFalse(
                os.path.exists(path) or os.path.exists(packagePath),
                "Module {0} exists".format(module),
            )
