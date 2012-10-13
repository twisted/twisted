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

try:
    from collections import deque
except ImportError:
    deque = list

RegexType = type(re.compile(""))


try:
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO

from twisted.python._utilpy3 import unsignedID
from twisted.python.deprecate import deprecated, deprecatedModuleAttribute
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

class Settable:
    """
    A mixin class for syntactic sugar.  Lets you assign attributes by
    calling with keyword arguments; for example, C{x(a=b,c=d,y=z)} is the
    same as C{x.a=b;x.c=d;x.y=z}.  The most useful place for this is
    where you don't want to name a variable, but you do want to set
    some attributes; for example, C{X()(y=z,a=b)}.
    """

    deprecatedModuleAttribute(
        Version("Twisted", 12, 1, 0),
        "Settable is old and untested. Please write your own version of this "
        "functionality if you need it.", "twisted.python.reflect", "Settable")

    def __init__(self, **kw):
        self(**kw)

    def __call__(self,**kw):
        for key,val in kw.items():
            setattr(self,key,val)
        return self


class AccessorType(type):
    """
    Metaclass that generates properties automatically.

    This is for Python 2.2 and up.

    Using this metaclass for your class will give you explicit accessor
    methods; a method called set_foo, will automatically create a property
    'foo' that uses set_foo as a setter method. Same for get_foo and del_foo.

    Note that this will only work on methods that are present on class
    creation. If you add methods after the class is defined they will not
    automatically become properties. Likewise, class attributes will only
    be used if they are present upon class creation, and no getter function
    was set - if a getter is present, the class attribute will be ignored.

    This is a 2.2-only alternative to the Accessor mixin - just set in your
    class definition::

        __metaclass__ = AccessorType

    """

    deprecatedModuleAttribute(
        Version("Twisted", 12, 1, 0),
        "AccessorType is old and untested. Please write your own version of "
        "this functionality if you need it.", "twisted.python.reflect",
        "AccessorType")

    def __init__(self, name, bases, d):
        type.__init__(self, name, bases, d)
        accessors = {}
        prefixs = ["get_", "set_", "del_"]
        for k in d.keys():
            v = getattr(self, k)
            for i in range(3):
                if k.startswith(prefixs[i]):
                    accessors.setdefault(k[4:], [None, None, None])[i] = v
        for name, (getter, setter, deler) in accessors.items():
            # create default behaviours for the property - if we leave
            # the getter as None we won't be able to getattr, etc..
            if getter is None:
                if hasattr(self, name):
                    value = getattr(self, name)
                    def getter(this, value=value, name=name):
                        if name in this.__dict__:
                            return this.__dict__[name]
                        else:
                            return value
                else:
                    def getter(this, name=name):
                        if name in this.__dict__:
                            return this.__dict__[name]
                        else:
                            raise AttributeError("no such attribute %r" % name)
            if setter is None:
                def setter(this, value, name=name):
                    this.__dict__[name] = value
            if deler is None:
                def deler(this, name=name):
                    del this.__dict__[name]
            setattr(self, name, property(getter, setter, deler, ""))


class PropertyAccessor(object):
    """
    A mixin class for Python 2.2 that uses AccessorType.

    This provides compatability with the pre-2.2 Accessor mixin, up
    to a point.

    Extending this class will give you explicit accessor methods; a
    method called set_foo, for example, is the same as an if statement
    in __setattr__ looking for 'foo'.  Same for get_foo and del_foo.

    There are also reallyDel and reallySet methods, so you can
    override specifics in subclasses without clobbering __setattr__
    and __getattr__, or using non-2.1 compatible code.

    There is are incompatibilities with Accessor - accessor
    methods added after class creation will *not* be detected. OTOH,
    this method is probably way faster.

    In addition, class attributes will only be used if no getter
    was defined, and instance attributes will not override getter methods
    whereas in original Accessor the class attribute or instance attribute
    would override the getter method.
    """
    # addendum to above:
    # The behaviour of Accessor is wrong IMHO, and I've found bugs
    # caused by it.
    #  -- itamar

    deprecatedModuleAttribute(
        Version("Twisted", 12, 1, 0),
        "PropertyAccessor is old and untested. Please write your own version "
        "of this functionality if you need it.", "twisted.python.reflect",
        "PropertyAccessor")
    __metaclass__ = AccessorType

    def reallySet(self, k, v):
        self.__dict__[k] = v

    def reallyDel(self, k):
        del self.__dict__[k]


