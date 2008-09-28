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

from twisted.python.versions import getVersionString
from twisted.python.reflect import fullyQualifiedName
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
        fullyQualifiedName(callableThing), getVersionString(version))



def deprecated(version):
    """
    Return a decorator that marks callables as deprecated.

    @type version: L{twisted.python.versions.Version}
    @param version: The version in which the callable will be marked as
        having been deprecated.  The decorated function will be annotated
        with this version, having it set as its C{deprecatedVersion}
        attribute.
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



class _Release(object):
    """
    Represents the release of a particular version of a project on a particular
    day.

    @ivar version: The L{Version} of this release.
    @ivar date: The day on which this release happened.
    """
    def __init__(self, version, date):
        self.version = version
        self.date = date



class _DeprecationPolicy(object):
    """
    Implementation of a time and release based deprecation policy.

    This class implements a policy where a new deprecation emits a
    L{PendingDeprecationWarning} for a configured minimum number of releases
    and a configured minimum amount of time.  After both these minimums have
    been exceeded, the warning class changes to L{DeprecationWarning}.

    @ivar minimumPendingPeriod: The minimum amount of time which must elapse
        between the first release which includes a deprecation and the first
        release in which the type will be L{DeprecationWarning} instead of
        L{PendingDeprecationWarning}.
    @type minimumPendingPeriod: L{timedelta}

    @ivar minimumPendingReleases: The minimum number of releases for which a
        deprecation must use L{PendingDeprecationWarning} before it will use
        L{DeprecationWarning}.
    @type minimumPendingReleases: C{int}

    @ivar allReleases: A C{list} of L{_Release} instances giving information
        about all releases of the project.  Releases older than any deprecation
        need not be included, but all releases after the first which includes a
        deprecation must be present.
    """
    def __init__(self, minimumPendingPeriod, minimumPendingReleases,
                 allReleases):
        if not allReleases:
            raise ValueError("At least one release is required.")
        lastRelease = allReleases[0]
        for nextRelease in allReleases[1:]:
            if nextRelease.date < lastRelease.date:
                raise ValueError(
                    "allReleases must be in date-ascending order.")
            if nextRelease.version < lastRelease.version:
                raise ValueError(
                    "allReleases must be in version-ascending order.")
            lastRelease = nextRelease

        self.minimumPendingPeriod = minimumPendingPeriod
        self.minimumPendingReleases = minimumPendingReleases
        self.allReleases = allReleases


    def releaseAfter(self, release):
        if release is self.allReleases[-1]:
            return None
        return self.allReleases[self.allReleases.index(release) + 1]


    def deprecationType(self, release):
        """
        Return the deprecation warning class which should be used to warn about
        the use of an API deprecated in the first release following C{release}.

        @param release: The last release in which the deprecation was not
            present.
        @type release: L{_Release}
        """
        # Find the first release in which the deprecation actually existed and
        # compute everything else relative to that.
        release = self.releaseAfter(release)

        # If no releases follow the indicated release, it's definitely still
        # pending.
        if release is None:
            return PendingDeprecationWarning


        # If the current release is less than self.minimumPendingPeriod after
        # the given release, the deprecation is still pending.
        if self.allReleases[-1].date < release.date + self.minimumPendingPeriod:
            return PendingDeprecationWarning

        # If the current release is less than self.minimumPendingReleases after
        # the given release, the deprecation is still pending.
        if (len(self.allReleases) - 1) < self.allReleases.index(release) + self.minimumPendingReleases:
            return PendingDeprecationWarning

        # Nothing indicates this release should still be pending, so it's not.
        return DeprecationWarning


    def decorator(self, release):
        """
        Return a decorator which will emit a warning indicating that the
        decorated function was deprecated in the release which followed
        C{release}.
        """
        def decorator(f):
            message = getDeprecationWarningString(f, release.version)
            def decorated(*args, **kw):
                self.warn(release, message, 3)
                return f(*args, **kw)
            return mergeFunctionMetadata(f, decorated)
        return decorator


    def warn(self, release, message, stacklevel=2):
        """
        Emit a deprecation warning of the appropriate type for a deprecation
        which was added in the release following C{release}.
        """
        getWarningMethod()(message, category=self.deprecationType(release),
                           stacklevel=stacklevel)

