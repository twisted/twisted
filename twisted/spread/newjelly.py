# -*- test-case-name: twisted.test.test_newjelly -*-

# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.


"""S-expression-based persistence of python objects.

Stability: semi-stable

Future Plans: Optimization.  Lots of optimization.  No semantic breakages
should be necessary, but if small tweaks are required to gain acceptable
large-scale performance then they will be made.  Although Glyph is the
maintainer, Bruce Mitchener will be supervising most of the optimization work
here.

I do something very much like L{Pickle<pickle>}; however, pickle's main goal
seems to be efficiency (both in space and time); jelly's main goals are
security, human readability, and portability to other environments.


This is how Jelly converts various objects to s-expressions:

Boolean: True --> ['boolean', 'true']

Integer: 1 --> 1

List: [1, 2] --> ['list', 1, 2]

String: \"hello\" --> \"hello\"

Float: 2.3 --> 2.3

Dictionary: {'a' : 1, 'b' : 'c'} --> ['dictionary', ['b', 'c'], ['a', 1]]

Module: UserString --> ['module', 'UserString']

Class: UserString.UserString --> ['class', ['module', 'UserString'], 'UserString']

Function: string.join --> ['function', 'join', ['module', 'string']]

Instance: s is an instance of UserString.UserString, with a __dict__ {'data': 'hello'}:
[\"UserString.UserString\", ['dictionary', ['data', 'hello']]]

# ['instance', ['class', ['module', 'UserString'], 'UserString'], ['dictionary', ['data', 'hello']]]

Class Method: UserString.UserString.center:
['method', 'center', ['None'], ['class', ['module', 'UserString'], 'UserString']]

Instance Method: s.center, where s is an instance of UserString.UserString:
['method', 'center', ['instance', ['reference', 1, ['class', ['module', 'UserString'], 'UserString']], ['dictionary', ['data', 'd']]], ['dereference', 1]]

@author: U{Glyph Lefkowitz<mailto:glyph@twistedmatrix.com>}
"""

__version__ = "$Revision: 1.9 $"[11:-2]

# System Imports
import string
import pickle
import sys
import types
from types import StringType
try:
    from types import UnicodeType
except ImportError:
    UnicodeType = None
from types import IntType
from types import TupleType
from types import ListType
from types import DictType
from types import LongType
from types import FloatType
from types import FunctionType
from types import MethodType
from types import ModuleType
from types import DictionaryType
from types import InstanceType
from types import NoneType
from types import ClassType
import copy

try:
    from types import BooleanType
except ImportError:
    BooleanType = None

from new import instance
from new import instancemethod


# Twisted Imports
from twisted.python.reflect import namedObject, namedModule, qual
from twisted.persisted.crefutil import NotKnown, _Tuple, _InstanceMethod, _DictKeyAndValue, _Dereference
from twisted.python import runtime

if runtime.platform.getType() == "java":
    from org.python.core import PyStringMap
    DictTypes = (DictionaryType, PyStringMap)
else:
    DictTypes = (DictionaryType,)


None_atom = "None"                  # N
# code
class_atom = "class"                # c
module_atom = "module"              # m
function_atom = "function"          # f

# references
dereference_atom = 'dereference'    # D
persistent_atom = 'persistent'      # p
reference_atom = 'reference'        # r

# mutable collections
dictionary_atom = "dictionary"      # d
list_atom = 'list'                  # l

# immutable collections
#   (assignment to __dict__ and __class__ still might go away!)
tuple_atom = "tuple"                # t


# errors
unpersistable_atom = "unpersistable"# u
unjellyableRegistry = {}
unjellyableFactoryRegistry = {}

def _maybeClass(classnamep):
    try:
        object
    except NameError:
        isObject = 0
    else:
        isObject = isinstance(classnamep, type)
    if isinstance(classnamep, ClassType) or isObject:
        return qual(classnamep)
    return classnamep

