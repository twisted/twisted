

"""
primitive constraints:
   types.StringType: string with maxLength=1k
   String(maxLength=1000): string with arbitrary maxLength
   types.BooleanType: boolean
   types.IntType: integer with abs(num) < 2**32 ?
   types.LongType: integer with abs(num) < 2**10000
   Int(maxValue=2**32): integer with arbitrary maxValue
   types.FloatType: number
   Number(maxValue=2**32): float or integer with maxValue
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
import banana, slicer

everythingTaster = {
    banana.STRING: banana.SIZE_LIMIT,
    banana.LIST: None,
    banana.INT: None,
    banana.NEG: None,
    banana.LONGINT: banana.SIZE_LIMIT,
    banana.LONGNEG: banana.SIZE_LIMIT,
    banana.VOCAB: None,
    banana.FLOAT: None,
    banana.OPEN: None,
    banana.CLOSE: None,
    banana.ABORT: None,
    }

class UnboundedSchema(Exception):
    pass

class Violation(Exception):
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
            raise BananaError("this primitive type is not accepted right now")
            # really, start discarding instead
        return self.taster[typebyte]

    def setNumberTaster(self, maxValue):
        self.taster = {banana.INT: None,
                       banana.NEG: None,
                       banana.LONGINT: None, # TODO
                       banana.LONGNEG: None,
                       }
    def checkOpentype(self, opentype):
        """Check the OPEN token type. Raise an exception if it is not
        accepted.
        """
        if self.opentypes == None:
            return
        if opentype not in self.opentypes:
            raise BananaError, "unacceptable OPEN type"

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
        """I return the maximum size (in bytes) which could be consumed by
        the serialized form of an object which conforms to my constraint,
        including all possible sub-objects which I contain. I raise an
        UnboundedSchema exception if there is no bound.
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
    def __init__(self, maxLength=1000):
        self.maxLength = maxLength
        self.taster = {banana.STRING: self.maxLength}
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
    def __init__(self, maxValue=2**32):
        self.maxValue = maxValue
        self.setNumberTaster(maxValue)
    def checkObject(self, obj):
        if not isinstance(obj, (types.IntType, types.LongType)):
            raise Violation
        if abs(obj) > self.maxValue:
            raise Violation
    def maxSize(self, seen=None):
        # TODO: not 8, log256(self.maxValue)
        return 64+1+8
    def maxDepth(self, seen=None):
        return 1

class SmallIntegerConstraint(IntegerConstraint):
    def __init__(self):
        self.maxValue = 2**32

class NumberConstraint(Constraint):
    def __init__(self, maxIntValue=2**32):
        self.maxIntValue = maxIntValue
        self.setNumberTaster(maxValue)
    def checkObject(self, obj):
        if not isinstance(obj, (types.IntType, types.LongType,
                                types.FloatType)):
            raise Violation
        if abs(obj) > self.maxValue:
            raise Violation
    def maxSize(self, seen=None):
        # TODO: same as IntegerConstraint
        return 64+1+8
    def maxDepth(self, seen=None):
        return 1

# constraints which describe OPEN sequences

COUNTERBYTES = 0 # max size of opencount

def OPENBYTES(name=None):
    # an OPEN,type,CLOSE sequence takes:
    if name == None:
        strlen = StringConstraint().maxSize(None)
    else:
        strlen = StringConstraint(len(name)).maxSize(None)
    return COUNTERBYTES+1 + strlen + COUNTERBYTES+1


class BooleanConstraint(Constraint):
    taster = {banana.INT: 2**32}
    opentypes = []
    _myint = SmallIntegerConstraint()

    def checkObject(self, obj):
        if type(obj) != types.BooleanType:
            raise Violation
    def maxSize(self, seen=None):
        if not seen: seen = []
        return OPENBYTES("boolean") + self._myint.maxSize(seen)
    def maxDepth(self, seen=None):
        if not seen: seen = []
        return 1+self._myint.maxDepth(seen)

class InterfaceConstraint(Constraint):
    def __init__(self, interface):
        self.interface = interface
    def checkObject(self, obj):
        # TODO: maybe try to get an adapter instead?
        if not implements(obj, self.interface):
            raise Violation

class ClassConstraint(Constraint):
    def __init__(self, klass):
        self.klass = klass
