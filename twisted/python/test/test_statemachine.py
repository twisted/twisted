# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for C{twisted.python.statemachine}.
"""

from twisted.trial.unittest import TestCase
from twisted.python.statemachine import makeStatefulDispatcher


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
            bar = makeStatefulDispatcher('quux', bar)

            def _quux_A(self):
                return 'a'

            def _quux_B(self):
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
        given one.
        """
        def aFunc():
            pass
        aFunc = makeStatefulDispatcher("theName", aFunc)
        self.assertEqual(aFunc.__name__, "theName")
        self.assertEqual(aFunc.func_name, "theName")


    def test_default(self):
        """
        If no method can be found for a given state, L{makeStatefulDispatcher}
        will lookup '_method_default'.
        """
        class Foo:
            _state = 'A'

            def bar(self):
                pass
            bar = makeStatefulDispatcher('quux', bar)

            def _quux_A(self):
                return 'a'

            def _quux_default(self):
                return 'default'

        stateful = Foo()
        self.assertEqual(stateful.bar(), 'a')
        stateful._state = 'B'
        self.assertEqual(stateful.bar(), 'default')
        stateful._state = 'C'
        self.assertEqual(stateful.bar(), 'default')
