

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

class Constraint:
    """
    Each __schema__ attribute is turned into an instance of this class, and
    is eventually given to the unserializer (the 'Unslicer') to enforce as
    the tokens are arriving off the wire.
    """
    pass

class StringConstraint(Constraint):
    def __init__(self, maxLength=1000):
        self.maxLength = maxLength
class BooleanConstraint(Constraint):
    pass
class IntegerConstraint(Constraint):
    def __init__(self, maxValue=2**32):
        self.maxValue = maxValue
class NumberConstraint(Constraint):
    def __init__(self, maxIntValue=2**32):
        self.maxIntValue = maxIntValue
class InterfaceConstraint(Constraint):
    def __init__(self, interface):
        self.interface = interface
class ClassConstraint(Constraint):
    def __init__(self, klass):
        self.klass = klass
class PolyConstraint(Constraint):
    def __init__(self, alternatives):
        self.alternatives = alternatives

class TupleConstraint(Constraint):
    def __init__(self, *elemConstraints):
        self.constraints = elemConstraints
TupleOf = TupleConstraint

class ListConstraint(Constraint):
    """The object must be a list of objects, with a given maximum length. To
    accept lists of any length, use maxLength=None (but you will get a
    UnboundedSchema warning). All member objects must obey the given
    constraint."""
    def __init__(self, constraint, maxLength=30):
        self.constraint = constraint
        self.maxLength = maxLength
ListOf = ListConstraint

class DictConstraint(Constraint):
    def __init__(self, keyconstraint, valueconstraint):
        self.keyconstraint = keyconstraint
        self.valueconstraint = valueconstraint
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
