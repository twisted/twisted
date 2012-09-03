# -*- test-case-name: twisted.python.test.test_utilpy3 -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
The subset of L{twisted.python.util} which has been ported to Python 3.
"""

from __future__ import division, absolute_import

import sys, errno

class FancyEqMixin:
    """
    Mixin that implements C{__eq__} and C{__ne__}.

    Comparison is done using the list of attributes defined in
    C{compareAttributes}.
    """
    compareAttributes = ()

    def __eq__(self, other):
        if not self.compareAttributes:
            return self is other
        if isinstance(self, other.__class__):
            return (
                [getattr(self, name) for name in self.compareAttributes] ==
                [getattr(other, name) for name in self.compareAttributes])
        return NotImplemented


    def __ne__(self, other):
        result = self.__eq__(other)
        if result is NotImplemented:
            return result
        return not result



_idFunction = id

def setIDFunction(idFunction):
    """
    Change the function used by L{unsignedID} to determine the integer id value
    of an object.  This is largely useful for testing to give L{unsignedID}
    deterministic, easily-controlled behavior.

    @param idFunction: A function with the signature of L{id}.
    @return: The previous function being used by L{unsignedID}.
    """
    global _idFunction
    oldIDFunction = _idFunction
    _idFunction = idFunction
    return oldIDFunction


# A value about twice as large as any Python int, to which negative values
# from id() will be added, moving them into a range which should begin just
# above where positive values from id() leave off.
_HUGEINT = (sys.maxsize + 1) * 2
def unsignedID(obj):
    """
    Return the id of an object as an unsigned number so that its hex
    representation makes sense.

    This is mostly necessary in Python 2.4 which implements L{id} to sometimes
    return a negative value.  Python 2.3 shares this behavior, but also
    implements hex and the %x format specifier to represent negative values as
    though they were positive ones, obscuring the behavior of L{id}.  Python
    2.5's implementation of L{id} always returns positive values.
    """
    rval = _idFunction(obj)
    if rval < 0:
        rval += _HUGEINT
    return rval



def untilConcludes(f, *a, **kw):
    """
    Call C{f} with the given arguments, handling C{EINTR} by retrying.

    @param f: A function to call.

    @param *a: Positional arguments to pass to C{f}.

    @param **kw: Keyword arguments to pass to C{f}.

    @return: Whatever C{f} returns.

    @raise: Whatever C{f} raises, except for C{IOError} or C{OSError} with
        C{errno} set to C{EINTR}.
    """
    while True:
        try:
            return f(*a, **kw)
        except (IOError, OSError) as e:
            if e.args[0] == errno.EINTR:
                continue
            raise
