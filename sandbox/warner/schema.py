

"""
primitive constraints:
   types.StringType: string with maxLength=1k
   String(maxLength=1000): string with arbitrary maxLength
   types.BooleanType: boolean
   types.IntType: integer that fits in s_int32_t
   types.LongType: integer with abs(num) < 2**8192 (fits in 1024 bytes)
   Int(maxBytes=1024): integer with arbitrary maxValue=2**(8*maxBytes)
   types.FloatType: number
   Number(maxBytes=1024): float or integer with maxBytes
   interface: instance which implements (or adapts to) the Interface
   class: instance of the class or a subclass
   # unicode? types? none?

container constraints:
   TupleOf(constraint1, constraint2..): fixed size, per-element constraint
   ListOf(constraint, maxLength=30): all elements obey constraint
   DictOf(keyconstraint, valueconstraint): keys and values obey constraints
   AttributeDict(*attrTuples, ignoreUnknown=False):
    attrTuples are (name, constraint)
    ignoreUnknown=True means that received attribute names which aren't
     listed in attrTuples should be ignored instead of raising an
     UnknownAttrName exception

composite constraints:
   tuple: alternatives: must obey one of the different constraints

modifiers:
   Shared(constraint, refLimit=None): object may be referenced multiple times
     within the serialization domain (question: which domain?). All
     constraints default to refLimit=1, and a MultiplyReferenced exception
     is raised as soon as the reference count goes above the limit.
     refLimit=None means no limit is enforced.
   Optional(name, constraint, default=None): key is not required. If not
            provided and default is None, key/attribute will not be created
            Only valid inside DictOf and AttributeDict.
   

"""

import types
from twisted.python import failure

from tokens import Violation, SIZE_LIMIT, STRING, LIST, INT, NEG, \
     LONGINT, LONGNEG, VOCAB, FLOAT, OPEN

everythingTaster = {
    # he likes everything
    STRING: SIZE_LIMIT,
    LIST: None,
    INT: None,
    NEG: None,
    LONGINT: SIZE_LIMIT,
    LONGNEG: SIZE_LIMIT,
    VOCAB: None,
    FLOAT: None,
    OPEN: None,
    }
openTaster = {
    OPEN: None,
    }

class UnboundedSchema(Exception):
    pass

class Constraint:
    """
    Each __schema__ attribute is turned into an instance of this class, and
    is eventually given to the unserializer (the 'Unslicer') to enforce as
    the tokens are arriving off the wire.
    """

    taster = everythingTaster
    """the Taster is a dict that specifies which basic token types are
    accepted. The keys are typebytes like INT and STRING, while the
    values are size limits: the body portion of the token must not be
    longer than LIMIT bytes.
    """

    opentypes = None
    """opentypes is a list of currently acceptable OPEN token types. None
    indicates that all types are accepted. An empty list indicates that no
    OPEN tokens are accepted.
    """

    def checkToken(self, typebyte):
        """Check the token type. Raise an exception if it is not accepted
        right now, or return a body-length limit if it is ok."""
        if not self.taster.has_key(typebyte):
            raise Violation("this primitive type is not accepted right now")
            # really, start discarding instead
        return self.taster[typebyte]

    def setNumberTaster(self, maxValue):
        self.taster = {INT: None,
                       NEG: None,
                       LONGINT: None, # TODO
                       LONGNEG: None,
                       FLOAT: None,
                       }
    def checkOpentype(self, opentype):
        """Check the OPEN type (the tuple of Index Tokens). Raise an
        exception if it is not accepted.
        """
        if self.opentypes == None:
            return
        if opentype not in self.opentypes:
            print "opentype %s, self.opentypes %s" % (opentype,
                                                      self.opentypes)
            raise Violation, "unacceptable OPEN type '%s'" % (opentype,)

    def checkObject(self, obj):
        """Validate an existing object. Usually objects are validated as
        their tokens come off the wire, but pre-existing objects may be
        added to containers if a REFERENCE token arrives which points to
        them. The older objects were were validated as they arrived (by a
        different schema), but now they must be re-validated by the new
        schema.

        A more naive form of validation would just accept the entire object
        tree into memory and then run checkObject() on the result. This
        validation is too late: it is vulnerable to both DoS and
        made-you-run-code attacks.

        This method is also used to validate outbound objects.
        """
        return

    def maxSize(self, seen=None):
        """
        I help a caller determine how much memory could be consumed by the
        input stream while my constraint is in effect.

        My constraint will be enforced against the bytes that arrive over
        the wire. Eventually I will either accept the incoming bytes and my
        Unslicer will provide an object to its parent (including any
        subobjects), or I will raise a Violation exception which will kick
        my Unslicer into 'discard' mode.

        I define maxSizeAccept as the maximum number of bytes that will be
        received before the stream is accepted as valid. maxSizeReject is
        the maximum that will be received before a Violation is raised. The
        max of the two provides an upper bound on single objects. For
        container objects, the upper bound is probably (n-1)*accept +
        reject, because there can only be one outstanding
        about-to-be-rejected object at any time.

        I return (maxSizeAccept, maxSizeReject).

        I raise an UnboundedSchema exception if there is no bound.
        """
        raise UnboundedSchema

    def maxDepth(self):
        """I return the greatest number Slicer objects that might exist on
        the SlicerStack (or Unslicers on the UnslicerStack) while processing
        an object which conforms to this constraint. This is effectively the
        maximum depth of the object tree. I raise UnboundedSchema if there is
        no bound.
        """
        raise UnboundedSchema

