# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for C{twisted.python._statedispatch}.
"""

from twisted.trial.unittest import TestCase
from twisted.python._statedispatch import makeStatefulDispatcher


class MakeStatefulDispatcherTests(TestCase):
    """
    Tests for L{makeStatefulDispatcher}.
    """
    def test_functionCalledByState(self):
        """
        A method defined with L{makeStatefulDispatcher} invokes a second
        method based on the current state of the object.
        """
        class Foo:
            _state = 'A'

            def bar(self):
                pass
            bar = makeStatefulDispatcher(bar)

            def _bar_A(self):
                return 'a'

            def _bar_B(self):
                return 'b'

        stateful = Foo()
        self.assertEqual(stateful.bar(), 'a')
        stateful._state = 'B'
        self.assertEqual(stateful.bar(), 'b')
        stateful._state = 'C'
        self.assertRaises(RuntimeError, stateful.bar)


    def test_name(self):
        """
        A method defined with L{makeStatefulDispatcher} has its name set to
        that of the template function, unless the name is overridden.
        """
        def aFunc():
            pass
        aFunc = makeStatefulDispatcher(aFunc)
        self.assertEqual(aFunc.__name__, "aFunc")
        self.assertEqual(aFunc.func_name, "aFunc")

        # We can override the name, though:
        def another():
            pass
        anotherFunc = makeStatefulDispatcher(another, name="different")
        self.assertEqual(anotherFunc.__name__, "different")
        self.assertEqual(anotherFunc.func_name, "different")


    def test_default(self):
        """
        If no method can be found for a given state, L{makeStatefulDispatcher}
        will lookup '_method_default'.
        """
        class Foo:
            _state = 'A'

            def bar(self):
                pass
            bar = makeStatefulDispatcher(bar)

            def _bar_A(self):
                return 'a'

            def _bar_default(self):
                return 'default'

        stateful = Foo()
        self.assertEqual(stateful.bar(), 'a')
        stateful._state = 'B'
        self.assertEqual(stateful.bar(), 'default')
        stateful._state = 'C'
        self.assertEqual(stateful.bar(), 'default')
