

"""

RemoteReference objects should all be tagged with interfaces that they
implement, which point to representations of the method schemas.  When a remote
method is called, PB should look up the appropriate method and serialize the
argument list accordingly.

We plan to eliminate positional arguments, so local RemoteReferences use their
schema to convert callRemote calls with positional arguments to all-keyword
arguments before serialization.

Conversion to the appropriate version interface should be handled at the
application level.  Eventually, with careful use of twisted.python.context, we
might be able to provide automated tools for helping application authors
automatically convert interface calls and isolate version-conversion code, but
that is probably pretty hard.

"""


class Attributes:
    def __init__(self,*a,**k):
        pass

X = Attributes(
    ('hello', str),
    ('goodbye', int),
    ('next', Shared(Narf)),             # allow the possibility of multiple or circular references
                                        # the default is to make multiple copies
                                        # to avoid making the serializer do extra work
    ('asdf', ListOf(Narf, maxLength=30)),
    ('fdsa', (Narf, String(maxLength=5), int)),
    ('qqqq', DictOf(str, Narf)),
    ('larg', AttributeDict(('A', int),
                           ('X', Number),
                           ('Z', float))),
    Optional("foo", str),
    Optional("bar", str, default=None),
    ignoreUnknown=True,
    )


class Narf(Remoteable):
    # step 1
    __schema__ = X
    # step 2 (possibly - this loses information)
    class schema:
        hello = str
        goodbye = int
        class add:
            x = Number
            y = Number
            __return__ = Copy(Number)

        class getRemoteThingy:
            fooID = Arg(WhateverID, default=None)
            barID = Arg(WhateverID, default=None)
            __return__ = Reference(Narf)

    # step 3 - this is the only example that shows argument order, which we
    # _do_ need in order to translate positional arguments to callRemote, so
    # don't take the nested-classes example too seriously.

    schema = """
    int add (int a, int b)
    """

    # Since the above schema could also be used for Formless, or possibly for
    # World (for state) we can also do:

    class remote_schema:
        """blah blah
        """

    # You could even subclass that from the other one...

    class remote_schema(schema):
        dontUse = 'hello', 'goodbye'

            
    def remote_add(self, x, y):
        return x + y

    def rejuvinate(self, deadPlayer):
        return Reference(deadPlayer.bringToLife())

    # "Remoteable" is a new concept - objects which may be method-published
    # remotely _or_ copied remotely.  The schema objects support both method /
    # interface definitions and state definitions, so which one gets used can
    # be defined by the sending side as to whether it sends a
    # Copy(theRemoteable) or Reference(theRemoteable)

    # (also, with methods that are explicitly published by a schema there is no
    # longer technically any security need for the remote_ prefix, which, based
    # on past experience can be kind of annoying if you want to provide the
    # same methods locally and remotely)

    # outstanding design choice - Referenceable and Copyable are subclasses of
    # Remoteable, but should they restrict the possibility of sending it the
    # other way or 

    def getPlayerInfo(self, playerID):
        return CopyOf(self.players[playerID])

    def getRemoteThingy(self, fooID, barID):
        return ReferenceTo(self.players[selfPlayerID])


class RemoteNarf(Remoted):
    __schema__ = X
    # or, example of a difference between local and remote
    class schema:
        class getRemoteThingy:
            __return__ = Reference(RemoteNarf)
        class movementUpdate:
            posX = int
            posY = int
            __return__ = None           # No return value
            __wait__ = False            # Don't wait for the answer
            __reliable__ = False        # Feel free to send this over UDP
            __ordered__ = True          # but send in order!
            __priority__ = 3            # use priority queue / stream 3
            __failure__ = FullFailure   # allow full serialization of failures
            __failure__ = ErrorMessage  # default: trivial failures, or str or int

            # These options may imply different method names - e.g. '__wait__ =
            # False' might imply that you can't use callRemote, you have to
            # call 'sendRemote' instead... __reliable__ = False might be
            # 'callRemoteUnreliable' (longer method name to make it less
            # convenient to call by accident...)