Any = Constraint # accept everything


# constraints which describe individual banana tokens

class StringConstraint(Constraint):
    opentypes = [] # redundant, as taster doesn't accept OPEN

    def __init__(self, maxLength=1000):
        self.maxLength = maxLength
        self.taster = {STRING: self.maxLength,
                       VOCAB: None}
    def checkObject(self, obj):
        if not isinstance(obj, types.StringTypes):
            raise Violation
        if self.maxLength != None and len(obj) > self.maxLength:
            raise Violation
    def maxSize(self, seen=None):
        if self.maxLength == None:
            raise UnboundedSchema
        return 64+1+self.maxLength
    def maxDepth(self, seen=None):
        return 1

class IntegerConstraint(Constraint):
    opentypes = [] # redundant
    # taster set in __init__

    def __init__(self, maxBytes=-1):
        # -1 means s_int32_t: INT/NEG instead of INT/NEG/LONGINT/LONGNEG
        # None means unlimited
        assert maxBytes == -1 or maxBytes == None or maxBytes >= 4
        self.maxBytes = maxBytes
        self.taster = {INT: None, NEG: None}
        if maxBytes != -1:
            self.taster[LONGINT] = maxBytes
            self.taster[LONGNEG] = maxBytes

    def checkObject(self, obj):
        if not isinstance(obj, (types.IntType, types.LongType)):
            raise Violation
        if self.maxBytes == -1:
            if obj >= 2**31 or obj < -2**31:
                raise Violation
        elif self.maxBytes != None:
            if abs(obj) >= 2**(8*self.maxBytes):
                raise Violation

    def maxSize(self, seen=None):
        if self.maxBytes == None:
            raise UnboundedSchema
        if self.maxBytes == -1:
            return 64+1
        return 64+1+self.maxBytes
    def maxDepth(self, seen=None):
        return 1

class NumberConstraint(IntegerConstraint):
    def __init__(self, maxBytes=1024):
        assert maxBytes != -1  # not valid here
        IntegerConstraint.__init__(self, maxBytes)
        self.taster[FLOAT] = None

    def checkObject(self, obj):
        if isinstance(obj, types.FloatType):
            return
        IntegerConstraint.checkObject(self, obj)

    def maxSize(self, seen=None):
        # floats are packed into 8 bytes, so the shortest FLOAT token is
        # 64+1+8
        intsize = IntegerConstraint.maxSize(self, seen)
        return max(64+1+8, intsize)
    def maxDepth(self, seen=None):
        return 1