def setUnjellyableForClass(classname, unjellyable):
    """Set which local class will represent a remote type.

    If you have written a Copyable class that you expect your client to be
    receiving, write a local "copy" class to represent it, then call::

        jellier.setUnjellyableForClass('module.package.Class', MyJellier).

    Call this at the module level immediately after its class
    definition. MyCopier should be a subclass of RemoteCopy.

    The classname may be a special tag returned by
    'Copyable.getTypeToCopyFor' rather than an actual classname.

    This call is also for cached classes, since there will be no
    overlap.  The rules are the same.
    """

    global unjellyableRegistry
    classname = _maybeClass(classname)
    unjellyableRegistry[classname] = unjellyable
    globalSecurity.allowTypes(classname)

def setUnjellyableFactoryForClass(classname, copyFactory):
    """
    Set the factory to construct a remote instance of a type::

        jellier.setFactoryForClass('module.package.Class', MyFactory)

    Call this at the module level immediately after its class definition.
    C{copyFactory} should return an instance or subclass of
    L{RemoteCopy<pb.RemoteCopy>}.

    Similar to L{setUnjellyableForClass} except it uses a factory instead
    of creating an instance.
    """

    global unjellyableFactoryRegistry
    classname = _maybeClass(classname)
    unjellyableFactoryRegistry[classname] = copyFactory
    globalSecurity.allowTypes(classname)


def setUnjellyableForClassTree(module, baseClass, prefix=None):
    """
    Set all classes in a module derived from C{baseClass} as copiers for
    a corresponding remote class.

    When you have a heirarchy of Copyable (or Cacheable) classes on
    one side, and a mirror structure of Copied (or RemoteCache)
    classes on the other, use this to setCopierForClass all your
    Copieds for the Copyables.

    Each copyTag (the \"classname\" argument to getTypeToCopyFor, and
    what the Copyable's getTypeToCopyFor returns) is formed from
    adding a prefix to the Copied's class name.  The prefix defaults
    to module.__name__.  If you wish the copy tag to consist of solely
    the classname, pass the empty string \'\'.

    @param module: a module object from which to pull the Copied classes.
        (passing sys.modules[__name__] might be useful)

    @param baseClass: the base class from which all your Copied classes derive.

    @param prefix: the string prefixed to classnames to form the
        unjellyableRegistry.
    """
    if prefix is None:
        prefix = module.__name__

    if prefix:
        prefix = "%s." % prefix

    for i in dir(module):
        i_ = getattr(module, i)
        if type(i_) == types.ClassType:
            if issubclass(i_, baseClass):
                setUnjellyableForClass('%s%s' % (prefix, i), i_)

def getInstanceState(inst, jellier):
    """Utility method to default to 'normal' state rules in serialization.
    """
    if hasattr(inst, "__getstate__"):
        state = inst.__getstate__()
    else:
        state = inst.__dict__
    sxp = jellier.prepare(inst)
    sxp.extend([qual(inst.__class__), jellier.jelly(state)])
    return jellier.preserve(inst, sxp)

def setInstanceState(inst, unjellier, jellyList):
    """Utility method to default to 'normal' state rules in unserialization.
    """
    state = unjellier.unjelly(jellyList[1])
    if hasattr(inst, "__setstate__"):
        inst.__setstate__(state)
    else:
        inst.__dict__ = state
    return inst

class Unpersistable:
    """
    This is an instance of a class that comes back when something couldn't be
    persisted.
    """
    def __init__(self, reason):
        """
        Initialize an unpersistable object with a descriptive `reason' string.
        """
        self.reason = reason

    def __repr__(self):
        return "Unpersistable(%s)" % repr(self.reason)

class Jellyable:
    """Inherit from me to Jelly yourself directly.
    """
    def getStateFor(self, jellier):
        return self.__dict__

    def jellyFor(self, jellier):
        sxp = jellier.prepare(self)
        sxp.extend([
            qual(self.__class__),
            jellier.jelly(self.getStateFor(jellier))])
        return jellier.preserve(self, sxp)

class Unjellyable:
    """Inherit from me to Unjelly yourself directly.
    """
    def setStateFor(self, unjellier, state):
        self.__dict__ = state

    def unjellyFor(self, unjellier, jellyList):
        state = unjellier.unjelly(jellyList[1])
        self.setStateFor(unjellier, state)


