# -*- test-case-name: twisted.test.test_plugin -*-
# Copyright (c) 2005 Divmod, Inc.
# See LICENSE for details.

"""
I'm a test drop-in.  The plugin system's unit tests use me.  No one
else should.
"""

from zope.interface import classProvides

from twisted.python.components import backwardsCompatImplements
from twisted.plugin import IPlugin, ITestPlugin, ITestPlugin2

class TestPlugin:
    """A plugin used solely for testing purposes.
    """
    classProvides(ITestPlugin,
                  IPlugin)
    def test1():
        pass

    test1 = staticmethod(test1)

backwardsCompatImplements(TestPlugin)


class AnotherTestPlugin:
    """Another plugin used solely for testing purposes.
    """
    classProvides(ITestPlugin2,
                  IPlugin)
    def test():
        pass
    test = staticmethod(test)

backwardsCompatImplements(AnotherTestPlugin)


class ThirdTestPlugin:
    """Another plugin used solely for testing purposes.
    """
    classProvides(ITestPlugin2,
                  IPlugin)
    def test():
        pass
    test = staticmethod(test)

backwardsCompatImplements(ThirdTestPlugin)

