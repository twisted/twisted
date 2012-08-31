# -*- test-case-name: twisted.python.test.test_deprecatepy3 -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
The parts of L{twisted.python.deprecate} which have been ported to Python 3.
"""

from __future__ import division, absolute_import

import inspect
from functools import wraps
from warnings import warn

from twisted.python.versions import getVersionString

DEPRECATION_WARNING_FORMAT = '%(fqpn)s was deprecated in %(version)s'

# Notionally, part of twisted.python.reflect, but defining it there causes a
# cyclic dependency between this module and that module.  Define it here,
# instead, and let reflect import it to re-expose to the public.
def _fullyQualifiedName(obj):
    """
    Return the fully qualified name of a module, class, method or function.
    Classes and functions need to be module level ones to be correctly
    qualified.

    @rtype: C{str}.
    """
    try:
        name = obj.__qualname__
    except AttributeError:
        name = obj.__name__

    if inspect.isclass(obj) or inspect.isfunction(obj):
        moduleName = obj.__module__
        return "%s.%s" % (moduleName, name)
    elif inspect.ismethod(obj):
        try:
            cls = obj.im_class
        except AttributeError:
            # Python 3 eliminates im_class, substitutes __module__ and
            # __qualname__ to provide similar information.
            return "%s.%s" % (obj.__module__, obj.__qualname__)
        else:
            className = _fullyQualifiedName(cls)
            return "%s.%s" % (className, name)
    return name
# Try to keep it looking like something in twisted.python.reflect.
_fullyQualifiedName.__module__ = 'twisted.python.reflect'
_fullyQualifiedName.__name__ = 'fullyQualifiedName'
_fullyQualifiedName.__qualname__ = 'fullyQualifiedName'


def _getReplacementString(replacement):
    """
    Surround a replacement for a deprecated API with some polite text exhorting
    the user to consider it as an alternative.

    @type replacement: C{str} or callable

    @return: a string like "please use twisted.python.modules.getModule
        instead".
    """
    if callable(replacement):
        replacement = _fullyQualifiedName(replacement)
    return "please use %s instead" % (replacement,)



def _getDeprecationDocstring(version, replacement=None):
    """
    Generate an addition to a deprecated object's docstring that explains its
    deprecation.

    @param version: the version it was deprecated.
    @type version: L{Version}

    @param replacement: The replacement, if specified.
    @type replacement: C{str} or callable

    @return: a string like "Deprecated in Twisted 27.2.0; please use
        twisted.timestream.tachyon.flux instead."
    """
    doc = "Deprecated in %s" % (getVersionString(version),)
    if replacement:
        doc = "%s; %s" % (doc, _getReplacementString(replacement))
    return doc + "."



def _getDeprecationWarningString(fqpn, version, format=None, replacement=None):
    """
    Return a string indicating that the Python name was deprecated in the given
    version.

    @param fqpn: Fully qualified Python name of the thing being deprecated
    @type fqpn: C{str}

    @param version: Version that C{fqpn} was deprecated in.
    @type version: L{twisted.python.versions.Version}

    @param format: A user-provided format to interpolate warning values into, or
        L{DEPRECATION_WARNING_FORMAT
        <twisted.python.deprecate.DEPRECATION_WARNING_FORMAT>} if C{None} is
        given.
    @type format: C{str}

    @param replacement: what should be used in place of C{fqpn}. Either pass in
        a string, which will be inserted into the warning message, or a
        callable, which will be expanded to its full import path.
    @type replacement: C{str} or callable

    @return: A textual description of the deprecation
    @rtype: C{str}
    """
    if format is None:
        format = DEPRECATION_WARNING_FORMAT
    warningString = format % {
        'fqpn': fqpn,
        'version': getVersionString(version)}
    if replacement:
        warningString = "%s; %s" % (
            warningString, _getReplacementString(replacement))
    return warningString



def getDeprecationWarningString(callableThing, version, format=None,
                                replacement=None):
    """
    Return a string indicating that the callable was deprecated in the given
    version.

    @type callableThing: C{callable}
    @param callableThing: Callable object to be deprecated

    @type version: L{twisted.python.versions.Version}
    @param version: Version that C{callableThing} was deprecated in

    @type format: C{str}
    @param format: A user-provided format to interpolate warning values into,
        or L{DEPRECATION_WARNING_FORMAT
        <twisted.python.deprecate.DEPRECATION_WARNING_FORMAT>} if C{None} is
        given

    @param callableThing: A callable to be deprecated.

    @param version: The L{twisted.python.versions.Version} that the callable
        was deprecated in.

    @param replacement: what should be used in place of the callable. Either
        pass in a string, which will be inserted into the warning message,
        or a callable, which will be expanded to its full import path.
    @type replacement: C{str} or callable

    @return: A string describing the deprecation.
    @rtype: C{str}
    """
    return _getDeprecationWarningString(
        _fullyQualifiedName(callableThing), version, format, replacement)



def _appendToDocstring(thingWithDoc, textToAppend):
    """
    Append the given text to the docstring of C{thingWithDoc}.

    If C{thingWithDoc} has no docstring, then the text just replaces the
    docstring. If it has a single-line docstring then it appends a blank line
    and the message text. If it has a multi-line docstring, then in appends a
    blank line a the message text, and also does the indentation correctly.
    """
    if thingWithDoc.__doc__:
        docstringLines = thingWithDoc.__doc__.splitlines()
    else:
        docstringLines = []

    if len(docstringLines) == 0:
        docstringLines.append(textToAppend)
    elif len(docstringLines) == 1:
        docstringLines.extend(['', textToAppend, ''])
    else:
        spaces = docstringLines.pop()
        docstringLines.extend(['',
                               spaces + textToAppend,
                               spaces])
    thingWithDoc.__doc__ = '\n'.join(docstringLines)



def deprecated(version, replacement=None):
    """
    Return a decorator that marks callables as deprecated.

    @type version: L{twisted.python.versions.Version}
    @param version: The version in which the callable will be marked as
        having been deprecated.  The decorated function will be annotated
        with this version, having it set as its C{deprecatedVersion}
        attribute.

    @param version: the version that the callable was deprecated in.
    @type version: L{twisted.python.versions.Version}

    @param replacement: what should be used in place of the callable. Either
        pass in a string, which will be inserted into the warning message,
        or a callable, which will be expanded to its full import path.
    @type replacement: C{str} or callable
    """
    def deprecationDecorator(function):
        """
        Decorator that marks C{function} as deprecated.
        """
        warningString = getDeprecationWarningString(
            function, version, None, replacement)

        @wraps(function)
        def deprecatedFunction(*args, **kwargs):
            warn(
                warningString,
                DeprecationWarning,
                stacklevel=2)
            return function(*args, **kwargs)

        _appendToDocstring(deprecatedFunction,
                           _getDeprecationDocstring(version, replacement))
        deprecatedFunction.deprecatedVersion = version
        return deprecatedFunction

    return deprecationDecorator
