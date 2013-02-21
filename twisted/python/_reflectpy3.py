# -*- test-case-name: twisted.python.test.test_reflectpy3 -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Reflection APIs which have been ported to Python 3.
"""

from __future__ import division, absolute_import

import types, sys, os, traceback

from twisted.python.compat import reraise, nativeString, NativeStringIO


def prefixedMethodNames(classObj, prefix):
    """
    Given a class object C{classObj}, returns a list of method names that match
    the string C{prefix}.

    @param classObj: A class object from which to collect method names.

    @param prefix: A native string giving a prefix.  Each method with a name
        which begins with this prefix will be returned.
    @type prefix: L{str}

    @return: A list of the names of matching methods of C{classObj} (and base
        classes of C{classObj}).
    @rtype: L{list} of L{str}
    """
    dct = {}
    addMethodNamesToDict(classObj, dct, prefix)
    return list(dct.keys())



def addMethodNamesToDict(classObj, dict, prefix, baseClass=None):
    """
    This goes through C{classObj} (and its bases) and puts method names
    starting with 'prefix' in 'dict' with a value of 1. if baseClass isn't
    None, methods will only be added if classObj is-a baseClass

    If the class in question has the methods 'prefix_methodname' and
    'prefix_methodname2', the resulting dict should look something like:
    {"methodname": 1, "methodname2": 1}.

    @param classObj: A class object from which to collect method names.

    @param dict: A L{dict} which will be updated with the results of the
        accumulation.  Items are added to this dictionary, with method names as
        keys and C{1} as values.
    @type dict: L{dict}

    @param prefix: A native string giving a prefix.  Each method of C{classObj}
        (and base classes of C{classObj}) with a name which begins with this
        prefix will be returned.
    @type prefix: L{str}

    @param baseClass: A class object at which to stop searching upwards for new
        methods.  To collect all method names, do not pass a value for this
        parameter.

    @return: C{None}
    """
    for base in classObj.__bases__:
        addMethodNamesToDict(base, dict, prefix, baseClass)

    if baseClass is None or baseClass in classObj.__bases__:
        for name, method in classObj.__dict__.items():
            optName = name[len(prefix):]
            if ((type(method) is types.FunctionType)
                and (name[:len(prefix)] == prefix)
                and (len(optName))):
                dict[optName] = 1



def prefixedMethods(obj, prefix=''):
    """
    Given an object C{obj}, returns a list of method objects that match the
    string C{prefix}.

    @param obj: An arbitrary object from which to collect methods.

    @param prefix: A native string giving a prefix.  Each method of C{obj} with
        a name which begins with this prefix will be returned.
    @type prefix: L{str}

    @return: A list of the matching method objects.
    @rtype: L{list}
    """
    dct = {}
    accumulateMethods(obj, dct, prefix)
    return list(dct.values())



def accumulateMethods(obj, dict, prefix='', curClass=None):
    """
    Given an object C{obj}, add all methods that begin with C{prefix}.

    @param obj: An arbitrary object to collect methods from.

    @param dict: A L{dict} which will be updated with the results of the
        accumulation.  Items are added to this dictionary, with method names as
        keys and corresponding instance method objects as values.
    @type dict: L{dict}

    @param prefix: A native string giving a prefix.  Each method of C{obj} with
        a name which begins with this prefix will be returned.
    @type prefix: L{str}

    @param curClass: The class in the inheritance hierarchy at which to start
        collecting methods.  Collection proceeds up.  To collect all methods
        from C{obj}, do not pass a value for this parameter.

    @return: C{None}
    """
    if not curClass:
        curClass = obj.__class__
    for base in curClass.__bases__:
        accumulateMethods(obj, dict, prefix, base)

    for name, method in curClass.__dict__.items():
        optName = name[len(prefix):]
        if ((type(method) is types.FunctionType)
            and (name[:len(prefix)] == prefix)
            and (len(optName))):
            dict[optName] = getattr(obj, name)



def namedModule(name):
    """
    Return a module given its name.
    """
    topLevel = __import__(name)
    packages = name.split(".")[1:]
    m = topLevel
    for p in packages:
        m = getattr(m, p)
    return m



def namedObject(name):
    """
    Get a fully named module-global object.
    """
    classSplit = name.split('.')
    module = namedModule('.'.join(classSplit[:-1]))
    return getattr(module, classSplit[-1])

namedClass = namedObject # backwards compat



class _NoModuleFound(Exception):
    """
    No module was found because none exists.
    """



class InvalidName(ValueError):
    """
    The given name is not a dot-separated list of Python objects.
    """



class ModuleNotFound(InvalidName):
    """
    The module associated with the given name doesn't exist and it can't be
    imported.
    """



class ObjectNotFound(InvalidName):
    """
    The object associated with the given name doesn't exist and it can't be
    imported.
    """



def _importAndCheckStack(importName):
    """
    Import the given name as a module, then walk the stack to determine whether
    the failure was the module not existing, or some code in the module (for
    example a dependent import) failing.  This can be helpful to determine
    whether any actual application code was run.  For example, to distiguish
    administrative error (entering the wrong module name), from programmer
    error (writing buggy code in a module that fails to import).

    @param importName: The name of the module to import.
    @type importName: C{str}
    @raise Exception: if something bad happens.  This can be any type of
        exception, since nobody knows what loading some arbitrary code might
        do.
    @raise _NoModuleFound: if no module was found.
    """
    try:
        return __import__(importName)
    except ImportError:
        excType, excValue, excTraceback = sys.exc_info()
        while excTraceback:
            execName = excTraceback.tb_frame.f_globals["__name__"]
            # in Python 2 execName is None when an ImportError is encountered,
            # where in Python 3 execName is equal to the importName.
            if execName is None or execName == importName:
                reraise(excValue, excTraceback)
            excTraceback = excTraceback.tb_next
        raise _NoModuleFound()



def namedAny(name):
    """
    Retrieve a Python object by its fully qualified name from the global Python
    module namespace.  The first part of the name, that describes a module,
    will be discovered and imported.  Each subsequent part of the name is
    treated as the name of an attribute of the object specified by all of the
    name which came before it.  For example, the fully-qualified name of this
    object is 'twisted.python.reflect.namedAny'.

    @type name: L{str}
    @param name: The name of the object to return.

    @raise InvalidName: If the name is an empty string, starts or ends with
        a '.', or is otherwise syntactically incorrect.

    @raise ModuleNotFound: If the name is syntactically correct but the
        module it specifies cannot be imported because it does not appear to
        exist.

    @raise ObjectNotFound: If the name is syntactically correct, includes at
        least one '.', but the module it specifies cannot be imported because
        it does not appear to exist.

    @raise AttributeError: If an attribute of an object along the way cannot be
        accessed, or a module along the way is not found.

    @return: the Python object identified by 'name'.
    """
    if not name:
        raise InvalidName('Empty module name')

    names = name.split('.')

    # if the name starts or ends with a '.' or contains '..', the __import__
    # will raise an 'Empty module name' error. This will provide a better error
    # message.
    if '' in names:
        raise InvalidName(
            "name must be a string giving a '.'-separated list of Python "
            "identifiers, not %r" % (name,))

    topLevelPackage = None
    moduleNames = names[:]
    while not topLevelPackage:
        if moduleNames:
            trialname = '.'.join(moduleNames)
            try:
                topLevelPackage = _importAndCheckStack(trialname)
            except _NoModuleFound:
                moduleNames.pop()
        else:
            if len(names) == 1:
                raise ModuleNotFound("No module named %r" % (name,))
            else:
                raise ObjectNotFound('%r does not name an object' % (name,))

    obj = topLevelPackage
    for n in names[1:]:
        obj = getattr(obj, n)

    return obj



def filenameToModuleName(fn):
    """
    Convert a name in the filesystem to the name of the Python module it is.

    This is aggressive about getting a module name back from a file; it will
    always return a string.  Aggressive means 'sometimes wrong'; it won't look
    at the Python path or try to do any error checking: don't use this method
    unless you already know that the filename you're talking about is a Python
    module.

    @param fn: A filesystem path to a module or package; C{bytes} on Python 2,
        C{bytes} or C{unicode} on Python 3.

    @return: A hopefully importable module name.
    @rtype: C{str}
    """
    if isinstance(fn, bytes):
        initPy = b"__init__.py"
    else:
        initPy = "__init__.py"
    fullName = os.path.abspath(fn)
    base = os.path.basename(fn)
    if not base:
        # this happens when fn ends with a path separator, just skit it
        base = os.path.basename(fn[:-1])
    modName = nativeString(os.path.splitext(base)[0])
    while 1:
        fullName = os.path.dirname(fullName)
        if os.path.exists(os.path.join(fullName, initPy)):
            modName = "%s.%s" % (
                nativeString(os.path.basename(fullName)),
                nativeString(modName))
        else:
            break
    return modName



def qual(clazz):
    """
    Return full import path of a class.
    """
    return clazz.__module__ + '.' + clazz.__name__



def _determineClass(x):
    try:
        return x.__class__
    except:
        return type(x)



def _determineClassName(x):
    c = _determineClass(x)
    try:
        return c.__name__
    except:
        try:
            return str(c)
        except:
            return '<BROKEN CLASS AT 0x%x>' % id(c)



def _safeFormat(formatter, o):
    """
    Helper function for L{safe_repr} and L{safe_str}.
    """
    try:
        return formatter(o)
    except:
        io = NativeStringIO()
        traceback.print_exc(file=io)
        className = _determineClassName(o)
        tbValue = io.getvalue()
        return "<%s instance at 0x%x with %s error:\n %s>" % (
            className, id(o), formatter.__name__, tbValue)



def safe_repr(o):
    """
    Returns a string representation of an object, or a string containing a
    traceback, if that object's __repr__ raised an exception.

    @param o: Any object.

    @rtype: C{str}
    """
    return _safeFormat(repr, o)



def safe_str(o):
    """
    Returns a string representation of an object, or a string containing a
    traceback, if that object's __str__ raised an exception.

    @param o: Any object.

    @rtype: C{str}
    """
    return _safeFormat(str, o)