class _Jellier:
    """(Internal) This class manages state for a call to jelly()
    """
    def __init__(self, taster, persistentStore, invoker):
        """Initialize.
        """
        self.taster = taster
        self.seen = {} # maps from object ID to reference number
        self._ref_id = 0
        #self.persistentStore = persistentStore  # ignored
        self.invoker = invoker

    constantTypes = {types.StringType : 1, types.IntType : 1,
                     types.FloatType : 1, types.LongType : 1}

    # XXX ancient horrible backwards-compatibility
    
    def prepare(self, obj):
        return []

    def preserve(self, obj, jlist):
        return jlist

    def _checkMutable(self, obj, refId):
        objId = id(obj)
        if self.seen.has_key(objId):
            objCheck, derefKey = self.seen[objId]
            return [dereference_atom, derefKey]
        self.seen[objId] = obj, refId

    def jelly(self, obj):
        if isinstance(obj, Jellyable):
            refId = self._ref_id
            self._ref_id += 1
            preRef = self._checkMutable(obj, refId)
            if preRef:
                return preRef
            return obj.jellyFor(self)
        objType = type(obj)
        if self.taster.isTypeAllowed(
            string.replace(objType.__name__, ' ', '_')):
            # "Immutable" Types
            if ((objType is StringType) or
                (objType is IntType) or
                (objType is LongType) or
                (objType is FloatType)):
                return obj

            refId = self._ref_id
            self._ref_id += 1
            
            if objType is MethodType:
                return ["method",
                        obj.im_func.__name__,
                        self.jelly(obj.im_self),
                        self.jelly(obj.im_class)]

            elif UnicodeType and objType is UnicodeType:
                return ['unicode', obj.encode('UTF-8')]
            elif objType is NoneType:
                return ['None']
            elif objType is FunctionType:
                name = obj.__name__
                return ['function', str(pickle.whichmodule(obj, obj.__name__))
                        + '.' +
                        name]
            elif objType is ModuleType:
                return ['module', obj.__name__]
            elif objType is BooleanType:
                return ['boolean', obj and 'true' or 'false']
            elif objType is ClassType or issubclass(objType, type):
                return ['class', qual(obj)]
            else:
                # "Mutable" Types
                preRef = self._checkMutable(obj, refId)
                if preRef:
                    return preRef
                sxp = []
                if objType is ListType:
                    sxp.append(list_atom)
                    for item in obj:
                        sxp.append(self.jelly(item))
                elif objType is TupleType:
                    sxp.append(tuple_atom)
                    for item in obj:
                        sxp.append(self.jelly(item))
                elif objType in DictTypes:
                    sxp.append(dictionary_atom)
                    for key, val in obj.items():
                        self._ref_id += 1
                        sxp.append([self.jelly(key), self.jelly(val)])
                elif objType is InstanceType:
                    className = qual(obj.__class__)
                    if self.taster.isClassAllowed(obj.__class__):
                        sxp.append(className)
                        if hasattr(obj, "__getstate__"):
                            state = obj.__getstate__()
                        else:
                            state = obj.__dict__
                        sxp.append(self.jelly(state))
                    else:
                        self.unpersistable(
                            "instance of class %s deemed insecure" %
                            qual(obj.__class__), sxp)
                else:
                    raise NotImplementedError("Don't know the type: %s" % objType)
                return sxp
        else:
            if objType is types.InstanceType:
                raise InsecureJelly("Class not allowed for instance: %s %s" %
                                    (obj.__class__, obj))
            raise InsecureJelly("Type not allowed for object: %s %s" %
                                (objType, obj))

    def unpersistable(self, reason, sxp=None):
        '''(internal)
        Returns an sexp: (unpersistable "reason").  Utility method for making
        note that a particular object could not be serialized.
        '''
        if sxp is None:
            sxp = []
        sxp.append(unpersistable_atom)
        sxp.append(reason)
        return sxp


class NullReference(Exception):
    
    """This object is a marker for when a reference is made to an object
    that can't be referenced, i.e.

        (tuple (tuple (reference 1)))

    """

