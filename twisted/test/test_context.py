# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

#

from twisted.trial.unittest import TestCase

from twisted.python import context

class ContextTest(TestCase):

    def testBasicContext(self):
        self.assertEquals(context.get("x"), None)
        self.assertEquals(context.call({"x": "y"}, context.get, "x"), "y")
        self.assertEquals(context.get("x"), None)
