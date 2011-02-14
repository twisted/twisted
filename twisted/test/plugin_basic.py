# Copyright (c) 2005 Divmod, Inc.
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

# Don't change the docstring, it's part of the tests
"""
I'm a test drop-in.  The plugin system's unit tests use me.  No one
else should.
"""

from zope.interface import classProvides

from twisted.plugin import IPlugin
from twisted.test.test_plugin import ITestPlugin, ITestPlugin2



class TestPlugin:
    """
    A plugin used solely for testing purposes.
    """

    classProvides(ITestPlugin,
                  IPlugin)

    def test1():
        pass
    test1 = staticmethod(test1)



class AnotherTestPlugin:
    """
    Another plugin used solely for testing purposes.
    """

    classProvides(ITestPlugin2,
                  IPlugin)

    def test():
        pass
    test = staticmethod(test)



class ThirdTestPlugin:
    """
    Another plugin used solely for testing purposes.
    """

    classProvides(ITestPlugin2,
                  IPlugin)

    def test():
        pass
    test = staticmethod(test)

