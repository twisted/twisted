
import string
import pickle
from types import *

from twisted.python.reflect import qual

from twisted.spread import interfaces
from twisted.spread.jelly import *
from twisted.spread.jelly import _Jellier
from twisted.spread import pb

def monkeyJelly(self, obj):
    jobj = interfaces.IJellyable(obj, default=None)
    if jobj is not None:
        preRef = self._checkMutable(obj)
        if preRef:
            return preRef
        return jobj.jellyFor(self)
    objType = type(obj)
    if self.taster.isTypeAllowed(
        string.replace(objType.__name__, ' ', '_')):
        # "Immutable" Types
        if ((objType is StringType) or
            (objType is IntType) or
            (objType is LongType) or
            (objType is FloatType)):
            return obj
        elif objType is MethodType:
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
        elif objType is ClassType or issubclass(type, objType):
            return ['class', qual(obj)]
        else:
            preRef = self._checkMutable(obj)
            if preRef:
                return preRef
            # "Mutable" Types
            sxp = self.prepare(obj)
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
                    sxp.append([self.jelly(key), self.jelly(val)])
            elif objType is InstanceType:
                className = qual(obj.__class__)
                persistent = None
                if self.persistentStore:
                    persistent = self.persistentStore(obj, self)
                if persistent is not None:
                    sxp.append(persistent_atom)
                    sxp.append(persistent)
                elif self.taster.isClassAllowed(obj.__class__):
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
            return self.preserve(obj, sxp)
    else:
        if objType is InstanceType:
            raise InsecureJelly("Class not allowed for instance: %s %s" %
                                (obj.__class__, obj))
        raise InsecureJelly("Type not allowed for object: %s %s" %
                            (objType, obj))

vars(_Jellier)['jelly'] = monkeyJelly
vars(SecurityOptions)['isModuleAllowed'] = lambda self, klass: True
vars(SecurityOptions)['isClassAllowed'] = lambda self, klass: True
vars(SecurityOptions)['isTypeAllowed'] = lambda self, klass: True
