# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

#

from twisted.trial.unittest import TestCase

from twisted.python import context

class ContextTest(TestCase):

    def testBasicContext(self):
        self.assertEqual(context.get("x"), None)
        self.assertEqual(context.call({"x": "y"}, context.get, "x"), "y")
        self.assertEqual(context.get("x"), None)