# constraints which describe OPEN sequences

COUNTERBYTES = 64 # max size of opencount

def OPENBYTES(dummy):
    # an OPEN,type,CLOSE sequence could consume:
    #  64 (header)
    #  1 (OPEN)
    #   64 (header)
    #   1 (STRING)
    #   1000 (value)
    #    or
    #   64 (header)
    #   1 (VOCAB)
    #  64 (header)
    #  1 (CLOSE)
    # for a total of 65+1065+65 = 1195
    return COUNTERBYTES+1 + 64+1+1000 + COUNTERBYTES+1


class BooleanConstraint(Constraint):
    taster = openTaster
    opentypes = [("boolean",)]
    _myint = IntegerConstraint()

    def __init__(self, value=None):
        # self.value is a joke. This allows you to use a schema of
        # BooleanConstraint(True) which only accepts 'True'. I cannot
        # imagine a possible use for this, but it made me laugh.
        self.value = value

    def checkObject(self, obj):
        if type(obj) != types.BooleanType:
            raise Violation
        if self.value != None:
            if obj != self.value:
                raise Violation

    def maxSize(self, seen=None):
        if not seen: seen = []
        return OPENBYTES("boolean") + self._myint.maxSize(seen)
    def maxDepth(self, seen=None):
        if not seen: seen = []
        return 1+self._myint.maxDepth(seen)

class InterfaceConstraint(Constraint):
    """This constraint accepts any instance which implements the given
    Interface. The object may be a RemoteCopy if the classname they provide
    maps to a local class which implements the given interface, or it may be
    a RemoteReference if they claim the backing object implements the
    interface.
    """
    # TODO: do we need an string-to-Interface map just like we have a
    # classname-to-class/factory map?
    taster = openTaster
    opentypes = [("instance",)]

    def __init__(self, interface):
        self.interface = interface
    def checkObject(self, obj):
        # TODO: maybe try to get an adapter instead?
        if not implements(obj, self.interface):
            raise Violation

class ClassConstraint(Constraint):
    taster = openTaster
    opentypes = [("instance",)]

    def __init__(self, klass):
        self.klass = klass
    def checkObject(self, obj):
        if not isinstance(obj, self.klass):
            raise Violation

class PolyConstraint(Constraint):
    def __init__(self, *alternatives):
        self.alternatives = [makeConstraint(a) for a in alternatives]
        self.alternatives = tuple(self.alternatives)
        # TODO: taster/opentypes should be a union of the alternatives'
    def checkObject(self, obj):
        ok = False
        for c in self.alternatives:
            try:
                c.checkObject(obj)
                ok = True
            except Violation:
                pass
        if not ok:
            raise Violation
    def maxSize(self, seen=None):
        if not seen: seen = []
        if self in seen:
            # TODO: if the PolyConstraint contains itself directly, the effect
            # is a nop. If a descendent contains the ancestor PolyConstraint,
            # then I think it's unbounded.. must draw this out
            raise UnboundedSchema # recursion
        seen.append(self)
        return reduce(max, [c.maxSize(seen[:])
                            for c in self.alternatives])
    def maxDepth(self, seen=None):
        if not seen: seen = []
        if self in seen:
            raise UnboundedSchema # recursion
        seen.append(self)
        return reduce(max, [c.maxDepth(seen[:]) for c in self.alternatives])

ChoiceOf = PolyConstraint

class TupleConstraint(Constraint):
    taster = openTaster
    opentypes = [("tuple",)]

    def __init__(self, *elemConstraints):
        self.constraints = [makeConstraint(e) for e in elemConstraints]
    def checkObject(self, obj):
        if type(obj) != types.TupleType:
            raise Violation
        if len(obj) != len(self.constraints):
            raise Violation
        for i in range(len(self.constraints)):
            self.constraints[i].checkObject(obj[i])
    def maxSize(self, seen=None):
        if not seen: seen = []
        if self in seen:
            raise UnboundedSchema # recursion
        seen.append(self)
        return OPENBYTES("tuple") + sum([c.maxSize(seen[:])
                                         for c in self.constraints])
    def maxDepth(self, seen=None):
        if not seen: seen = []
        if self in seen:
            raise UnboundedSchema # recursion
        seen.append(self)
        return 1 + reduce(max, [c.maxDepth(seen[:])
                                for c in self.constraints])

