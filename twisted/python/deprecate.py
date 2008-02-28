# -*- test-case-name: twisted.python.test.test_deprecate -*-

# Copyright (c) 2008 Twisted Matrix Laboratories.
# See LICENSE for details.


"""
Deprecation framework for Twisted.

To mark a method or function as being deprecated do this::

    def badAPI(self, first, second):
        '''
        Docstring for badAPI.
        '''
        ...
    badAPI = deprecate(Version("Twisted", 8, 0, 0))(badAPI)

The newly-decorated badAPI will issue a warning when called. It will also have
a deprecation notice appended to its docstring.

See also L{Version}.
"""


__all__ = [
    'deprecated',
    'getDeprecationWarningString',
    'getWarningMethod',
    'setWarningMethod',
    ]


from warnings import warn

from twisted.python.versions import getVersionString, Version
from twisted.python.reflect import qual
from twisted.python.util import mergeFunctionMetadata


def getWarningMethod():
    """
    Return the warning method currently used to record deprecation warnings.
    """
    return warn



def setWarningMethod(newMethod):
    """
    Set the warning method to use to record deprecation warnings.

    The callable should take message, category and stacklevel. The return
    value is ignored.
    """
    global warn
    warn = newMethod



def _getDeprecationDocstring(version):
    return "Deprecated in %s." % getVersionString(version)



def getDeprecationWarningString(callableThing, version):
    """
    Return a string indicating that the callable was deprecated in the given
    version.

    @param callableThing: A callable to be deprecated.
    @param version: The L{twisted.python.versions.Version} that the callable
        was deprecated in.
    @return: A string describing the deprecation.
    """
    return "%s was deprecated in %s" % (
        qual(callableThing), getVersionString(version))



def deprecated(version):
    """
    Return a decorator that marks callables as deprecated.
    """

    def deprecationDecorator(function):
        """
        Decorator that marks C{function} as deprecated.
        """

        warningString = getDeprecationWarningString(function, version)

        def deprecatedFunction(*args, **kwargs):
            warn(
                warningString,
                DeprecationWarning,
                stacklevel=2)
            return function(*args, **kwargs)

        deprecatedFunction = mergeFunctionMetadata(
            function, deprecatedFunction)
        _appendToDocstring(deprecatedFunction,
                           _getDeprecationDocstring(version))
        deprecatedFunction.deprecatedVersion = version
        return deprecatedFunction

    return deprecationDecorator



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
