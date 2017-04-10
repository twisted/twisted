# -*- test-case-name: twisted.python.test.test_deprecate -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Deprecation framework for Twisted.

To mark a method, function, or class as being deprecated do this::

    from incremental import Version
    from twisted.python.deprecate import deprecated

    @deprecated(Version("Twisted", 8, 0, 0))
    def badAPI(self, first, second):
        '''
        Docstring for badAPI.
        '''
        ...

    @deprecated(Version("Twisted", 16, 0, 0))
    class BadClass(object):
        '''
        Docstring for BadClass.
        '''

The newly-decorated badAPI will issue a warning when called, and BadClass will
issue a warning when instantiated. Both will also have  a deprecation notice
appended to their docstring.

To deprecate properties you can use::

    from incremental import Version
    from twisted.python.deprecate import deprecatedProperty

    class OtherwiseUndeprecatedClass(object):

        @deprecatedProperty(Version('Twisted', 16, 0, 0))
        def badProperty(self):
            '''
            Docstring for badProperty.
            '''

        @badProperty.setter
        def badProperty(self, value):
            '''
            Setter sill also raise the deprecation warning.
            '''


To mark module-level attributes as being deprecated you can use::

    badAttribute = "someValue"

    ...

    deprecatedModuleAttribute(
        Version("Twisted", 8, 0, 0),
        "Use goodAttribute instead.",
        "your.full.module.name",
        "badAttribute")

The deprecated attributes will issue a warning whenever they are accessed. If
the attributes being deprecated are in the same module as the
L{deprecatedModuleAttribute} call is being made from, the C{__name__} global
can be used as the C{moduleName} parameter.

See also L{incremental.Version}.

@type DEPRECATION_WARNING_FORMAT: C{str}
@var DEPRECATION_WARNING_FORMAT: The default deprecation warning string format
    to use when one is not provided by the user.
"""

from __future__ import division, absolute_import

from eventually import (
    deprecated,
    deprecatedProperty,
    getDeprecationWarningString,
    deprecatedModuleAttribute,
    DEPRECATION_WARNING_FORMAT,
    warnAboutFunction,
    getWarningMethod,
    setWarningMethod
)
from eventually._deprecate import _mutuallyExclusiveArguments

__all__ = [
    'deprecated',
    'deprecatedProperty',
    'getWarningMethod',
    'setWarningMethod',
    'deprecatedModuleAttribute',
    'getDeprecationWarningString',
]