class Accessor:
    """
    Extending this class will give you explicit accessor methods; a
    method called C{set_foo}, for example, is the same as an if statement
    in L{__setattr__} looking for C{'foo'}.  Same for C{get_foo} and
    C{del_foo}.  There are also L{reallyDel} and L{reallySet} methods,
    so you can override specifics in subclasses without clobbering
    L{__setattr__} and L{__getattr__}.

    This implementation is for Python 2.1.
    """

    deprecatedModuleAttribute(
        Version("Twisted", 12, 1, 0),
        "Accessor is an implementation for Python 2.1 which is no longer "
        "supported by Twisted.", "twisted.python.reflect", "Accessor")

    def __setattr__(self, k,v):
        kstring='set_%s'%k
        if hasattr(self.__class__,kstring):
            return getattr(self,kstring)(v)
        else:
            self.reallySet(k,v)

    def __getattr__(self, k):
        kstring='get_%s'%k
        if hasattr(self.__class__,kstring):
            return getattr(self,kstring)()
        raise AttributeError("%s instance has no accessor for: %s" % (qual(self.__class__),k))

    def __delattr__(self, k):
        kstring='del_%s'%k
        if hasattr(self.__class__,kstring):
            getattr(self,kstring)()
            return
        self.reallyDel(k)

    def reallySet(self, k,v):
        """
        *actually* set self.k to v without incurring side-effects.
        This is a hook to be overridden by subclasses.
        """
        if k == "__dict__":
            self.__dict__.clear()
            self.__dict__.update(v)
        else:
            self.__dict__[k]=v

    def reallyDel(self, k):
        """
        *actually* del self.k without incurring side-effects.  This is a
        hook to be overridden by subclasses.
        """
        del self.__dict__[k]

# just in case
OriginalAccessor = Accessor
deprecatedModuleAttribute(
    Version("Twisted", 12, 1, 0),
    "OriginalAccessor is a reference to class twisted.python.reflect.Accessor "
    "which is deprecated.", "twisted.python.reflect", "OriginalAccessor")


class Summer(Accessor):
    """
    Extend from this class to get the capability to maintain 'related
    sums'.  Have a tuple in your class like the following::

        sums=(('amount','credit','credit_total'),
              ('amount','debit','debit_total'))

    and the 'credit_total' member of the 'credit' member of self will
    always be incremented when the 'amount' member of self is
    incremented, similiarly for the debit versions.
    """

    deprecatedModuleAttribute(
        Version("Twisted", 12, 1, 0),
        "Summer is a child class of twisted.python.reflect.Accessor which is " 
        "deprecated.", "twisted.python.reflect", "Summer")

    def reallySet(self, k,v):
        "This method does the work."
        for sum in self.sums:
            attr=sum[0]
            obj=sum[1]
            objattr=sum[2]
            if k == attr:
                try:
                    oldval=getattr(self, attr)
                except:
                    oldval=0
                diff=v-oldval
                if hasattr(self, obj):
                    ob=getattr(self,obj)
                    if ob is not None:
                        try:oldobjval=getattr(ob, objattr)
                        except:oldobjval=0.0
                        setattr(ob,objattr,oldobjval+diff)

            elif k == obj:
                if hasattr(self, attr):
                    x=getattr(self,attr)
                    setattr(self,attr,0)
                    y=getattr(self,k)
                    Accessor.reallySet(self,k,v)
                    setattr(self,attr,x)
                    Accessor.reallySet(self,y,v)
        Accessor.reallySet(self,k,v)


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

    'Settable', 'AccessorType', 'PropertyAccessor', 'Accessor', 'Summer',
    'QueueMethod', 'OriginalAccessor',

    'funcinfo', 'fullFuncName', 'qual', 'getcurrent', 'getClass', 'isinst',
    'namedModule', 'namedObject', 'namedClass', 'namedAny',
    'safe_repr', 'safe_str', 'allYourBase', 'accumulateBases',
    'prefixedMethodNames', 'addMethodNamesToDict', 'prefixedMethods',
    'accumulateMethods',
    'accumulateClassDict', 'accumulateClassList', 'isSame', 'isLike',
    'modgrep', 'isOfType', 'findInstances', 'objgrep', 'filenameToModuleName',
    'fullyQualifiedName']
