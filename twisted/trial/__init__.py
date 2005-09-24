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

def _setUpAdapters():
    from twisted.spread import jelly
    # sibling imports
    import itrial, remote
    components.registerAdapter(remote.JellyableTestMethod,
                               itrial.ITestMethod,
                               jelly.IJellyable)


_setUpAdapters()

