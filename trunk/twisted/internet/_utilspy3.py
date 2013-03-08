# -*- test-case-name: twisted.internet.test.test_utilspy3 -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Utility methods, ported to Python 3.
"""

from __future__ import division, absolute_import

import sys, warnings
from functools import wraps

from twisted.python.compat import reraise
from twisted.internet import defer

def _resetWarningFilters(passthrough, addedFilters):
    for f in addedFilters:
        try:
            warnings.filters.remove(f)
        except ValueError:
            pass
    return passthrough


def runWithWarningsSuppressed(suppressedWarnings, f, *a, **kw):
    """Run the function C{f}, but with some warnings suppressed.

    @param suppressedWarnings: A list of arguments to pass to filterwarnings.
                               Must be a sequence of 2-tuples (args, kwargs).
    @param f: A callable, followed by its arguments and keyword arguments
    """
    for args, kwargs in suppressedWarnings:
        warnings.filterwarnings(*args, **kwargs)
    addedFilters = warnings.filters[:len(suppressedWarnings)]
    try:
        result = f(*a, **kw)
    except:
        exc_info = sys.exc_info()
        _resetWarningFilters(None, addedFilters)
        reraise(exc_info[1], exc_info[2])
    else:
        if isinstance(result, defer.Deferred):
            result.addBoth(_resetWarningFilters, addedFilters)
        else:
            _resetWarningFilters(None, addedFilters)
        return result


def suppressWarnings(f, *suppressedWarnings):
    """
    Wrap C{f} in a callable which suppresses the indicated warnings before
    invoking C{f} and unsuppresses them afterwards.  If f returns a Deferred,
    warnings will remain suppressed until the Deferred fires.
    """
    @wraps(f)
    def warningSuppressingWrapper(*a, **kw):
        return runWithWarningsSuppressed(suppressedWarnings, f, *a, **kw)
    return warningSuppressingWrapper
