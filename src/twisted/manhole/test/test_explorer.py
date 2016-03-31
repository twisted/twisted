# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.manhole.explorer}.
"""

from twisted.trial import unittest
from twisted.manhole.explorer import (
    CRUFT_WatchyThingie,
    ExplorerImmutable,
    Pool,
    _WatchMonkey,
    )


class Foo:
    """
    Test helper.
    """


class PoolTests(unittest.TestCase):
    """
    Tests for the Pool class.
    """

    def test_instanceBuilding(self):
        """
        If the object is not in the pool a new instance is created and
        returned.
        """
        p = Pool()
        e = p.getExplorer(123, 'id')
        self.assertIsInstance(e, ExplorerImmutable)
        self.assertEqual(e.value, 123)
        self.assertEqual(e.identifier, 'id')



class CRUFTWatchyThingieTests(unittest.TestCase):
    """
    Tests for the CRUFT_WatchyThingie class.
    """
    def test_watchObjectConstructedClass(self):
        """
        L{CRUFT_WatchyThingie.watchObject} changes the class of its
        first argument to a custom watching class.
        """
        foo = Foo()
        cwt = CRUFT_WatchyThingie()
        cwt.watchObject(foo, 'id', 'cback')

        # check new constructed class
        newClassName = foo.__class__.__name__
        self.assertEqual(newClassName, "WatchingFoo%X" % (id(foo),))


    def test_watchObjectConstructedInstanceMethod(self):
        """
        L{CRUFT_WatchyThingie.watchingfoo} adds a C{_watchEmitChanged}
        attribute which refers to a bound method on the instance
        passed to it.
        """
        foo = Foo()
        cwt = CRUFT_WatchyThingie()
        cwt.watchObject(foo, 'id', 'cback')

        # check new constructed instance method
        self.assertIdentical(foo._watchEmitChanged.im_self, foo)



class WatchMonkeyTests(unittest.TestCase):
    """
    Tests for the _WatchMonkey class.
    """
    def test_install(self):
        """
        When _WatchMonkey is installed on a method, calling that
        method calls the _WatchMonkey.
        """
        class Foo:
            """
            Helper.
            """
            def someMethod(self):
                """
                Just a method.
                """

        foo = Foo()
        wm = _WatchMonkey(foo)
        wm.install('someMethod')

        # patch wm's method to check that the method was exchanged
        called = []
        wm.__call__ = lambda s: called.append(True)

        # call and check
        foo.someMethod()
        self.assertTrue(called)