_theNullRef = NullReference()

class _Unjellier:
    def __init__(self, taster, persistentLoad, invoker):
        self.taster = taster
        #self.persistentLoad = persistentLoad  # ignored
        self.references = []
        self.postCallbacks = []
        self.invoker = invoker

    def unjellyFull(self, obj):
        o = self.unjelly(obj)
        for m in self.postCallbacks:
            m()
        return o

    def unjelly(self, obj):
        if type(obj) is not types.ListType:
            return obj
        self.references.append(_theNullRef)
        jelType = obj[0]
        if not self.taster.isTypeAllowed(jelType):
            raise InsecureJelly(jelType)
        regClass = unjellyableRegistry.get(jelType)
        if regClass is not None:
            if isinstance(regClass, ClassType):
                inst = _Dummy() # XXX chomp, chomp
                self.resolveReference(inst)
                inst.__class__ = regClass
                val = inst.unjellyFor(self,obj)
            else:
                refid = self.getRefId()
                self.resolveReference(NotKnown())
                val = regClass(self, obj) # this is how it ought to be done
                self.resolveReference(val, refid)
            if hasattr(val, 'postUnjelly'):
                self.postCallbacks.append(inst.postUnjelly)
            return val
        regFactory = unjellyableFactoryRegistry.get(jelType)
        if regFactory is not None:
            refid = self.getRefId()
            self.resolveReference(NotKnown())
            state = self.unjelly(obj[1])
            inst = regFactory(state)
            if hasattr(inst, 'postUnjelly'):
                self.postCallbacks.append(inst.postUnjelly)
            return self.resolveReference(inst, refid)
        thunk = getattr(self, '_unjelly_%s'%jelType, None)
        if thunk is not None:
            ret = thunk(obj[1:])
        else:
            nameSplit = string.split(jelType, '.')
            modName = string.join(nameSplit[:-1], '.')
            if not self.taster.isModuleAllowed(modName):
                raise InsecureJelly("Module %s not allowed." % modName)
            clz = namedObject(jelType)
            if not self.taster.isClassAllowed(clz):
                raise InsecureJelly("Class %s not allowed." % jelType)
            if hasattr(clz, "__setstate__"):
                ret = instance(clz, {})
                self.resolveReference(ret)
                state = self.unjelly(obj[1])
                ret.__setstate__(state)
            else:
                ret = instance(clz, {})
                self.resolveReference(ret)
                state = self.unjelly(obj[1])
                ret.__dict__ = state
            if hasattr(clz, 'postUnjelly'):
                self.postCallbacks.append(ret.postUnjelly)
        return ret

    def resolveReference(self, obj, index=-1):
        if isinstance(self.references[index], NotKnown):
            assert not isinstance(obj, NotKnown)
            self.references[index].resolveDependants(obj)
        self.references[index] = obj
        return obj

    def _unjelly_None(self, exp):
        return self.resolveReference(None)

    def _unjelly_unicode(self, exp):
        if UnicodeType:
            return self.resolveReference(unicode(exp[0], "UTF-8"))
        else:
            return self.resolveReference(Unpersistable(exp[0]))

    def _unjelly_boolean(self, exp):
        if BooleanType:
            assert exp[0] in ('true', 'false')
            return self.resolveReference(exp[0] == 'true')
        else:
            return self.resolveReference(Unpersistable(exp[0]))

    def unjellyInto(self, obj, loc, jel):
        o = self.unjelly(jel)
        if isinstance(o, NotKnown):
            o.addDependant(obj, loc)
        obj[loc] = o
        return o

    def _unjelly_dereference(self, lst):
        refid = lst[0]
        return self.references[refid]

    def getRefId(self):
        return len(self.references) - 1

    def _unjelly_tuple(self, lst):
        l = [NotKnown()] * len(lst)
        result = None
        preTuple = _Tuple(l)
        refid = self.getRefId()
        self.resolveReference(preTuple)
        for elem in xrange(len(l)):
            self.unjellyInto(preTuple, elem, lst[elem])
        # zero-length tuples are false!!
        # return preTuple.resolvedObject or preTuple
        if preTuple.resolvedObject is None:
            return preTuple
        else:
            return preTuple.resolvedObject
    
    def _unjelly_list(self, lst):
        l = range(len(lst))
        self.resolveReference(l)
        for elem in l:
            self.unjellyInto(l, elem, lst[elem])
        return l

    def _unjelly_dictionary(self, lst):
        d = {}
        self.resolveReference(d)
        for k, v in lst:
            self.references.append(_theNullRef)
            kvd = _DictKeyAndValue(d)
            self.unjellyInto(kvd, 0, k)
            self.unjellyInto(kvd, 1, v)
        return d


    def _unjelly_module(self, rest):
        moduleName = rest[0]
        # if len(rest) > 0: warn("reference numbers will be out of sync")
        if type(moduleName) != types.StringType:
            raise InsecureJelly("Attempted to unjelly a module with a non-string name.")
        if not self.taster.isModuleAllowed(moduleName):
            raise InsecureJelly("Attempted to unjelly module named %s" % repr(moduleName))
        mod = __import__(moduleName, {}, {},"x")
        self.resolveReference(mod)
        return mod

    def _unjelly_class(self, rest):
        clist = string.split(rest[0], '.')
        # if len(rest) > 0: warn("reference numbers will be out of sync")
        modName = string.join(clist[:-1], '.')
        if not self.taster.isModuleAllowed(modName):
            raise InsecureJelly("module %s not allowed" % modName)
        klaus = namedObject(rest[0])
        if type(klaus) is not types.ClassType:
            raise InsecureJelly("class %s unjellied to something that isn't a class: %s" % (repr(name), repr(klaus)))
        if not self.taster.isClassAllowed(klaus):
            raise InsecureJelly("class not allowed: %s" % qual(klaus))
        self.resolveReference(klaus)
        return klaus

    def _unjelly_function(self, rest):
        modSplit = string.split(rest[0], '.')
        # if len(rest) > 0: warn("reference numbers will be out of sync")
        modName = string.join(modSplit[:-1], '.')
        if not self.taster.isModuleAllowed(modName):
            raise InsecureJelly("Module not allowed: %s"% modName)
        # XXX do I need an isFunctionAllowed?
        function = namedObject(rest[0])
        self.resolveReference(function)
        return function

    def _unjelly_unpersistable(self, rest):
        return self.resolveReference(Unpersistable(rest[0]))

    def _unjelly_method(self, rest):
        ''' (internal) unjelly a method
        '''
        nk = NotKnown()
        rid = self.getRefId()
        self.resolveReference(nk)
        im_name = rest[0]
        im_self = self.unjelly(rest[1])
        im_class = self.unjelly(rest[2])
        assert not isinstance(im_self, NotKnown)
        if type(im_class) is not types.ClassType:
            raise InsecureJelly("Method found with non-class class.")
        if im_class.__dict__.has_key(im_name):
            if im_self is None:
                im = getattr(im_class, im_name)
            else:
                im = instancemethod(im_class.__dict__[im_name],
                                    im_self,
                                    im_class)
        else:
            raise 'instance method changed'
        return self.resolveReference(im, rid)


