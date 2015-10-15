# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

import sys

from twisted.trial import unittest
from twisted.python.reflect import namedModule



class QtreactorTests(unittest.TestCase):
    """
    Tests for L{twisted.internet.qtreactor}.
    """
    def test_importQtreactor(self):
        """
        Attempting to import L{twisted.internet.qtreactor} should raise an
        C{ImportError} indicating that C{qtreactor} is no longer a part of
        Twisted.
        """
        sys.modules["qtreactor"] = None
        from twisted.plugins.twisted_qtstub import errorMessage
        try:
            namedModule('twisted.internet.qtreactor')
        except ImportError, e:
            self.assertEqual(str(e), errorMessage)
