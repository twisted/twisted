# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.runner.portmap}.
"""

from twisted.trial.unittest import SynchronousTestCase

from twisted.runner.portmap import _alias, set, unset


class AliasTests(SynchronousTestCase):
    """
    Tests for L{_alias}.
    """
    def test_makesAlias(self):
        """
        When C{_alias(foo)} is used as a decorator, the decorated function ends
        up as an alias for C{foo}.  That is, calling it is the same as calling
        C{foo}.
        """
        def foo(a, b):
            return a - b
        @_alias(foo)
        def bar():
            pass
        self.assertEqual(5, foo(10, b=5))


    def test_name(self):
        """
        The name of the decorated function is the same as the name of the
        target of the alias.
        """
        def foo():
            pass
        @_alias(foo)
        def bar():
            pass
        self.assertEqual(foo.__name__, bar.__name__)


    def test_docstring(self):
        """
        The docstring is copied from the decorated function to the target of
        the alias.
        """
        def foo():
            pass
        @_alias(foo)
        def bar():
            # Disregard the coding standard docstring standard to simplify the
            # assertion below.
            "This is bar"
        self.assertEqual(bar.__doc__, "This is bar")


    def test_original(self):
        """
        The target of the alias is available as the C{target} attribute of the
        decorated function.
        """
        def foo():
            pass
        @_alias(foo)
        def bar():
            pass
        self.assertIs(foo, bar.target)



class PortmapTests(SynchronousTestCase):
    """
    Tests for L{set} and L{unset}.
    """
    def test_set(self):
        """
        L{set} is an alias for I{pmap_set}.
        """
        self.assertEqual("pmap_set", set.__name__)


    def test_unset(self):
        """
        L{unset} is an alias for I{pmap_unset}.
        """
        self.assertEqual("pmap_unset", unset.__name__)
