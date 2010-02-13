# -*- test-case-name: twisted.python.test.test_deprecate -*-
# Copyright (c) 2008-2010 Twisted Matrix Laboratories.
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

See also L{Version}.

@type DEPRECATION_WARNING_FORMAT: C{str}
@var DEPRECATION_WARNING_FORMAT: The default deprecation warning string format
    to use when one is not provided by the user.
"""


__all__ = [
    'deprecated',
    'getDeprecationWarningString',
    'getWarningMethod',
    'setWarningMethod',
    'deprecatedModuleAttribute',
    ]


import sys, inspect
from warnings import warn

from twisted.python.versions import getVersionString
from twisted.python.util import mergeFunctionMetadata



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
    name = obj.__name__
    if inspect.isclass(obj) or inspect.isfunction(obj):
        moduleName = obj.__module__
        return "%s.%s" % (moduleName, name)
    elif inspect.ismethod(obj):
        className = _fullyQualifiedName(obj.im_class)
        return "%s.%s" % (className, name)
    return name
# Try to keep it looking like something in twisted.python.reflect.
_fullyQualifiedName.__module__ = 'twisted.python.reflect'
_fullyQualifiedName.__name__ = 'fullyQualifiedName'


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



def _getDeprecationWarningString(fqpn, version, format=None):
    """
    Return a string indicating that the Python name was deprecated in the given
    version.

    @type fqpn: C{str}
    @param fqpn: Fully qualified Python name of the thing being deprecated

    @type version: L{twisted.python.versions.Version}
    @param version: Version that C{fqpn} was deprecated in

    @type format: C{str}
    @param format: A user-provided format to interpolate warning values into,
        or L{DEPRECATION_WARNING_FORMAT} if C{None} is given

    @rtype: C{str}
    @return: A textual description of the deprecation
    """
    if format is None:
        format = DEPRECATION_WARNING_FORMAT
    return format % {
        'fqpn': fqpn,
        'version': getVersionString(version)}



def getDeprecationWarningString(callableThing, version, format=None):
    """
    Return a string indicating that the callable was deprecated in the given
    version.

    @type callableThing: C{callable}
    @param callableThing: Callable object to be deprecated

    @type version: L{twisted.python.versions.Version}
    @param version: Version that C{fqpn} was deprecated in

    @type format: C{str}
    @param format: A user-provided format to interpolate warning values into,
        or L{DEPRECATION_WARNING_FORMAT} if C{None} is given

    @rtype: C{str}
    @return: A textual description of the deprecation
    """
    return _getDeprecationWarningString(
        _fullyQualifiedName(callableThing), version, format)



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



class _ModuleProxy(object):
    """
    Python module wrapper to hook module-level attribute access.

    Access to deprecated attributes first checks L{_deprecatedAttributes}, if
    the attribute does not appear there then access falls through to L{_module},
    the wrapped module object.

    @type _module: C{module}
    @ivar _module: Module on which to hook attribute access.

    @type _deprecatedAttributes: C{dict} mapping C{str} to
        L{_DeprecatedAttribute}
    @ivar _deprecatedAttributes: Mapping of attribute names to objects that
        retrieve the module attribute's original value.
    """
    def __init__(self, module):
        object.__setattr__(self, '_module', module)
        object.__setattr__(self, '_deprecatedAttributes', {})


    def __repr__(self):
        """
        Get a string containing the type of the module proxy and a
        representation of the wrapped module object.
        """
        _module = object.__getattribute__(self, '_module')
        return '<%s module=%r>' % (
            type(self).__name__,
            _module)


    def __setattr__(self, name, value):
        """
        Set an attribute on the wrapped module object.
        """
        _module = object.__getattribute__(self, '_module')
        setattr(_module, name, value)


    def __getattribute__(self, name):
        """
        Get an attribute on the wrapped module object.

        If the specified name has been deprecated then a warning is issued.
        """
        _module = object.__getattribute__(self, '_module')
        _deprecatedAttributes = object.__getattribute__(
            self, '_deprecatedAttributes')

        getter = _deprecatedAttributes.get(name)
        if getter is not None:
            value = getter.get()
        else:
            value = getattr(_module, name)
        return value



class _DeprecatedAttribute(object):
    """
    Wrapper for deprecated attributes.

    This is intended to be used by L{_ModuleProxy}. Calling
    L{_DeprecatedAttribute.get} will issue a warning and retrieve the
    underlying attribute's value.

    @type module: C{module}
    @ivar module: The original module instance containing this attribute

    @type fqpn: C{str}
    @ivar fqpn: Fully qualified Python name for the deprecated attribute

    @type version: L{twisted.python.versions.Version}
    @ivar version: Version that the attribute was deprecated in

    @type message: C{str}
    @ivar message: Deprecation message
    """
    def __init__(self, module, name, version, message):
        """
        Initialise a deprecated name wrapper.
        """
        self.module = module
        self.__name__ = name
        self.fqpn = module.__name__ + '.' + name
        self.version = version
        self.message = message


    def get(self):
        """
        Get the underlying attribute value and issue a deprecation warning.
        """
        message = _getDeprecationWarningString(self.fqpn, self.version,
            DEPRECATION_WARNING_FORMAT + ': ' + self.message)
        warn(message, DeprecationWarning, stacklevel=3)
        return getattr(self.module, self.__name__)



def _deprecateAttribute(proxy, name, version, message):
    """
    Mark a module-level attribute as being deprecated.

    @type proxy: L{_ModuleProxy}
    @param proxy: The module proxy instance proxying the deprecated attributes

    @type name: C{str}
    @param name: Attribute name

    @type version: L{twisted.python.versions.Version}
    @param version: Version that the attribute was deprecated in

    @type message: C{str}
    @param message: Deprecation message
    """
    _module = object.__getattribute__(proxy, '_module')
    attr = _DeprecatedAttribute(_module, name, version, message)
    # Add a deprecated attribute marker for this module's attribute. When this
    # attribute is accessed via _ModuleProxy a warning is emitted.
    _deprecatedAttributes = object.__getattribute__(
        proxy, '_deprecatedAttributes')
    _deprecatedAttributes[name] = attr



def deprecatedModuleAttribute(version, message, moduleName, name):
    """
    Declare a module-level attribute as being deprecated.

    @type version: L{twisted.python.versions.Version}
    @param version: Version that the attribute was deprecated in

    @type message: C{str}
    @param message: Deprecation message

    @type moduleName: C{str}
    @param moduleName: Fully-qualified Python name of the module containing
        the deprecated attribute; if called from the same module as the
        attributes are being deprecated in, using the C{__name__} global can
        be helpful

    @type name: C{str}
    @param name: Attribute name to deprecate
    """
    module = sys.modules[moduleName]
    if not isinstance(module, _ModuleProxy):
        module = _ModuleProxy(module)
        sys.modules[moduleName] = module

    _deprecateAttribute(module, name, version, message)
