# -*- test-case-name: twisted.test.test_reflect -*-

# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.


"""
Standardized versions of various cool and/or strange things that you can do
with Python's reflection capabilities.
"""

from __future__ import nested_scopes


# System Imports
import sys
import os
import types
import string
import pickle
import new
import traceback
import weakref
import re

RegexType = type(re.compile(""))


try:
    import cStringIO as StringIO
except ImportError:
    import StringIO

class Settable:
    """
    A mixin class for syntactic sugar.  Lets you assign attributes by
    calling with keyword arguments; for example, C{x(a=b,c=d,y=z)} is the
    same as C{x.a=b;x.c=d;x.y=z}.  The most useful place for this is
    where you don't want to name a variable, but you do want to set
    some attributes; for example, C{X()(y=z,a=b)}.
    """
    def __init__(self, **kw):
        self(**kw)

    def __call__(self,**kw):
        for key,val in kw.items():
            setattr(self,key,val)
        return self


class AccessorType(type):
    """Metaclass that generates properties automatically.

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
                        if this.__dict__.has_key(name):
                            return this.__dict__[name]
                        else:
                            return value
                else:
                    def getter(this, name=name):
                        if this.__dict__.has_key(name):
                            return this.__dict__[name]
                        else:
                            raise AttributeError, "no such attribute %r" % name
            if setter is None:
                def setter(this, value, name=name):
                    this.__dict__[name] = value
            if deler is None:
                def deler(this, name=name):
                    del this.__dict__[name]
            setattr(self, name, property(getter, setter, deler, ""))


class PropertyAccessor(object):
    """A mixin class for Python 2.2 that uses AccessorType.

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
    """ I represent a method that doesn't exist yet."""
    def __init__(self, name, calls):
        self.name = name
        self.calls = calls
    def __call__(self, *args):
        self.calls.append((self.name, args))


def funcinfo(function):
    """
    this is more documentation for myself than useful code.
    """
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

def qual(clazz):
    """Return full import path of a class."""
    return clazz.__module__ + '.' + clazz.__name__

def getcurrent(clazz):
    assert type(clazz) == types.ClassType, 'must be a class...'
    module = namedModule(clazz.__module__)
    currclass = getattr(module, clazz.__name__, None)
    if currclass is None:
        return clazz
    return currclass

def getClass(obj):
    """Return the class or type of object 'obj'.
    Returns sensible result for oldstyle and newstyle instances and types."""
    if hasattr(obj, '__class__'):
        return obj.__class__
    else:
        return type(obj)

# class graph nonsense

# I should really have a better name for this...
def isinst(inst,clazz):
    if type(inst) != types.InstanceType or type(clazz)!=types.ClassType:
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


def namedModule(name):
    """Return a module given its name."""
    topLevel = __import__(name)
    packages = name.split(".")[1:]
    m = topLevel
    for p in packages:
        m = getattr(m, p)
    return m


def namedObject(name):
    """Get a fully named module-global object.
    """
    classSplit = string.split(name, '.')
    module = namedModule(string.join(classSplit[:-1], '.'))
    return getattr(module, classSplit[-1])

namedClass = namedObject # backwards compat

def namedAny(name):
    """Get a fully named package, module, module-global object, or attribute.
    """
    names = name.split('.')
    topLevelPackage = None
    moduleNames = names[:]
    while not topLevelPackage:
        try:
            trialname = '.'.join(moduleNames)
            topLevelPackage = __import__(trialname)
        except ImportError:
            # if the ImportError happened in the module being imported,
            # this is a failure that should be handed to our caller.
            # count stack frames to tell the difference.
            exc_info = sys.exc_info()
            if len(traceback.extract_tb(exc_info[2])) > 1:
                try:
                    # Clean up garbage left in sys.modules.
                    del sys.modules[trialname]
                except KeyError:
                    # Python 2.4 has fixed this.  Yay!
                    pass
                raise exc_info[0], exc_info[1], exc_info[2]
            moduleNames.pop()
    
    obj = topLevelPackage
    for n in names[1:]:
        obj = getattr(obj, n)
        
    return obj

def _reclass(clazz):
    clazz = getattr(namedModule(clazz.__module__),clazz.__name__)
    clazz.__bases__ = tuple(map(_reclass, clazz.__bases__))
    return clazz




def macro(name, filename, source, **identifiers):
    """macro(name, source, **identifiers)

    This allows you to create macro-like behaviors in python.  See
    twisted.python.hook for an example of its usage.
    """
    if not identifiers.has_key('name'):
        identifiers['name'] = name
    source = source % identifiers
    codeplace = "<%s (macro)>" % filename
    code = compile(source, codeplace, 'exec')

    # shield your eyes!
    sm = sys.modules
    tprm = "twisted.python.reflect.macros"
    if not sm.has_key(tprm):
        macros = new.module(tprm)
        sm[tprm] = macros
        macros.count = 0
    macros = sm[tprm]
    macros.count += 1
    macroname = 'macro_' + str(macros.count)
    tprmm = tprm + '.' + macroname
    mymod = new.module(tprmm)
    sys.modules[tprmm] = mymod
    setattr(macros, macroname, mymod)
    dict = mymod.__dict__

    # Before we go on, I guess I should explain why I just did that.  Basically
    # it's a gross hack to get epydoc to work right, but the general idea is
    # that it will be a useful aid in debugging in _any_ app which expects
    # sys.modules to have the same globals as some function.  For example, it
    # would be useful if you were foolishly trying to pickle a wrapped function
    # directly from a class that had been hooked.

    exec code in dict, dict
    return dict[name]

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
            return '<BROKEN CLASS AT %s>' % id(c)

