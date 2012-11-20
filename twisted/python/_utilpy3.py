# -*- test-case-name: twisted.python.test.test_utilpy3 -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
The subset of L{twisted.python.util} which has been ported to Python 3.
"""

from __future__ import division, absolute_import

import sys, errno, warnings

from twisted.python.compat import unicode

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


def runWithWarningsSuppressed(suppressedWarnings, f, *args, **kwargs):
    """
    Run C{f(*args, **kwargs)}, but with some warnings suppressed.

    Unlike L{twisted.internet.utils.runWithWarningsSuppressed}, it has no
    special support for L{twisted.internet.defer.Deferred}.

    @param suppressedWarnings: A list of arguments to pass to filterwarnings.
        Must be a sequence of 2-tuples (args, kwargs).

    @param f: A callable.

    @param args: Arguments for C{f}.

    @param kwargs: Keyword arguments for C{f}

    @return: The result of C{f(*args, **kwargs)}.
    """
    with warnings.catch_warnings():
        for a, kw in suppressedWarnings:
            warnings.filterwarnings(*a, **kw)
        return f(*args, **kwargs)



class FancyStrMixin:
    """
    Mixin providing a flexible implementation of C{__str__}.

    C{__str__} output will begin with the name of the class, or the contents
    of the attribute C{fancybasename} if it is set.

    The body of C{__str__} can be controlled by overriding C{showAttributes} in
    a subclass.  Set C{showAttributes} to a sequence of strings naming
    attributes, or sequences of C{(attributeName, callable)}, or sequences of
    C{(attributeName, displayName, formatCharacter)}. In the second case, the
    callable is passed the value of the attribute and its return value used in
    the output of C{__str__}.  In the final case, the attribute is looked up
    using C{attributeName}, but the output uses C{displayName} instead, and
    renders the value of the attribute using C{formatCharacter}, e.g. C{"%.3f"}
    might be used for a float.
    """
    # Override in subclasses:
    showAttributes = ()


    def __str__(self):
        r = ['<', (hasattr(self, 'fancybasename') and self.fancybasename)
             or self.__class__.__name__]
        for attr in self.showAttributes:
            if isinstance(attr, str):
                r.append(' %s=%r' % (attr, getattr(self, attr)))
            elif len(attr) == 2:
                r.append((' %s=' % (attr[0],)) + attr[1](getattr(self, attr[0])))
            else:
                r.append((' %s=' + attr[2]) % (attr[1], getattr(self, attr[0])))
        r.append('>')
        return ''.join(r)

    __repr__ = __str__



def nameToLabel(mname):
    """
    Convert a string like a variable name into a slightly more human-friendly
    string with spaces and capitalized letters.

    @type mname: C{str}
    @param mname: The name to convert to a label.  This must be a string
    which could be used as a Python identifier.  Strings which do not take
    this form will result in unpredictable behavior.

    @rtype: C{str}
    """
    labelList = []
    word = ''
    lastWasUpper = False
    for letter in mname:
        if letter.isupper() == lastWasUpper:
            # Continuing a word.
            word += letter
        else:
            # breaking a word OR beginning a word
            if lastWasUpper:
                # could be either
                if len(word) == 1:
                    # keep going
                    word += letter
                else:
                    # acronym
                    # we're processing the lowercase letter after the acronym-then-capital
                    lastWord = word[:-1]
                    firstLetter = word[-1]
                    labelList.append(lastWord)
                    word = firstLetter + letter
            else:
                # definitely breaking: lower to upper
                labelList.append(word)
                word = letter
        lastWasUpper = letter.isupper()
    if labelList:
        labelList[0] = labelList[0].capitalize()
    else:
        return mname.capitalize()
    labelList.append(word)
    return ' '.join(labelList)



class InsensitiveDict:
    """Dictionary, that has case-insensitive keys.

    Normally keys are retained in their original form when queried with
    .keys() or .items().  If initialized with preserveCase=0, keys are both
    looked up in lowercase and returned in lowercase by .keys() and .items().
    """
    """
    Modified recipe at
    http://aspn.activestate.com/ASPN/Cookbook/Python/Recipe/66315 originally
    contributed by Sami Hangaslammi.
    """

    def __init__(self, dict=None, preserve=1):
        """Create an empty dictionary, or update from 'dict'."""
        self.data = {}
        self.preserve=preserve
        if dict:
            self.update(dict)

    def __delitem__(self, key):
        k=self._lowerOrReturn(key)
        del self.data[k]

    def _lowerOrReturn(self, key):
        if isinstance(key, bytes) or isinstance(key, unicode):
            return key.lower()
        else:
            return key

    def __getitem__(self, key):
        """Retrieve the value associated with 'key' (in any case)."""
        k = self._lowerOrReturn(key)
        return self.data[k][1]

    def __setitem__(self, key, value):
        """Associate 'value' with 'key'. If 'key' already exists, but
        in different case, it will be replaced."""
        k = self._lowerOrReturn(key)
        self.data[k] = (key, value)

    def has_key(self, key):
        """Case insensitive test whether 'key' exists."""
        k = self._lowerOrReturn(key)
        return k in self.data

    __contains__=has_key

    def _doPreserve(self, key):
        if not self.preserve and (isinstance(key, bytes)
                                  or isinstance(key, unicode)):
            return key.lower()
        else:
            return key

    def keys(self):
        """List of keys in their original case."""
        return list(self.iterkeys())

    def values(self):
        """List of values."""
        return list(self.itervalues())

    def items(self):
        """List of (key,value) pairs."""
        return list(self.iteritems())

    def get(self, key, default=None):
        """Retrieve value associated with 'key' or return default value
        if 'key' doesn't exist."""
        try:
            return self[key]
        except KeyError:
            return default

    def setdefault(self, key, default):
        """If 'key' doesn't exists, associate it with the 'default' value.
        Return value associated with 'key'."""
        if not self.has_key(key):
            self[key] = default
        return self[key]

    def update(self, dict):
        """Copy (key,value) pairs from 'dict'."""
        for k,v in dict.items():
            self[k] = v

    def __repr__(self):
        """String representation of the dictionary."""
        items = ", ".join([("%r: %r" % (k,v)) for k,v in self.items()])
        return "InsensitiveDict({%s})" % items

    def iterkeys(self):
        for v in self.data.values():
            yield self._doPreserve(v[0])

    def itervalues(self):
        for v in self.data.values():
            yield v[1]

    def iteritems(self):
        for (k, v) in self.data.values():
            yield self._doPreserve(k), v

    def popitem(self):
        i=self.items()[0]
        del self[i[0]]
        return i

    def clear(self):
        for k in self.keys():
            del self[k]

    def copy(self):
        return InsensitiveDict(self, self.preserve)

    def __len__(self):
        return len(self.data)

    def __eq__(self, other):
        for k,v in self.items():
            if not (k in other) or not (other[k]==v):
                return 0
        return len(self)==len(other)
