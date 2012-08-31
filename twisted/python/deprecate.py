# -*- test-case-name: twisted.python.test.test_deprecate -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Deprecation framework for Twisted.

To mark a method or function as being deprecated do this::

    from twisted.python.versions import Version
    from twisted.python.deprecate import deprecated

    @deprecated(Version("Twisted", 8, 0, 0))
    def badAPI(self, first, second):
        '''
        Docstring for badAPI.
        '''
        ...

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
from warnings import warn, warn_explicit
from dis import findlinestarts

from twisted.python._deprecatepy3 import (
    DEPRECATION_WARNING_FORMAT, deprecated, getDeprecationWarningString,
    _getDeprecationWarningString)


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



class _InternalState(object):
    """
    An L{_InternalState} is a helper object for a L{_ModuleProxy}, so that it
    can easily access its own attributes, bypassing its logic for delegating to
    another object that it's proxying for.

    @ivar proxy: a L{ModuleProxy}
    """
    def __init__(self, proxy):
        object.__setattr__(self, 'proxy', proxy)


    def __getattribute__(self, name):
        return object.__getattribute__(object.__getattribute__(self, 'proxy'),
                                       name)


    def __setattr__(self, name, value):
        return object.__setattr__(object.__getattribute__(self, 'proxy'),
                                  name, value)



class _ModuleProxy(object):
    """
    Python module wrapper to hook module-level attribute access.

    Access to deprecated attributes first checks
    L{_ModuleProxy._deprecatedAttributes}, if the attribute does not appear
    there then access falls through to L{_ModuleProxy._module}, the wrapped
    module object.

    @ivar _module: Module on which to hook attribute access.
    @type _module: C{module}

    @ivar _deprecatedAttributes: Mapping of attribute names to objects that
        retrieve the module attribute's original value.
    @type _deprecatedAttributes: C{dict} mapping C{str} to
        L{_DeprecatedAttribute}

    @ivar _lastWasPath: Heuristic guess as to whether warnings about this
        package should be ignored for the next call.  If the last attribute
        access of this module was a C{getattr} of C{__path__}, we will assume
        that it was the import system doing it and we won't emit a warning for
        the next access, even if it is to a deprecated attribute.  The CPython
        import system always tries to access C{__path__}, then the attribute
        itself, then the attribute itself again, in both successful and failed
        cases.
    @type _lastWasPath: C{bool}
    """
    def __init__(self, module):
        state = _InternalState(self)
        state._module = module
        state._deprecatedAttributes = {}
        state._lastWasPath = False


    def __repr__(self):
        """
        Get a string containing the type of the module proxy and a
        representation of the wrapped module object.
        """
        state = _InternalState(self)
        return '<%s module=%r>' % (type(self).__name__, state._module)


    def __setattr__(self, name, value):
        """
        Set an attribute on the wrapped module object.
        """
        state = _InternalState(self)
        state._lastWasPath = False
        setattr(state._module, name, value)


    def __getattribute__(self, name):
        """
        Get an attribute from the module object, possibly emitting a warning.

        If the specified name has been deprecated, then a warning is issued.
        (Unless certain obscure conditions are met; see
        L{_ModuleProxy._lastWasPath} for more information about what might quash
        such a warning.)
        """
        state = _InternalState(self)
        if state._lastWasPath:
            deprecatedAttribute = None
        else:
            deprecatedAttribute = state._deprecatedAttributes.get(name)

        if deprecatedAttribute is not None:
            # If we have a _DeprecatedAttribute object from the earlier lookup,
            # allow it to issue the warning.
            value = deprecatedAttribute.get()
        else:
            # Otherwise, just retrieve the underlying value directly; it's not
            # deprecated, there's no warning to issue.
            value = getattr(state._module, name)
        if name == '__path__':
            state._lastWasPath = True
        else:
            state._lastWasPath = False
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
        # This might fail if the deprecated thing is a module inside a package.
        # In that case, don't emit the warning this time.  The import system
        # will come back again when it's not an AttributeError and we can emit
        # the warning then.
        result = getattr(self.module, self.__name__)
        message = _getDeprecationWarningString(self.fqpn, self.version,
            DEPRECATION_WARNING_FORMAT + ': ' + self.message)
        warn(message, DeprecationWarning, stacklevel=3)
        return result



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


def warnAboutFunction(offender, warningString):
    """
    Issue a warning string, identifying C{offender} as the responsible code.

    This function is used to deprecate some behavior of a function.  It differs
    from L{warnings.warn} in that it is not limited to deprecating the behavior
    of a function currently on the call stack.

    @param function: The function that is being deprecated.

    @param warningString: The string that should be emitted by this warning.
    @type warningString: C{str}

    @since: 11.0
    """
    # inspect.getmodule() is attractive, but somewhat
    # broken in Python < 2.6.  See Python bug 4845.
    offenderModule = sys.modules[offender.__module__]
    filename = inspect.getabsfile(offenderModule)
    lineStarts = list(findlinestarts(offender.func_code))
    lastLineNo = lineStarts[-1][1]
    globals = offender.func_globals

    kwargs = dict(
        category=DeprecationWarning,
        filename=filename,
        lineno=lastLineNo,
        module=offenderModule.__name__,
        registry=globals.setdefault("__warningregistry__", {}),
        module_globals=None)

    if sys.version_info[:2] < (2, 5):
        kwargs.pop('module_globals')

    warn_explicit(warningString, **kwargs)