def safe_repr(o):
    """safe_repr(anything) -> string

    Returns a string representation of an object, or a string containing a
    traceback, if that object's __repr__ raised an exception.
    """

    try:
        return repr(o)
    except:
        io = StringIO.StringIO()
        traceback.print_stack(file=io)
        whati = _determineClassName(o)
        swron = io.getvalue()
        gwith = id(o)
        you ='<%s instance at %s with repr error %s>' % (
            whati,swron,gwith)
        return you

def safe_str(o):
    """safe_str(anything) -> string

    Returns a string representation of an object, or a string containing a
    traceback, if that object's __str__ raised an exception.
    """

    try:
        return str(o)
    except:
        strExc = '\n'.join(traceback.format_exception(*sys.exc_info()))
        clsName = _determineClassName(o)
        obId = id(o)
        return '<%s instance at %s with str error %s>' % (
            clsName, obId, strExc)


##the following were factored out of usage

def allYourBase(classObj, baseClass=None):
    """allYourBase(classObj, baseClass=None) -> list of all base
    classes that are subclasses of baseClass, unless it is None,
    in which case all bases will be added.
    """
    l = []
    accumulateBases(classObj, l, baseClass)
    return l


def accumulateBases(classObj, l, baseClass=None):
    for base in classObj.__bases__:
        if baseClass is None or issubclass(base, baseClass):
            l.append(base)
        accumulateBases(base, l, baseClass)


def prefixedMethodNames(classObj, prefix):
    """A list of method names with a given prefix in a given class.
    """
    dct = {}
    addMethodNamesToDict(classObj, dct, prefix)
    return dct.keys()


def addMethodNamesToDict(classObj, dict, prefix, baseClass=None):
    """
    addMethodNamesToDict(classObj, dict, prefix, baseClass=None) -> dict
    this goes through 'classObj' (and its bases) and puts method names
    starting with 'prefix' in 'dict' with a value of 1. if baseClass isn't
    None, methods will only be added if classObj is-a baseClass

    If the class in question has the methods 'prefix_methodname' and
    'prefix_methodname2', the resulting dict should look something like:
    {"methodname": 1, "methodname2": 1}.
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
    """A list of methods with a given prefix on a given instance.
    """
    dct = {}
    accumulateMethods(obj, dct, prefix)
    return dct.values()

def accumulateMethods(obj, dict, prefix='', curClass=None):
    """accumulateMethods(instance, dict, prefix)
    I recurse through the bases of instance.__class__, and add methods
    beginning with 'prefix' to 'dict', in the form of
    {'methodname':*instance*method_object}.
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

def accumulateClassDict(classObj, attr, adict, baseClass=None):
    """Accumulate all attributes of a given name in a class heirarchy into a single dictionary.

    Assuming all class attributes of this name are dictionaries.
    If any of the dictionaries being accumulated have the same key, the
    one highest in the class heirarchy wins.
    (XXX: If \"higest\" means \"closest to the starting class\".)

    Ex::

    | class Soy:
    |   properties = {\"taste\": \"bland\"}
    |
    | class Plant:
    |   properties = {\"colour\": \"green\"}
    |
    | class Seaweed(Plant):
    |   pass
    |
    | class Lunch(Soy, Seaweed):
    |   properties = {\"vegan\": 1 }
    |
    | dct = {}
    |
    | accumulateClassDict(Lunch, \"properties\", dct)
    |
    | print dct

    {\"taste\": \"bland\", \"colour\": \"green\", \"vegan\": 1}
    """
    for base in classObj.__bases__:
        accumulateClassDict(base, attr, adict)
    if baseClass is None or baseClass in classObj.__bases__:
        adict.update(classObj.__dict__.get(attr, {}))


def accumulateClassList(classObj, attr, listObj, baseClass=None):
    """Accumulate all attributes of a given name in a class heirarchy into a single list.

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
    '''An insanely CPU-intensive process for finding stuff.
    '''
    if paths is None:
        paths = []
    if seen is None:
        seen = {}
    if eq(start, goal):
        paths.append(path)
    if seen.has_key(id(start)):
        if seen[id(start)] is start:
            return
    if maxDepth is not None:
        if maxDepth == 0:
            return
        maxDepth -= 1
    seen[id(start)] = start
    if isinstance(start, types.DictionaryType):
        r = []
        for k, v in start.items():
            objgrep(k, goal, eq, path+'{'+repr(v)+'}', paths, seen, showUnknowns, maxDepth)
            objgrep(v, goal, eq, path+'['+repr(k)+']', paths, seen, showUnknowns, maxDepth)
    elif isinstance(start, types.ListType) or isinstance(start, types.TupleType):
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

def _startswith(s, sub):
    # aug python2.1
    return s[:len(sub)] == sub

def filenameToModuleName(fn):
    """Convert a name in the filesystem to the name of the Python module it is.

    This is agressive about getting a module name back from a file; it will
    always return a string.  Agressive means 'sometimes wrong'; it won't look
    at the Python path or try to do any error checking: don't use this method
    unless you already know that the filename you're talking about is a Python
    module.
    """
    fullName = os.path.abspath(fn)
    modName = os.path.splitext(os.path.basename(fn))[0]
    while 1:
        fullName = os.path.dirname(fullName)
        if os.path.exists(os.path.join(fullName, "__init__.py")):
            modName = "%s.%s" % (os.path.basename(fullName), modName)
        else:
            break
    return modName

#boo python
