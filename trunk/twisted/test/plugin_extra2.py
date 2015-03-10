# Copyright (c) 2005 Divmod, Inc.
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Test plugin used in L{twisted.test.test_plugin}.
"""

from zope.interface import classProvides

from twisted.plugin import IPlugin
from twisted.test.test_plugin import ITestPlugin



class FourthTestPlugin:
    classProvides(ITestPlugin,
                  IPlugin)

    def test1():
        pass
    test1 = staticmethod(test1)



class FifthTestPlugin:
    """
    More documentation: I hate you.
    """
    classProvides(ITestPlugin,
                  IPlugin)

    def test1():
        pass
    test1 = staticmethod(test1)
