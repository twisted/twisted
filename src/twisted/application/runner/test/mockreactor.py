# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Mock reactor.
"""

from twisted.internet import error
from twisted.test.proto_helpers import MemoryReactor as BaseReactor



class MockReactor(BaseReactor):
    """
    Mock reactor.
    """
    def __init__(self, testCase):
        BaseReactor.__init__(self)
        self.testCase = testCase


    def install(self):
        """
        Mock installation of L{MockReactor}.
        """
        if self.hasInstalled:
            raise error.ReactorAlreadyInstalledError(
                "reactor already installed"
            )

        BaseReactor.install(self)

        import sys
        import twisted.internet

        modules = sys.modules.copy()
        modules["twisted.internet.reactor"] = self

        self.testCase.patch(sys, "modules", self)
        self.testCase.patch(twisted.internet, "reactor", self)