TupleOf = TupleConstraint

class ListConstraint(Constraint):
    """The object must be a list of objects, with a given maximum length. To
    accept lists of any length, use maxLength=None (but you will get a
    UnboundedSchema warning). All member objects must obey the given
    constraint."""

    taster = openTaster
    opentypes = [("list",)]

    def __init__(self, constraint, maxLength=30):
        self.constraint = makeConstraint(constraint)
        self.maxLength = maxLength
    def checkObject(self, obj):
        if type(obj) != types.ListType:
            raise Violation
        if len(obj) > self.maxLength:
            raise Violation
        for o in obj:
            self.constraint.checkObject(o)
    def maxSize(self, seen=None):
        if not seen: seen = []
        if self in seen:
            raise UnboundedSchema # recursion
        seen.append(self)
        if self.maxLength == None:
            raise UnboundedSchema
        return (OPENBYTES("list") +
                self.maxLength * self.constraint.maxSize(seen))
    def maxDepth(self, seen=None):
        if not seen: seen = []
        if self in seen:
            raise UnboundedSchema # recursion
        seen.append(self)
        return 1 + self.constraint.maxDepth(seen)

ListOf = ListConstraint

class DictConstraint(Constraint):
    taster = openTaster
    opentypes = [("dict",)]

    def __init__(self, keyConstraint, valueConstraint, maxKeys=30):
        self.keyConstraint = makeConstraint(keyConstraint)
        self.valueConstraint = makeConstraint(valueConstraint)
        self.maxKeys = maxKeys
    def checkObject(self, obj):
        if type(obj) != types.DictType:
            raise Violation, "'%s' (%s) is not a Dictionary" % (obj,
                                                                type(obj))
        if self.maxKeys != None and len(obj) > self.maxKeys:
            raise Violation, "Dict keys=%d > maxKeys=%d" % (len(obj),
                                                            self.maxKeys)
        for key, value in obj.iteritems():
            self.keyConstraint.checkObject(key)
            self.valueConstraint.checkObject(value)
    def maxSize(self, seen=None):
        if not seen: seen = []
        if self in seen:
            raise UnboundedSchema # recursion
        seen.append(self)
        if self.maxKeys == None:
            raise UnboundedSchema
        keySize = self.keyConstraint.maxSize(seen[:])
        valueSize = self.valueConstraint.maxSize(seen[:])
        return OPENBYTES("dict") + self.maxKeys * (keySize + valueSize)
    def maxDepth(self, seen=None):
        if not seen: seen = []
        if self in seen:
            raise UnboundedSchema # recursion
        seen.append(self)
        keyDepth = self.keyConstraint.maxDepth(seen[:])
        valueDepth = self.valueConstraint.maxDepth(seen[:])
        return 1 + max(keyDepth, valueDepth)

DictOf = DictConstraint

