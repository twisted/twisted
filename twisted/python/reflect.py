# -*- test-case-name: twisted.test.test_reflect -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Standardized versions of various cool and/or strange things that you can do
with Python's reflection capabilities.
"""

import sys
import types
import pickle
import weakref
import re
import warnings
from collections import deque

RegexType = type(re.compile(""))


try:
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO

from twisted.python.compat import _PY3
from twisted.python.deprecate import deprecated
from twisted.python.deprecate import _fullyQualifiedName as fullyQualifiedName
from twisted.python.versions import Version

from twisted.python._reflectpy3 import (
    prefixedMethods, accumulateMethods, prefixedMethodNames,
    addMethodNamesToDict)
from twisted.python._reflectpy3 import namedModule, namedObject, namedClass
from twisted.python._reflectpy3 import InvalidName, ModuleNotFound
from twisted.python._reflectpy3 import ObjectNotFound, namedAny
from twisted.python._reflectpy3 import filenameToModuleName
from twisted.python._reflectpy3 import qual, safe_str, safe_repr


class QueueMethod:
    """
    I represent a method that doesn't exist yet.
    """
    def __init__(self, name, calls):
        self.name = name
        self.calls = calls
    def __call__(self, *args):
        self.calls.append((self.name, args))


def funcinfo(function):
    """
    this is more documentation for myself than useful code.
    """
    warnings.warn(
        "[v2.5] Use inspect.getargspec instead of twisted.python.reflect.funcinfo",
        DeprecationWarning,
        stacklevel=2)
    code=function.func_code
    name=function.func_name
    argc=code.co_argcount
    argv=code.co_varnames[:argc]
    defaults=function.func_defaults

    out = []

    out.append('The function %s accepts %s arguments' % (name ,argc))
    if defaults:
        required=argc-len(defaults)
        out.append('It requires %s arguments' % required)
        out.append('The arguments required are: %s' % argv[:required])
        out.append('additional arguments are:')
        for i in range(argc-required):
            j=i+required
            out.append('%s which has a default of' % (argv[j], defaults[i]))
    return out


ISNT=0
WAS=1
IS=2


def fullFuncName(func):
    qualName = (str(pickle.whichmodule(func, func.__name__)) + '.' + func.__name__)
    if namedObject(qualName) is not func:
        raise Exception("Couldn't find %s as %s." % (func, qualName))
    return qualName



def getcurrent(clazz):
    assert type(clazz) == types.ClassType, 'must be a class...'
    module = namedModule(clazz.__module__)
    currclass = getattr(module, clazz.__name__, None)
    if currclass is None:
        return clazz
    return currclass


def getClass(obj):
    """
    Return the class or type of object 'obj'.
    Returns sensible result for oldstyle and newstyle instances and types.
    """
    if hasattr(obj, '__class__'):
        return obj.__class__
    else:
        return type(obj)

# class graph nonsense

# I should really have a better name for this...
def isinst(inst,clazz):
    if type(inst) != types.InstanceType or type(clazz)!= types.ClassType:
        return isinstance(inst,clazz)
    cl = inst.__class__
    cl2 = getcurrent(cl)
    clazz = getcurrent(clazz)
    if issubclass(cl2,clazz):
        if cl == cl2:
            return WAS
        else:
            inst.__class__ = cl2
            return IS
    else:
        return ISNT



## the following were factored out of usage

if not _PY3:
    # These functions are still imported by libraries used in turn by the
    # Twisted unit tests, like Nevow 0.10. Since they are deprecated,
    # there's no need to port them to Python 3 (hence the condition above).
    # https://bazaar.launchpad.net/~divmod-dev/divmod.org/trunk/revision/2716
    # removed the dependency in Nevow. Once that is released, these functions
    # can be safely removed from Twisted.

    @deprecated(Version("Twisted", 11, 0, 0), "inspect.getmro")
    def allYourBase(classObj, baseClass=None):
        """
        allYourBase(classObj, baseClass=None) -> list of all base
        classes that are subclasses of baseClass, unless it is None,
        in which case all bases will be added.
        """
        l = []
        _accumulateBases(classObj, l, baseClass)
        return l


    @deprecated(Version("Twisted", 11, 0, 0), "inspect.getmro")
    def accumulateBases(classObj, l, baseClass=None):
        _accumulateBases(classObj, l, baseClass)


    def _accumulateBases(classObj, l, baseClass=None):
        for base in classObj.__bases__:
            if baseClass is None or issubclass(base, baseClass):
                l.append(base)
            _accumulateBases(base, l, baseClass)


def accumulateClassDict(classObj, attr, adict, baseClass=None):
    """
    Accumulate all attributes of a given name in a class hierarchy into a single dictionary.

    Assuming all class attributes of this name are dictionaries.
    If any of the dictionaries being accumulated have the same key, the
    one highest in the class heirarchy wins.
    (XXX: If \"higest\" means \"closest to the starting class\".)

    Ex::

      class Soy:
        properties = {\"taste\": \"bland\"}
    
      class Plant:
        properties = {\"colour\": \"green\"}
    
      class Seaweed(Plant):
        pass
    
      class Lunch(Soy, Seaweed):
        properties = {\"vegan\": 1 }
    
      dct = {}
    
      accumulateClassDict(Lunch, \"properties\", dct)
    
      print dct

    {\"taste\": \"bland\", \"colour\": \"green\", \"vegan\": 1}
    """
    for base in classObj.__bases__:
        accumulateClassDict(base, attr, adict)
    if baseClass is None or baseClass in classObj.__bases__:
        adict.update(classObj.__dict__.get(attr, {}))


def accumulateClassList(classObj, attr, listObj, baseClass=None):
    """
    Accumulate all attributes of a given name in a class heirarchy into a single list.

    Assuming all class attributes of this name are lists.
    """
    for base in classObj.__bases__:
        accumulateClassList(base, attr, listObj)
    if baseClass is None or baseClass in classObj.__bases__:
        listObj.extend(classObj.__dict__.get(attr, []))


def isSame(a, b):
    return (a is b)


def isLike(a, b):
    return (a == b)


def modgrep(goal):
    return objgrep(sys.modules, goal, isLike, 'sys.modules')


def isOfType(start, goal):
    return ((type(start) is goal) or
            (isinstance(start, types.InstanceType) and
             start.__class__ is goal))


def findInstances(start, t):
    return objgrep(start, t, isOfType)


def objgrep(start, goal, eq=isLike, path='', paths=None, seen=None, showUnknowns=0, maxDepth=None):
    """
    An insanely CPU-intensive process for finding stuff.
    """
    if paths is None:
        paths = []
    if seen is None:
        seen = {}
    if eq(start, goal):
        paths.append(path)
    if id(start) in seen:
        if seen[id(start)] is start:
            return
    if maxDepth is not None:
        if maxDepth == 0:
            return
        maxDepth -= 1
    seen[id(start)] = start
    if isinstance(start, types.DictionaryType):
        for k, v in start.items():
            objgrep(k, goal, eq, path+'{'+repr(v)+'}', paths, seen, showUnknowns, maxDepth)
            objgrep(v, goal, eq, path+'['+repr(k)+']', paths, seen, showUnknowns, maxDepth)
    elif isinstance(start, (list, tuple, deque)):
        for idx in xrange(len(start)):
            objgrep(start[idx], goal, eq, path+'['+str(idx)+']', paths, seen, showUnknowns, maxDepth)
    elif isinstance(start, types.MethodType):
        objgrep(start.im_self, goal, eq, path+'.im_self', paths, seen, showUnknowns, maxDepth)
        objgrep(start.im_func, goal, eq, path+'.im_func', paths, seen, showUnknowns, maxDepth)
        objgrep(start.im_class, goal, eq, path+'.im_class', paths, seen, showUnknowns, maxDepth)
    elif hasattr(start, '__dict__'):
        for k, v in start.__dict__.items():
            objgrep(v, goal, eq, path+'.'+k, paths, seen, showUnknowns, maxDepth)
        if isinstance(start, types.InstanceType):
            objgrep(start.__class__, goal, eq, path+'.__class__', paths, seen, showUnknowns, maxDepth)
    elif isinstance(start, weakref.ReferenceType):
        objgrep(start(), goal, eq, path+'()', paths, seen, showUnknowns, maxDepth)
    elif (isinstance(start, types.StringTypes+
                    (types.IntType, types.FunctionType,
                     types.BuiltinMethodType, RegexType, types.FloatType,
                     types.NoneType, types.FileType)) or
          type(start).__name__ in ('wrapper_descriptor', 'method_descriptor',
                                   'member_descriptor', 'getset_descriptor')):
        pass
    elif showUnknowns:
        print 'unknown type', type(start), start
    return paths



__all__ = [
    'InvalidName', 'ModuleNotFound', 'ObjectNotFound',

    'ISNT', 'WAS', 'IS',

    'QueueMethod',

    'funcinfo', 'fullFuncName', 'qual', 'getcurrent', 'getClass', 'isinst',
    'namedModule', 'namedObject', 'namedClass', 'namedAny',
    'safe_repr', 'safe_str', 'allYourBase', 'accumulateBases',
    'prefixedMethodNames', 'addMethodNamesToDict', 'prefixedMethods',
    'accumulateMethods',
    'accumulateClassDict', 'accumulateClassList', 'isSame', 'isLike',
    'modgrep', 'isOfType', 'findInstances', 'objgrep', 'filenameToModuleName',
    'fullyQualifiedName']
