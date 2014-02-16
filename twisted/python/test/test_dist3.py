# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.python.dist3}.
"""

from __future__ import division

from twisted.trial.unittest import TestCase

from twisted.python.dist3 import modulesToInstall
from twisted.python.filepath import FilePath


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
        root = FilePath(twisted.__file__.encode("utf-8")).parent().parent()
        for module in modulesToInstall:
            segments = module.encode("utf-8").split(b".")
            segments[-1] += b".py"
            path = root.descendant(segments)
            alternateSegments = module.encode("utf-8").split(b".") + [
                b"__init__.py"]
            packagePath = root.descendant(alternateSegments)
            self.assertTrue(path.exists() or packagePath.exists(),
                            "Module %s does not exist" % (module,))