## (and yes, donovan, we know that TypedInterface exists and we are going to
## use it.  we're just screwing around with other syntaxes to see what about PB
## might be different.)

"""
Common banana sequences:

A reference to a remote object.
   (On the sending side: Referenceable or ReferenceTo(aRemoteable)
    On the receiving side: RemoteReference)
('remote', reference-id, interface, version, interface, version, ...)


A call to a remote method:
('fastcall', request-id, reference-id, method-name, 'arg-name', arg1, 'arg-name', arg2)

A call to a remote method with extra spicy metadata:
('call', request-id, reference-id, interface, version, method-name, 'arg-name', arg1, 'arg-name', arg2)

Special hack: request-id of 0 means 'do not answer this call, do not acknowledge', etc.

Answer to a method call:
('answer', request-id, response)
('error', request-id, response)

Decrement a reference incremented by 'remote' command:
('decref', reference-id)


"""


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
            raise BananaError("this primitive type is not accepted right now"
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

Any = Constraint # accept everything

class StringConstraint(Constraint):
    def __init__(self, maxLength=1000):
        self.maxLength = maxLength
        self.taster = {banana.STRING: self.maxLength}
    def checkObject(self, obj):
        if type(obj) != types.StringTypes:
            raise Violation
        if len(obj) > self.maxLength:
            raise Violation

class BooleanConstraint(Constraint):
    def checkObject(self, obj):
        if type(obj) != types.BooleanType:
            raise Violation

class IntegerConstraint(Constraint):
    def __init__(self, maxValue=2**32):
        self.maxValue = maxValue
        self.setNumberTaster(maxValue)
    def checkObject(self, obj):
        if type(obj) not in (types.IntType, types.LongType):
            raise Violation
        if abs(obj) > self.maxValue:
            raise Violation

class NumberConstraint(Constraint):
    def __init__(self, maxIntValue=2**32):
        self.maxIntValue = maxIntValue
        self.setNumberTaster(maxValue)
    def checkObject(self, obj):
        if type(obj) not in (types.IntType, types.LongType, types.FloatType):
            raise Violation
        if abs(obj) > self.maxValue:
            raise Violation

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
    def __init__(self, alternatives):
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
ListOf = ListConstraint

class DictConstraint(Constraint):
    def __init__(self, keyconstraint, valueconstraint):
        self.keyconstraint = keyconstraint
        self.valueconstraint = valueconstraint
    def checkObject(self, obj):
        if type(obj) != types.DictType:
            raise Violation
        for key, value in obj.iteritems():
            self.keyconstraint.checkObject(key)
            self.valueconstraint.checkObject(value)
DictOf = DictConstraint

class AttributeDictConstraint(Constraint):
    def __init__(self, *attrTuples, ignoreUnknown=False):
        self.keys = {}
        for name, constraint in attrTuples:
            assert name not in self.keys.keys()
            self.keys[name] = makeConstraint(constraint)
        self.ignoreUnknown = ignoreUnknown

class Shared(Constraint):
    def __init__(self, constraint, refLimit=None):
        self.constraint = makeConstraint(constraint)
        self.refLimit = refLimit

class Optional(Constraint):
    def __init__(self, constraint, default):
        self.constraint = makeConstraint(constraint)
        self.default = default



def makeConstraint(t):
    if isinstance(t, Constraint):
        return t
    map = {
        types.StringType: StringConstraint(),
        types.BooleanType: BooleanConstraint(),
        types.IntType: IntegerConstraint()
        types.LongType: IntegerConstraint(maxValue=2**10000)
        types.FloatType: NumberConstraint()
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



class ListUnslicer(BaseUnslicer):
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
        self.itemConstraint.checkToken(typebyte)
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


class ReferenceUnslicer(LeafUnslicer):

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
