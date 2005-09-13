# -*- test-case-name: twisted.trial.test.test_trial -*-
#
# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.
#
# Author: Jonathan D. Simms <slyphon@twistedmatrix.com>

"""Unit testing framework."""

tbformat = 'plain'

from twisted.python import components
try:
    from zope.interface import interface, declarations
    from zope.interface.adapter import AdapterRegistry
except ImportError:
    raise ImportError, "you need zope.interface installed (http://zope.org/Products/ZopeInterface/)"

pyunit = __import__('unittest')

def _setUpAdapters():
    from twisted.spread import jelly
    from twisted.python import failure
    # sibling imports
    import types
    import reporter, runner, itrial, adapters, remote
    
    for a, o, i in [

# ---- ITestMethod adapters -----------
(runner.TestMethod, types.MethodType, itrial.ITestMethod),
(runner.PyUnitTestMethod, pyunit.TestCase, itrial.ITestMethod),

# ---- Magic Attribute Adapters -----------------------
(adapters.TupleTodo, types.TupleType, itrial.ITodo),
(adapters.StringTodo, types.StringType, itrial.ITodo),
(adapters.TodoBase, types.NoneType, itrial.ITodo),
(remote.JellyableTestMethod, itrial.ITestMethod, jelly.IJellyable)]:

        components.registerAdapter(a, o, i)

_setUpAdapters()