class _Dummy:
    """(Internal)
    Dummy class, used for unserializing instances.
    """




#### Published Interface.


class InsecureJelly(Exception):
    """
    This exception will be raised when a jelly is deemed `insecure'; e.g. it
    contains a type, class, or module disallowed by the specified `taster'
    """



class DummySecurityOptions:
    """DummySecurityOptions() -> insecure security options
    Dummy security options -- this class will allow anything.
    """
    def isModuleAllowed(self, moduleName):
        """DummySecurityOptions.isModuleAllowed(moduleName) -> boolean
        returns 1 if a module by that name is allowed, 0 otherwise
        """
        return 1

    def isClassAllowed(self, klass):
        """DummySecurityOptions.isClassAllowed(class) -> boolean
        Assumes the module has already been allowed.  Returns 1 if the given
        class is allowed, 0 otherwise.
        """
        return 1

    def isTypeAllowed(self, typeName):
        """DummySecurityOptions.isTypeAllowed(typeName) -> boolean
        Returns 1 if the given type is allowed, 0 otherwise.
        """
        return 1



class SecurityOptions:
    """
    This will by default disallow everything, except for 'none'.
    """

    basicTypes = ["dictionary", "list", "tuple",
                  "reference", "dereference", "unpersistable",
                  "persistent", "long_int", "long", "dict"]

    def __init__(self):
        """SecurityOptions()
        Initialize.
        """
        # I don't believe any of these types can ever pose a security hazard,
        # except perhaps "reference"...
        self.allowedTypes = {"None": 1,
                             "bool": 1,
                             "boolean": 1,
                             "string": 1,
                             "str": 1,
                             "int": 1,
                             "float": 1,
                             "NoneType": 1}
        if hasattr(types, 'UnicodeType'):
            self.allowedTypes['unicode'] = 1
        self.allowedModules = {}
        self.allowedClasses = {}

    def allowBasicTypes(self):
        """SecurityOptions.allowBasicTypes()
        Allow all `basic' types.  (Dictionary and list.  Int, string, and float are implicitly allowed.)
        """
        self.allowTypes(*self.basicTypes)

    def allowTypes(self, *types):
        """SecurityOptions.allowTypes(typeString): Allow a particular type, by its name.
        """
        for typ in types:
            self.allowedTypes[string.replace(typ, ' ', '_')]=1

    def allowInstancesOf(self, *classes):
        """SecurityOptions.allowInstances(klass, klass, ...): allow instances
        of the specified classes

        This will also allow the 'instance', 'class' (renamed 'classobj' in
        Python 2.3), and 'module' types, as well as basic types.
        """
        self.allowBasicTypes()
        self.allowTypes("instance", "class", "classobj", "module")
        for klass in classes:
            self.allowTypes(qual(klass))
            self.allowModules(klass.__module__)
            self.allowedClasses[klass] = 1

    def allowModules(self, *modules):
        """SecurityOptions.allowModules(module, module, ...): allow modules by name
        This will also allow the 'module' type.
        """
        for module in modules:
            if type(module) == types.ModuleType:
                module = module.__name__
            self.allowedModules[module] = 1

    def isModuleAllowed(self, moduleName):
        """SecurityOptions.isModuleAllowed(moduleName) -> boolean
        returns 1 if a module by that name is allowed, 0 otherwise
        """
        return self.allowedModules.has_key(moduleName)

    def isClassAllowed(self, klass):
        """SecurityOptions.isClassAllowed(class) -> boolean
        Assumes the module has already been allowed.  Returns 1 if the given
        class is allowed, 0 otherwise.
        """
        return self.allowedClasses.has_key(klass)

    def isTypeAllowed(self, typeName):
        """SecurityOptions.isTypeAllowed(typeName) -> boolean
        Returns 1 if the given type is allowed, 0 otherwise.
        """
        return (self.allowedTypes.has_key(typeName) or
                '.' in typeName)


globalSecurity = SecurityOptions()
globalSecurity.allowBasicTypes()

debugCrap = []

def jelly(object, taster = DummySecurityOptions(), persistentStore=None, invoker=None):
    """Serialize to s-expression.

    Returns a list which is the serialized representation of an object.  An
    optional 'taster' argument takes a SecurityOptions and will mark any
    insecure objects as unpersistable rather than serializing them.
    """
    jr = _Jellier(taster, persistentStore, invoker)
    jel = jr.jelly(object)
    # jr.__dict__.clear()
    return jel


def unjelly(sexp, taster = DummySecurityOptions(), persistentLoad=None, invoker=None):
    """Unserialize from s-expression.

    Takes an list that was the result from a call to jelly() and unserializes
    an arbitrary object from it.  The optional 'taster' argument, an instance
    of SecurityOptions, will cause an InsecureJelly exception to be raised if a
    disallowed type, module, or class attempted to unserialize.
    """
    ujr = _Unjellier(taster, persistentLoad, invoker)
    result = ujr.unjellyFull(sexp)
    # debugCrap.append(ujr.references)
    return result