class PolyConstraint(Constraint):
    def __init__(self, *alternatives):
        self.alternatives = alternatives
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
    def __init__(self, *elemConstraints):
        self.constraints = elemConstraints
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
    def __init__(self, constraint, maxLength=30):
        self.constraint = constraint
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
    def __init__(self, keyconstraint, valueconstraint, maxKeys=30):
        self.keyconstraint = keyconstraint
        self.valueconstraint = valueconstraint
        self.maxKeys = maxKeys
    def checkObject(self, obj):
        if type(obj) != types.DictType:
            raise Violation
        for key, value in obj.iteritems():
            self.keyconstraint.checkObject(key)
            self.valueconstraint.checkObject(value)
    def maxSize(self, seen=None):
        if not seen: seen = []
        if self in seen:
            raise UnboundedSchema # recursion
        seen.append(self)
        if self.maxKeys == None:
            raise UnboundedSchema
        keySize = self.keyconstraint.maxSize(seen[:])
        valueSize = self.valueconstraint.maxSize(seen[:])
        return OPENBYTES("dict") + self.maxKeys * (keySize + valueSize)
    def maxDepth(self, seen=None):
        if not seen: seen = []
        if self in seen:
            raise UnboundedSchema # recursion
        seen.append(self)
        keyDepth = self.keyconstraint.maxDepth(seen[:])
        valueDepth = self.valueconstraint.maxDepth(seen[:])
        return 1 + max(keyDepth, valueDepth)

DictOf = DictConstraint

class AttributeDictConstraint(Constraint):
    def __init__(self, ignoreUnknown=False, *attrTuples):
        self.keys = {}
        for name, constraint in attrTuples:
            assert name not in self.keys.keys()
            self.keys[name] = makeConstraint(constraint)
        self.ignoreUnknown = ignoreUnknown
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



def makeConstraint(t):
    if isinstance(t, Constraint):
        return t
    map = {
        types.StringType: StringConstraint(),
        types.BooleanType: BooleanConstraint(),
        types.IntType: IntegerConstraint(),
        types.LongType: IntegerConstraint(maxValue=2**10000),
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
        return PolyConstraint(t)

    raise UnknownSchemaType



class ListUnslicer(slicer.BaseUnslicer):
    constraint = Any()
    # .opener usually chains to RootUnslicer.opener
    # .constraint is populated by our creator (in doOpen)

    def start(self, count):
        #self.opener = foo # could replace it if we wanted to
        assert isinstance(self.constraint, ListConstraint)
        self.maxLength = self.constraint.maxLength
        self.itemConstraint = self.constraint.constraint

        self.list = []
        self.protocol.setObject(count, self.list)

    def checkToken(self, typebyte):
        return self.itemConstraint.checkToken(typebyte)
    def checkOpentype(self, opentype):
        self.itemConstraint.checkOpentype(opentype)

    def doOpen(self, opentype):
        # decide whether the given object type is acceptable here. Raise a
        # Violation exception if not, otherwise give it to our opener (which
        # will normally be the RootUnslicer). Apply a constraint to the new
        # unslicer.
        if self.maxLength != None and len(self.list) >= self.maxLength:
            # this is hit if the max+1 item is a non-primitive type
            raise Violation
        self.itemConstraint.checkOpentype(opentype)
        unslicer = self.opener(opentype)
        unslicer.constraint = self.itemConstraint
        unslicer.opener = self.opener
        return unslicer

    def receiveChild(self, obj):
        # obj could be a primitive type, a Deferred, or a complex type like
        # those returned from an InstanceUnslicer. However, the individual
        # object has already been through the schema validation process. The
        # only remaining question is whether the larger schema will accept
        # it.
        if self.maxLength != None and len(self.list) >= self.maxLength:
            # this is hit if the max+1 item is a primitive type
            # (if it were a non-primitive one, it would be caught in doOpen)
            raise Violation
        if isinstance(obj, Deferred):
            obj.addCallback(self.update, len(self.list))
            obj.addErrback(self.printErr)
            self.list.append(None) # placeholder
            return
        self.list.append(token)

    def update(self, obj, index):
        # obj has already passed typechecking
        assert(type(index) == types.IntType)
        self.list[index] = obj

    def receiveClose(self):
        return self.list

    def describe(self):
        return "[%d]" % len(self.list)


class ReferenceUnslicer(slicer.LeafUnslicer):

    def receiveToken(self, token):
        if hasattr(self, 'obj'):
            raise ValueError, "'reference' token already got number"
        if type(token) != types.IntType:
            raise ValueError, "'reference' token requires integer"
        self.obj = self.protocol.getObject(token)
        # assert that this conforms to the constraint
        self.constraint.checkObject(self.obj)
        # TODO: it might be a Deferred, but we should know enough about the
        # incoming value to check the constraint. This requires a subclass
        # of Deferred which can give us the metadata.

    def receiveClose(self):
        return self.obj


# how to accept "([(ref0" ?
# X = "TupleOf(ListOf(TupleOf(" * infinity
# ok, so you can't write a constraint that accepts it. I'm ok with that.
