# -*- test-case-name: twisted.test.test_reflect -*-

# Twisted, the Framework of Your Internet
# Copyright (C) 2001 Matthew W. Lefkowitz
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of version 2.1 of the GNU Lesser General Public
# License as published by the Free Software Foundation.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

"""
Standardized versions of various cool and/or strange things that you can do
with Python's reflection capabilities.
"""

from __future__ import nested_scopes


# System Imports
import sys
import os
import types
import cStringIO
import string
import pickle

# Sibling Imports
import reference
import failure


class Settable:
    """
    A mixin class for syntactic sugar.  Lets you assign attributes by
    calling with keyword arguments; for example, x(a=b,c=d,y=z) is the
    same as x.a=b;x.c=d;x.y=z.  The most useful place for this is
    where you don't want to name a variable, but you do want to set
    some attributes; for example, X()(y=z,a=b).
    """
    def __init__(self, **kw):
        apply(self,(),kw)

    def __call__(self,**kw):
        for key,val in kw.items():
            setattr(self,key,val)
        return self


if sys.version_info[:2] >= (2, 2):
    type22 = type
else:
    # just make fake classes so the module can be imported
    class type22: pass
    class object: pass


class AccessorType(type22):
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
    
    def __init__(self, name, bases, dict):
        type.__init__(self, name, bases, dict)
        accessors = {}
        prefixs = ["get_", "set_", "del_"]
        for k in dict.keys():
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

    There is are incompatibilities with the 2.1 version - accessor
    methods added after class creation will *not* be detected. OTOH,
    this method is probably way faster.

    In addition, class attributes will only be used if no getter
    was defined, and instance attributes will not override getter methods
    whereas in original Accessor the class attribute or instance attribute
    would override the getter method.
    """
    # addendum to above:
    # The behaviour of OriginalAccessor is wrong IMHO, and I've found bugs
    # caused by it.
    #  -- itamar
    
    __metaclass__ = AccessorType

    def reallySet(self, k, v):
        self.__dict__[k] = v

    def reallyDel(self, k):
        del self.__dict__[k]


class OriginalAccessor:
    """
    Extending this class will give you explicit accessor methods; a
    method called set_foo, for example, is the same as an if statement
    in __setattr__ looking for 'foo'.  Same for get_foo and del_foo.
    There are also reallyDel and reallySet methods, so you can
    override specifics in subclasses without clobbering __setattr__
    and __getattr__.

    This implementation is for Python 2.1.
    """

    def __setattr__(self, k,v):
        kstring='set_%s'%k
        # early-out for references, since they will be reassigned
        # later, and no accessor method should have to know what to do
        # with them.
        if (not isinst(v, reference.Reference) and
            hasattr(self.__class__,kstring)):
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
        self.__dict__[k]=v

    def reallyDel(self, k):
        """
        *actually* del self.k without incurring side-effects.  This is a
        hook to be overridden by subclasses.
        """
        del self.__dict__[k]


# on 2.2, use the PropertyAccessor, on 2.1 use OriginalAccessor
if sys.version_info[:2] >= (2, 2):
    # for now, I'm leaving the new version disabled, as:
    #  1. it causes marmalade to barf - apprently marmalade doesn't like new-style
    #     classes or something
    #  2. it causes errors in observable
    # plus I had to fix some bugs in tendril - I think the OriginalAccessor is
    # rather broken, and the problem is dealing with the fact that the new
    # version's behaviour is different (albeit non-broken).
    #
    # To enable property-based accessor in 2.2, uncomment next 2 lines and
    # delete the 3rd.
    
    #del OriginalAccessor
    #Accessor = PropertyAccessor
    Accessor = OriginalAccessor
else:
    del AccessorType
    del PropertyAccessor
    Accessor = OriginalAccessor


class Summer(Accessor):
    """
    Extend from this class to get the capability to maintain 'related
    sums'.  Have a tuple in your class like the following:

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

class Promise:
    """I represent an object not yet available.

    Methods called on me will be queued and sent as soon as the object becomes
    available.  Typically my __become__ method is registered as a callback with
    some event that will return my new identity.
    """
    def __init__(self):
        self.calls = []

    def __become__(self, new_self):
        for c in self.calls:
            apply(getattr(new_self, c[0]), c[1])
        self.__class__ = new_self.__class__
        self.__dict__ = new_self.__dict__

    def __getattr__(self, key):
        return QueueMethod(key, self.calls)

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
    return clazz.__module__ + '.' + clazz.__name__

def getcurrent(clazz):
    assert type(clazz) == types.ClassType, 'must be a class...'
    module = namedModule(clazz.__module__)
    currclass = getattr(module, clazz.__name__, None)
    if currclass is None:
        log.msg("Reflection Warning: class %s deleted from module %s" % (
            clazz.__name__, clazz.__module__))
        return clazz
    return currclass

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
    """Return a module give its name."""
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

def _reclass(clazz):
    clazz = getattr(namedModule(clazz.__module__),clazz.__name__)
    clazz.__bases__ = tuple(map(_reclass, clazz.__bases__))
    return clazz


# Whoever named this should have check-in priviliges removed,
# unless he or she makes sure no one uses this and then *kills it*.
#
# You know who you are ;)
def refrump(obj):
    """Fix an instance's class after a reload(module). I think.

    See twisted.python.rebuild for a better way of doing this.
    """
    x = _reclass(obj.__class__)
    if x is not obj.__class__:
        obj.__class__ = x
    return obj


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
    dict = {}
    exec code in dict, dict
    return dict[name]

def safe_repr(obj):
    """safe_repr(anything) -> string
    Returns a string representation of an object (or a traceback, if that
    object's __repr__ raised an exception) """

    try:
        return repr(obj)
    except:
        io = cStringIO.StringIO()
        failure.printTraceback(file=io)
        return "exception in repr!\n"+ io.getvalue()


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

def prefixedMethods(obj, prefix):
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

def accumulateClassDict(classObj, attr, dict, baseClass=None):
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
        accumulateClassDict(base, attr, dict)
    if baseClass is None or baseClass in classObj.__bases__:
        dict.update(getattr(classObj, attr, {}))

def accumulateClassList(classObj, attr, listObj, baseClass=None):
    """Accumulate all attributes of a given name in a class heirarchy into a single list.

    Assuming all class attributes of this name are lists.
    """
    for base in classObj.__bases__:
        accumulateClassList(base, attr, listObj)
    if baseClass is None or baseClass in classObj.__bases__:
        listObj.extend(getattr(classObj, attr, []))

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

def objgrep(start, goal, eq=isLike, path='', paths=None, seen=None):
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
    seen[id(start)] = start
    if isinstance(start, types.DictionaryType):
        r = []
        for k, v in start.items():
            objgrep(k, goal, eq, path+'{'+repr(v)+'}', paths, seen)
            objgrep(v, goal, eq, path+'['+repr(k)+']', paths, seen)
    elif isinstance(start, types.ListType) or isinstance(start, types.TupleType):
        for idx in xrange(len(start)):
            objgrep(start[idx], goal, eq, path+'['+str(idx)+']', paths, seen)
    elif (isinstance(start, types.InstanceType) or
          isinstance(start, types.ClassType) or
          isinstance(start, types.ModuleType)):
        for k, v in start.__dict__.items():
            objgrep(v, goal, eq, path+'.'+k, paths, seen)
        if isinstance(start, types.InstanceType):
            objgrep(start.__class__, goal, eq, path+'.__class__', paths, seen)
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
import log