class AttributeDictConstraint(Constraint):
    """This is a constraint for dictionaries that are used for attributes.
    All keys are short strings, and each value has a separate constraint.
    It could be used to describe instance state, but could also be used
    to constraint arbitrary dictionaries with string keys.

    Some special constraints are legal here: Optional.
    """
    taster = openTaster
    opentypes = [("attrdict",)]

    def __init__(self, *attrTuples, **kwargs):
        self.ignoreUnknown = kwargs.get('ignoreUnknown', False)
        self.keys = {}
        for name, constraint in (list(attrTuples) +
                                 kwargs.get('attributes', {}).items()):
            assert name not in self.keys.keys()
            self.keys[name] = makeConstraint(constraint)

    def maxSize(self, seen=None):
        if not seen: seen = []
        if self in seen:
            raise UnboundedSchema # recursion
        seen.append(self)
        return OPENBYTES("attributedict") + \
               sum([StringConstraint(len(name)).maxSize(seen) +
                    constraint.maxSize(seen[:])
                    for name, constraint in self.keys.iteritems()])
    def maxDepth(self, seen=None):
        if not seen: seen = []
        if self in seen:
            raise UnboundedSchema # recursion
        seen.append(self)
        # all the attribute names are 1-deep, so the min depth of the dict
        # items is 1. The other "1" is for the AttributeDict container itself
        return 1 + reduce(max, [c.maxDepth(seen[:])
                                for c in self.itervalues()], 1)
    def checkObject(self, obj):
        if type(obj) != type({}):
            raise Violation, "'%s' (%s) is not a Dictionary" % (obj,
                                                                type(obj))
        allkeys = self.keys.keys()
        for k in obj.keys():
            try:
                constraint = self.keys[k]
                allkeys.remove(k)
            except KeyError:
                if not self.ignoreUnknown:
                    raise Violation, "key '%s' not in schema" % k
                else:
                    # hmm. kind of a soft violation. allow it for now.
                    pass
            else:
                constraint.checkObject(obj[k])

        for k in allkeys[:]:
            if isinstance(self.keys[k], Optional):
                allkeys.remove(k)
        if allkeys:
            raise Violation("object is missing required keys: %s" % \
                            ",".join(allkeys))

class MethodArgumentsConstraint(Constraint):
    """This is a constraint for the argument list for a remotely-invokable
    method. It gets to require, deny, or impose further constraints upon a
    set of named arguments.

    This constraint is created by using keyword arguments with the same
    names as the target method's arguments. Two special names are used:

    __ignoreUnknown__: if True, unexpected argument names are silently
    dropped. (note that this makes the schema unbounded)

    __acceptUnknown__: if True, unexpected argument names are always
    accepted without a constraint (which also makes this schema unbounded)

    The remotely-accesible object's .getMethodSchema() method may return one
    of these objects.
    """

    taster = {} # this should not be used as a top-level constraint
    opentypes = [] # overkill
    ignoreUnknown = False
    acceptUnknown = False

    def __init__(self, **kwargs):
        if kwargs.has_key("__ignoreUnknown__"):
            self.ignoreUnknown = kwargs["__ignoreUnknown__"]
            del kwargs["__ignoreUnknown__"]
        if kwargs.has_key("__acceptUnknown__"):
            self.acceptUnknown = kwargs["__acceptUnknown__"]
            del kwargs["__acceptUnknown__"]
        # build up a list of required arguments for later checking
        self.args = {}
        self.required = []
        for argname, constraint in kwargs.items():
            if not isinstance(constraint, Optional):
                self.required.append(argname)
            self.args[argname] = makeConstraint(constraint)

    def getArgConstraint(self, argname):
        if self.args.has_key(argname):
            c = self.args[argname]
            if isinstance(c, Optional):
                c = c.constraint
            return (True, c)
        # what do we do with unknown arguments?
        if self.ignoreUnknown:
            return (False, None)
        if self.acceptUnknown:
            return (True, None)
        raise Violation("unknown argument '%s'" % argname)

    def checkArgs(self, argdict):
        # this is called on the inbound side. Each argument has already been
        # checked individually, so all we have to do is verify global things
        # like all required arguments have been provided.
        for argname in self.required:
            if not argdict.has_key(argname):
                raise Violation("missing required argument '%s'" % argname)

    def checkObject(self, kwargs):
        for argname, argvalue in kwargs.items():
            accept, constraint = self.getArgConstraint(argname)
            if not accept:
                # this argument will be ignored by the far end. TODO: emit a
                # warning
                pass
            constraint.checkObject(argvalue)
        self.checkArgs(kwargs)

    def maxSize(self, seen=None):
        if self.acceptUnknown:
            raise UnboundedSchema # there is no limit on that thing
        if self.ignoreUnknown:
            # for now, we ignore unknown arguments by accepting the object
            # and then throwing it away. This makes us vulnerable to the
            # memory consumed by that object. TODO: in the CallUnslicer,
            # arrange to discard the ignored object instead of receiving it.
            # When this is done, ignoreUnknown will not cause the schema to
            # be unbounded and this clause should be removed.
            raise UnboundedSchema
        # TODO: implement the rest of maxSize, just like a dictionary
        raise NotImplementedError

