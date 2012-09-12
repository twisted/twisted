# -*- test-case-name: twisted.trial.test -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
The parts of L{twisted.trial.util} which have been ported to Python 3.
"""

from __future__ import division, absolute_import

from twisted.python.failure import Failure


_DEFAULT = object()
def acquireAttribute(objects, attr, default=_DEFAULT):
    """Go through the list 'objects' sequentially until we find one which has
    attribute 'attr', then return the value of that attribute.  If not found,
    return 'default' if set, otherwise, raise AttributeError. """
    for obj in objects:
        if hasattr(obj, attr):
            return getattr(obj, attr)
    if default is not _DEFAULT:
        return default
    raise AttributeError('attribute %r not found in %r' % (attr, objects))


def excInfoOrFailureToExcInfo(err):
    """
    Coerce a Failure to an _exc_info, if err is a Failure.

    @param err: Either a tuple such as returned by L{sys.exc_info} or a
        L{Failure} object.
    @return: A tuple like the one returned by L{sys.exc_info}. e.g.
        C{exception_type, exception_object, traceback_object}.
    """
    if isinstance(err, Failure):
        # Unwrap the Failure into a exc_info tuple.
        err = (err.type, err.value, err.getTracebackObject())
    return err


def suppress(action='ignore', **kwarg):
    """
    Sets up the .suppress tuple properly, pass options to this method as you
    would the stdlib warnings.filterwarnings()

    So, to use this with a .suppress magic attribute you would do the
    following:

      >>> from twisted.trial import unittest, util
      >>> import warnings
      >>>
      >>> class TestFoo(unittest.TestCase):
      ...     def testFooBar(self):
      ...         warnings.warn("i am deprecated", DeprecationWarning)
      ...     testFooBar.suppress = [util.suppress(message='i am deprecated')]
      ...
      >>>

    Note that as with the todo and timeout attributes: the module level
    attribute acts as a default for the class attribute which acts as a default
    for the method attribute. The suppress attribute can be overridden at any
    level by specifying C{.suppress = []}
    """
    return ((action,), kwarg)