class RemoteMethodSchema:
    # under development
    def __init__(self):
        self.argumentNames = []
        self.argsConstraint = None
        self.responseConstraint = None
        self.options = {} # return, wait, reliable, etc

    def mapArguments(self, args, kwargs):
        """Create a dictionary of arguments. All positional arguments must
        be turned into keyword ones. All default arguments should be filled
        in (?).
        """
        # python probably provides a utility function for this

        # TODO: this does not really work. Fix it.

        # TODO: this would also be a good place to implement the
        # schema-driven Copyable vs Referenceable decisions
        for i in range(len(args)):
            name = self.argumentNames[i]
            if kwargs.has_key(name):
                raise TypeError(
                    "got multiple values for keyword argument '%s'" % name)
            kwargs[name] = args[i]
        return kwargs

    def getArgsConstraint(self):
        # return a MethodArgumentsConstraint
        return self.argsConstraint

    def getResponseConstraint(self):
        return self.responseConstraint

class RemoteReferenceSchema:
    # under development
    def __init__(self):
        self.methods = {} # values are RemoteMethodSchema instances
    def getMethods(self):
        return self.methods.keys()
    def getMethodSchema(self, methodname):
        return self.methods[methodname]
    


#TODO
class Shared(Constraint):
    def __init__(self, constraint, refLimit=None):
        self.constraint = makeConstraint(constraint)
        self.refLimit = refLimit
    def maxSize(self, seen=None):
        if not seen: seen = []
        if self in seen:
            raise UnboundedSchema # recursion
        seen.append(self)
        return self.constraint.maxSize(seen)
    def maxDepth(self, seen=None):
        if not seen: seen = []
        if self in seen:
            raise UnboundedSchema # recursion
        seen.append(self)
        return self.constraint.maxDepth(seen)

#TODO: might be better implemented with a .optional flag
class Optional(Constraint):
    def __init__(self, constraint, default):
        self.constraint = makeConstraint(constraint)
        self.default = default
    def maxSize(self, seen=None):
        if not seen: seen = []
        if self in seen:
            raise UnboundedSchema # recursion
        seen.append(self)
        return self.constraint.maxSize(seen)
    def maxDepth(self, seen=None):
        if not seen: seen = []
        if self in seen:
            raise UnboundedSchema # recursion
        seen.append(self)
        return self.constraint.maxDepth(seen)

#class FailureConstraint(ClassConstraint):
#    def __init__(self):
#        ClassConstraint.__init__(self, failure.Failure)
FailureConstraint = StringConstraint

def makeConstraint(t):
    if isinstance(t, Constraint):
        return t
    map = {
        types.StringType: StringConstraint(),
        types.BooleanType: BooleanConstraint(),
        types.IntType: IntegerConstraint(),
        types.LongType: IntegerConstraint(maxBytes=1024),
        types.FloatType: NumberConstraint(),
        }
    c = map.get(t, None)
    if c:
        return c
    try:
        if issubclass(t, components.Interface):
            return InterfaceConstraint(t)
    except NameError:
        pass # if t is not a class, issubclass raises an exception
    if isinstance(t, types.ClassType):
        return ClassConstraint(t)

    # alternatives
    if type(t) == types.TupleType:
        return PolyConstraint(*t)

    raise UnknownSchemaType




# how to accept "([(ref0" ?
# X = "TupleOf(ListOf(TupleOf(" * infinity
# ok, so you can't write a constraint that accepts it. I'm ok with that.
