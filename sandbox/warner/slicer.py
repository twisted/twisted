#! /usr/bin/python

import types
from pickle import whichmodule  # used by FunctionSlicer
from new import instance, instancemethod

from twisted.python.failure import Failure
from twisted.internet.defer import Deferred
from twisted.python import log, reflect

from tokens import Violation
import schema

class IBananaSlicer:
    def sendOpen(self, opentype):
        """Send an Open(type) token. Must be matched with a sendClose.
        opentype must be a string."""
    def sendToken(self, token):
        """Send a token. Must be a number or a string"""
    def sendClose(self):
        """Send a Close token."""
class IJellying:
    def JellyYourBadSelf(self, banana):
        """Send banana tokens to banana by calling IBananaSender methods"""
    def description(self):
        """Return a short string describing where in the object tree this
        jellier is sitting. A list of these strings will be used to describe
        where any problems occurred."""

def getInstanceState(inst):
    """Utility function to default to 'normal' state rules in serialization.
    """
    if hasattr(inst, "__getstate__"):
        state = inst.__getstate__()
    else:
        state = inst.__dict__
    return state

SimpleTokens = (types.IntType, types.LongType, types.FloatType,
                types.StringType)

class BaseSlicer:
    opentype = None
    trackReferences = 0

    def __init__(self):
        self.openID = None

    def describe(self):
        return "??"

    # start/slice/finish are the main "serialize yourself" entry points used
    # by Banana

    def send(self, obj):
        # utility function
        if self.protocol.debug:
            print "BaseSlicer.send(%s{%s})" % (obj, type(obj))
        if type(obj) in SimpleTokens:
            if self.protocol.debug:
                print " was in SimpleTokens"
            self.protocol.sendToken(obj)
        else:
            if self.protocol.debug:
                print " not in SimpleTokens"
            self.protocol.slice(obj)
            # does life stop while we wait for this?

    def start(self, obj):
        # refid is for reference tracking
        assert(self.openID == None)
        self.openID = self.protocol.sendOpen(self.opentype)
        if self.trackReferences:
            self.protocol.setRefID(obj, self.openID)

    def slice(self, obj):
        """Tokenize the object and send the tokens via
        self.protocol.sendToken(). Will be called after open() and before
        finish().
        """
        raise NotImplementedError

    def finish(self, obj):
        assert(self.openID is not None)
        self.protocol.sendClose(self.openID)
        self.openID = None

    def abort(self):
        """Stop trying to tokenize the object. Send an ABORT token, then a
        CLOSE. Producers may want to hook this to free up other resources,
        etc.
        """
        self.protocol.sendAbort()
        self.protocol.sendClose()


    # newSlicer/taste/setRefID/getRefID are the other functions of the Slice
    # stack

    def newSlicer(self, obj):
        """Return an IBananaSlicer object based upon the type of the object
        being serialized. This object will be asked to do start(), slice(),
        and finish(). The entire Slicer stack is asked for an object: the
        first slice that returns something other than None will stop the
        search.
        """
        return None

    def taste(self, obj):
        """All Slicers in the stack get to pass judgement upon the outgoing
        object. If they don't like that they see, they should raise an
        InsecureBanana exception.
        """
        pass

    def setRefID(self, obj, refid):
        """To pass references to previously-sent objects, the [OPEN,
        'reference', number, CLOSE] sequence is used. The numbers are
        generated implicitly by the sending Banana, counting from 0 for the
        object described by the very first OPEN sent over the wire,
        incrementing for each subsequent one. The objects themselves are
        stored in any/all Slicers who cares to. Generally this is the
        RootSlicer, but child slices could do it too if they wished.
        """
        pass

    def getRefID(self, obj):
        """'None' means 'ask our parent instead'.
        """
        return None

class UnicodeSlicer(BaseSlicer):
    opentype = 'unicode'
    trackReferences = 0

    def slice(self, obj):
        self.send(obj.encode('UTF-8'))

class ListSlicer(BaseSlicer):
    opentype = 'list'
    trackReferences = 1

    # it would be useful if this could behave more consumer/producerish.
    # maybe NOT_DONE_YET? Generators?

    def slice(self, obj):
        for elem in obj:
            self.send(elem)

class TupleSlicer(ListSlicer):
    opentype = 'tuple'

class DictSlicer(BaseSlicer):
    opentype = 'dict'
    trackReferences = 1

    def slice(self, obj):
        for key,value in obj.items():
            self.send(key)
            self.send(value)

class OrderedDictSlicer(BaseSlicer):
    opentype = 'dict'
    trackReferences = 1

    def slice(self, obj):
        keys = obj.keys()
        keys.sort()
        for key in keys:
            value = obj[key]
            self.send(key)
            self.send(value)

class VocabSlicer(OrderedDictSlicer):
    opentype = 'vocab'
    trackReferences = 0

class InstanceSlicer(OrderedDictSlicer):
    opentype = 'instance'
    trackReferences = 1

    def slice(self, obj):
        self.protocol.sendToken(reflect.qual(obj.__class__))
        OrderedDictSlicer.slice(self, getInstanceState(obj)) #DictSlicer

class ModuleSlicer(BaseSlicer):
    opentype = 'module'
    trackReferences = 1

    def slice(self, obj):
        self.send(obj.__name__)

class ClassSlicer(BaseSlicer):
    opentype = 'class'
    trackReferences = 1

    def slice(self, obj):
        self.send(reflect.qual(obj))

class MethodSlicer(BaseSlicer):
    opentype = 'method'
    trackReferences = 1

    def slice(self, obj):
        self.send(obj.im_func.__name__)
        self.send(obj.im_self)
        self.send(obj.im_class)

class FunctionSlicer(BaseSlicer):
    opentype = 'function'
    trackReferences = 1

    def slice(self, obj):
        name = obj.__name__
        fullname = str(whichmodule(obj, obj.__name__)) + '.' + name
        self.send(fullname)

class NoneSlicer(BaseSlicer):
    opentype = 'none'
    trackReferences = 0

    def slice(self, obj):
        pass

class BooleanSlicer(BaseSlicer):
    opentype = 'boolean'
    trackReferences = 0

    def slice(self, obj):
        if obj:
            self.send(1)
        else:
            self.send(0)


class ReferenceSlicer(BaseSlicer):
    opentype = 'reference'

    def __init__(self, refid):
        BaseSlicer.__init__(self)
        assert(type(refid) == types.IntType)
        self.refid = refid

    def slice(self, obj):
        self.protocol.sendToken(self.refid)

class RootSlicer(BaseSlicer):
    # this lives at the bottom of the Slicer stack, at least for our testing
    # purposes

    def __init__(self):
        self.references = {}

    def start(self, obj):
        self.references = {}

    def slice(self, obj):
        self.protocol.slice(obj)

    def finish(self, obj):
        self.references = {}

    def newSlicer(self, obj):
        refid = self.protocol.getRefID(obj)
        if refid is not None:
            slicer = ReferenceSlicer(refid)
            return slicer
        slicerClass = SlicerRegistry.get(type(obj))
        if not slicerClass:
            raise KeyError, "I don't know how to slice %s" % type(obj)
        slicer = slicerClass()
        return slicer


    def setRefID(self, obj, refid):
        if self.protocol.debug:
            print "setRefID(%s{%s}) -> %s" % (obj, id(obj), refid)
        self.references[id(obj)] = refid

    def getRefID(self, obj):
        refid = self.references.get(id(obj))
        if self.protocol.debug:
            print "getObject(%s{%s}) -> %s" % (obj, id(obj), refid)
        return refid

class RootSlicer2(RootSlicer):

    def newSlicer(self, obj):
        refid = self.protocol.getRefID(obj)
        if refid is not None:
            slicer = ReferenceSlicer(refid)
            return slicer
        slicerClass = SlicerRegistry2.get(type(obj))
        if not slicerClass:
            if issubclass(type(obj), type):
                slicerClass = ClassSlicer
        if not slicerClass:
            raise KeyError, "I don't know how to slice %s" % type(obj)
        slicer = slicerClass()
        return slicer
    
SlicerRegistry = {
    types.UnicodeType: UnicodeSlicer,
    types.ListType: ListSlicer,
    types.TupleType: TupleSlicer,
    types.DictType: OrderedDictSlicer, #DictSlicer
    types.InstanceType: InstanceSlicer,
    types.NoneType: NoneSlicer,
    }

try:
    from types import BooleanType
    SlicerRegistry[BooleanType] = BooleanSlicer
except ImportError:
    pass

SlicerRegistry2 = {}
SlicerRegistry2.update(SlicerRegistry)
SlicerRegistry2.update({
    types.ModuleType: ModuleSlicer,
    types.ClassType: ClassSlicer,
    types.MethodType: MethodSlicer,
    types.FunctionType: FunctionSlicer,
    })



class IBananaUnslicer:
    # .parent

    # start/receiveChild/receiveClose/finish are
    # the main "here are some tokens, make an object out of them" entry
    # points used by Unbanana.

    # start/receiveChild can call self.protocol.abandonUnslicer(failure,
    # self) to tell the protocol that the unslicer has given up on life and
    # all its remaining tokens should be discarded. The failure will be
    # given to the late unslicer's parent in lieu of the object normally
    # returned by receiveClose.
    
    # start/receiveChild/receiveClose/finish may raise a Violation
    # exception, which tells the protocol that this object is contaminated
    # and should be abandoned. An UnbananaFailure will be passed to its
    # parent.

    # Note, however, that it is not valid to both call abandonUnslicer *and*
    # raise a Violation. That would discard too much.

    def setConstraint(self, constraint):
        """Add a constraint for this unslicer. The unslicer will enforce
        this constraint upon all incoming data. The constraint must be of an
        appropriate type (a ListUnslicer will only accept a ListConstraint,
        etc). It must not be None.

        If this function is not called, the Unslicer will accept any valid
        banana as input, which probably means there is no limit on the
        number of bytes it will accept (and therefore on the memory it could
        be made to consume) before it finally accepts or rejects the input.
        """

    def start(self, count):
        """Called to initialize the new slice. The 'count' argument is the
        reference id: if this object might be shared (and therefore the
        target of a 'reference' token), it should call
        self.protocol.setObject(count, obj) with the object being created.
        If this object is not available yet (tuples), it should save a
        Deferred there instead.
        """

    def checkToken(self, typebyte):
        """Check to see if the given token is acceptable (does it conform to
        the constraint?). It will not be asked about ABORT or CLOSE tokens,
        but it *will* be asked about OPEN. It should return a length limit
        for long tokens (STRING and LONGINT/LONGNEG types). If STRING is
        acceptable, then VOCAB should be too. A return value of None
        indicates that unlimited lengths are acceptable. Should raise
        Violation if the schema indiates the token is not acceptable. Should
        raise UnbananaError if the type byte violates the basic Banana
        protocol. (if no schema is in effect, this should never raise
        Violation, but might still raise UnbananaError).
        """

    def doOpen(self, opentype):
        """Opentype is a string. Check to see if this kind of child object
        conforms to the constraint, raise Violation if not. Create a new
        Unslicer (usually by calling self.opener, which chains back to the
        RootUnslicer). Set a constraint on the child unslicer, if any. Set
        the child's .opener attribute (usually to self.opener).
        """

    def receiveChild(self, childobject):
        """'childobject' is being handed to this unslicer. It may be a
        primitive type (number or string), or a composite type produced by
        another Unslicer. It might be an UnbananaFailure if something went
        wrong, in which case it may be appropriate to do
        self.protocol.abandonUnslicer(failure, self). It might also be a
        Deferred, in which case you should add a callback that will fill in
        the appropriate object later."""

    def receiveClose(self):
        """Called when the Close token is received. Should return the object
        just created, or an UnbananaFailure if something went wrong. If
        necessary, unbanana.setObject should be called, then the Deferred
        created in start() should be fired with the new object."""

    def finish(self):
        """Called when the unslicer is popped off the stack. This is called
        even if the pop is because of an exception. The unslicer should
        perform cleanup, including firing the Deferred with an
        UnbananaFailure if the object it is creating could not be created.

        TODO: can receiveClose and finish be merged? Or should the child
        object be returned from finish() instead of receiveClose?
        """

    def description(self):
        """Return a short string describing where in the object tree this
        unslicer is sitting, relative to its parent. These strings are
        obtained from every unslicer in the stack, and joined to describe
        where any problems occurred."""



class UnbananaFailure:
    def __init__(self, where="<unknown>", failure=None):
        self.where = where
        self.failure = failure
    def __repr__(self):
        return "<%s at: %s>" % (self.__class__, self.where)

def setInstanceState(inst, state):
    """Utility function to default to 'normal' state rules in unserialization.
    """
    if hasattr(inst, "__setstate__"):
        inst.__setstate__(state)
    else:
        inst.__dict__ = state
    return inst

class BaseUnslicer:
    def __init__(self):
        pass

    def describe(self):
        return "??"


    def setConstraint(self, constraint):
        pass

    def start(self, count):
        pass

    def checkToken(self, typebyte):
        return None # unlimited

    def doOpen(self, opentype):
        """Return an IBananaUnslicer object based upon the 'opentype'
        string. This object will receive all tokens destined for the
        subnode.
        """
        raise NotImplementedError

    def receiveChild(self, obj):
        pass

    def receiveClose(self):
        raise NotImplementedError

    def finish(self):
        pass

    def setObject(self, counter, obj):
        """To pass references to previously-sent objects, the [OPEN,
        'reference', number, CLOSE] sequence is used. The numbers are
        generated implicitly by the sending Banana, counting from 0 for the
        object described by the very first OPEN sent over the wire,
        incrementing for each subsequent one. The objects themselves are
        stored in any/all Unslicers who cares to. Generally this is the
        RootUnslicer, but child slices could do it too if they wished.
        """
        pass

    def getObject(self, counter):
        """'None' means 'ask our parent instead'.
        """
        return None

class LeafUnslicer(BaseUnslicer):
    # inherit from this to reject any child nodes

    # checkToken should reject OPEN tokens

    def doOpen(self, opentype):
        raise Violation, "'%s' does not accept sub-objects" % self

class UnicodeUnslicer(BaseUnslicer):
    # accept a UTF-8 encoded string
    string = None
    constraint = None
    def setConstraint(self, constraint):
        assert isinstance(constraint, schema.StringConstraint)
        self.constraint = constraint

    def checkToken(self, typebyte):
        if typebyte != tokens.STRING:
            raise BananaError("UnicideUnslicer only accepts strings")
        if self.constraint:
            return self.constraint.checkToken(typebyte)
        return None # no size limit

    def receiveToken(self, token):

    def receiveChild(self, obj):
        if self.string != None:
            raise BananaError("already received a string")
        self.string = unicode(obj, "UTF-8")
    def receiveClose(self):
        return self.string
    def describe(self):
        return "<unicode>"

class ListUnslicer(BaseUnslicer):
    maxLength = None
    itemConstraint = None
    # .opener usually chains to RootUnslicer.opener
    debug = False

    def setConstraint(self, constraint):
        assert isinstance(constraint, schema.ListConstraint)
        self.maxLength = constraint.maxLength
        self.itemConstraint = constraint.constraint
        print "itemConstraint", self.itemConstraint

    def start(self, count):
        #self.opener = foo # could replace it if we wanted to
        self.list = []
        self.count = count
        if self.debug:
            print "%s[%d].start with %s" % (self, self.count, self.list)
        self.protocol.setObject(count, self.list)

    def checkToken(self, typebyte):
        if self.maxLength != None and len(self.list) >= self.maxLength:
            # list is full, no more tokens accepted
            # this is hit if the max+1 item is a primitive type
            raise Violation
        if self.itemConstraint:
            return self.itemConstraint.checkToken(typebyte)
        return None # unlimited

    def doOpen(self, opentype):
        # decide whether the given object type is acceptable here. Raise a
        # Violation exception if not, otherwise give it to our opener (which
        # will normally be the RootUnslicer). Apply a constraint to the new
        # unslicer.
        if self.maxLength != None and len(self.list) >= self.maxLength:
            # this is hit if the max+1 item is a non-primitive type
            raise Violation
        if self.itemConstraint:
            self.itemConstraint.checkOpentype(opentype)
        unslicer = self.opener(opentype)
        if self.itemConstraint:
            unslicer.setConstraint(self.itemConstraint)
        unslicer.opener = self.opener
        return unslicer

    def update(self, obj, index):
        # obj has already passed typechecking
        if self.debug:
            print "%s[%d].update: [%d]=%s" % (self, self.count, index, obj)
        assert(type(index) == types.IntType)
        self.list[index] = obj

#    def receiveToken(self, token):
#        if self.protocol.debug or self.debug:
#            print "%s[%d].receiveToken(%s{%s})" % (self, self.count,
#                                                   token, id(token))
#        self.list.append(token)

    def receiveChild(self, obj):
        if self.debug:
            print "%s[%d].receiveChild(%s)" % (self, self.count, obj)
        # obj could be a primitive type, a Deferred, or a complex type like
        # those returned from an InstanceUnslicer. However, the individual
        # object has already been through the schema validation process. The
        # only remaining question is whether the larger schema will accept
        # it. It could also be an UnbananaFailure (if the subobject were
        # aborted or if it violated the schema).
        if self.maxLength != None and len(self.list) >= self.maxLength:
            # this is redundant
            # (if it were a non-primitive one, it would be caught in doOpen)
            # (if it were a primitive one, it would be caught in checkToken)
            raise Violation
        if isinstance(obj, Deferred):
            if self.debug:
                print " adding my update[%d] to %s" % (len(self.list), obj)
            obj.addCallback(self.update, len(self.list))
            obj.addErrback(self.printErr)
            self.list.append(None) # placeholder
        elif isinstance(obj, UnbananaFailure):
            self.protocol.startDiscarding(obj, self)
        else:
            self.list.append(obj)

    def printErr(self, why):
        print "ERR!"
        print why.getBriefTraceback()
        log.err(why)

    def receiveClose(self):
        return self.list

    def describe(self):
        return "[%d]" % len(self.list)

class TupleUnslicer(ListUnslicer):
    debug = 0

    def start(self, count):
        self.list = []
        self.stoppedAdding = 0
        self.deferred = Deferred()
        self.count = count
        if self.debug:
            print "%s[%d].start with %s" % (self, self.count, self.deferred)
        self.protocol.setObject(count, self.deferred)

    def update(self, obj, index):
        if self.debug:
            print "%s[%d].update: [%d]=%s" % (self, self.count, index, obj)
        assert(type(index) == types.IntType)
        self.list[index] = obj
        if self.stoppedAdding:
            self.checkComplete()

    def checkComplete(self):
        if self.debug:
            print "%s[%d].checkComplete" % (self, self.count)
        for i in self.list:
            if isinstance(i, Deferred):
                # not finished yet, we'll fire our Deferred when we are
                if self.debug:
                    print " not finished yet"
                return self.deferred
        # list is now complete. We can finish.
        t = tuple(self.list)
        if self.debug:
            print " finished! tuple:%s{%s}" % (t, id(t))
        self.protocol.setObject(self.count, t)
        self.deferred.callback(t)
        return t

    def receiveClose(self):
        if self.debug:
            print "%s[%d].receiveClose" % (self, self.count)
        self.stoppedAdding = 1
        return self.checkComplete()


class DictUnslicer(BaseUnslicer):
    haveKey = 0

    def start(self, count):
        self.d = {}
        self.protocol.setObject(count, self.d)
        self.key = None

    def receiveToken(self, token):
        if not self.haveKey:
            if self.d.has_key(token):
                raise ValueError, "duplicate key '%s'" % token
            self.key = token
            self.haveKey = 1
        else:
            self.d[self.key] = token
            self.haveKey = 0

    def receiveChild(self, obj):
        if isinstance(obj, Deferred):
            assert(self.haveKey)
            obj.addCallback(self.update, self.key)
            obj.addErrback(log.err)
        self.receiveToken(obj)

    def update(self, obj, key):
        self.d[key] = obj


    def receiveClose(self):
        return self.d

    def describe(self):
        if self.haveKey:
            return "{}[%s]" % self.key
        else:
            return "{}"

class NewVocabulary:
    def __init__(self, newvocab):
        self.nv = newvocab

class VocabUnslicer(LeafUnslicer):
    """Much like DictUnslicer, but keys must be numbers, and values must
    be strings"""
    
    def start(self, count):
        self.d = {}
        self.haveKey = 0
        self.key = None

    def receiveToken(self, token):
        if not self.haveKey:
            if self.d.has_key(token):
                raise ValueError, "duplicate key '%s'" % token
            if not isinstance(token, types.IntType):
                raise ValueError, "VOCAB key '%s' must be a number" % token
            self.key = token
            self.haveKey = 1
        else:
            if not isinstance(token, types.StringType):
                raise ValueError, "VOCAB value '%s' must be a string" % token
            self.d[self.key] = token
            self.haveKey = 0

    def receiveClose(self):
        return NewVocabulary(self.d)

    def describe(self):
        if self.haveKey:
            return "<vocabdict>[%s]" % self.key
        else:
            return "<vocabdict>"


class BrokenDictUnslicer(DictUnslicer):
    dieInFinish = 0
    dieInReceiveChild = 0

    def receiveToken(self, token):
        if token == "die":
            raise "aaaaaaaaargh"
        if token == "please_die_in_finish":
            self.dieInFinish = 1
        if token == "please_die_in_receiveChild":
            self.dieInReceiveChild = 1
        DictUnslicer.receiveToken(self, token)

    def receiveChild(self, obj):
        if self.dieInReceiveChild:
            raise "dead in receiveChild"
        DictUnslicer.receiveChild(self, obj)

    def receiveClose(self):
        if self.dieInFinish:
            raise "dead in receiveClose()"
        DictUnslicer.receiveClose(self)

class ReallyBrokenDictUnslicer(DictUnslicer):
    def start(self, count):
        raise "dead in start"


class Dummy:
    def __repr__(self):
        return "<Dummy %s>" % self.__dict__
    def __cmp__(self, other):
        if not type(other) == type(self):
            return -1
        return cmp(self.__dict__, other.__dict__)


class InstanceUnslicer(DictUnslicer):

    def start(self, count):
        self.d = {}
        self.deferred = Deferred()
        self.count = count
        self.protocol.setObject(count, self.deferred)
        self.classname = None
        # push something to indicate that we only accept strings as
        # classname or keys

    def receiveToken(self, token):
        if self.classname == None:
            if type(token) != types.StringType:
                raise ValueError, "classname must be string, not '%s'" % token
            self.classname = token
        else:
            DictUnslicer.receiveToken(self, token)

    def receiveChild(self, obj):
        # TODO: handle isinstance(obj, Deferred)
        self.receiveToken(obj)

    def receiveClose(self):
        o = Dummy()
        #o.__classname__ = self.classname
        setInstanceState(o, self.d)
        self.protocol.setObject(self.count, o)
        self.deferred.callback(o)
        return o

    def describe(self):
        if self.classname == None:
            return "<??>"
        me = "<%s>" % self.classname
        if self.haveKey:
            return "%s.%s" % (me, self.key)
        return "%s.attrname??" % me

class InstanceUnslicer2(InstanceUnslicer):

    def receiveClose(self):
        # TODO: taste me!
        klass = reflect.namedObject(self.classname)
        assert type(klass) == types.ClassType # TODO: new-style classes
        o = instance(klass, {})
        setInstanceState(o, self.d)
        self.protocol.setObject(self.count, o)
        self.deferred.callback(o)
        return o
    

class ReferenceUnslicer(LeafUnslicer):
    constraint = None
    def receiveToken(self, token):
        if hasattr(self, 'obj'):
            raise ValueError, "'reference' token already got number"
        if type(token) != types.IntType:
            raise ValueError, "'reference' token requires integer"
        self.obj = self.protocol.getObject(token)
        # assert that this conforms to the constraint
        if self.constraint:
            self.constraint.checkObject(self.obj)
        # TODO: it might be a Deferred, but we should know enough about the
        # incoming value to check the constraint. This requires a subclass
        # of Deferred which can give us the metadata.

    def receiveClose(self):
        return self.obj

class ModuleUnslicer(LeafUnslicer):
    def receiveToken(self, token):
        assert type(token) == types.StringType
        self.name = token
    def receiveClose(self):
        # TODO: taste here!
        mod = __import__(moduleName, {}, {}, "x")
        return mod

class ClassUnslicer(LeafUnslicer):
    name = None
    def receiveToken(self, token):
        assert(type(token) == types.StringType)
        assert self.name == None
        self.name = token
    def receiveClose(self):
        # TODO: taste
        klaus = reflect.namedObject(self.name)
        return klaus

class MethodUnslicer(BaseUnslicer):
    state = 0
    im_func = None
    im_self = None
    im_class = None

    # 0: expecting a string with the method name
    # 1: expecting an instance (or None for unbound methods)
    # 2: expecting a class
    def receiveToken(self, token):
        if self.state == 1:
            raise ValueError, "%s expecting an instance now" % self
        if self.state == 2:
            raise ValueError, "%s expecting a class now" % self
        if self.state > 2:
            raise ValueError, "%s got too many tokens" % self
        assert type(token) == types.StringType
        self.im_func = token
        self.state = 1

    def receiveChild(self, obj):
        if self.state == 0:
            raise ValueError, "%s expecting a string (method name) now" % self
        elif self.state == 1:
            assert type(obj) in (types.InstanceType, types.NoneType)
            self.im_self = obj
            self.state = 2
        elif self.state == 2:
            assert type(obj) == types.ClassType # TODO: new-style classes?
            self.im_class = obj
            self.state = 3
        else:
            raise ValueError, "%s got too many tokens" % self

    def receiveClose(self):
        assert self.state == 3
        if self.im_self is None:
            meth = getattr(self.im_class, self.im_func)
            # getattr gives us an unbound method
            return meth
        # TODO: late-available instances
        #if isinstance(self.im_self, NotKnown):
        #    im = _InstanceMethod(self.im_name, self.im_self, self.im_class)
        #    return im
        meth = self.im_class.__dict__[self.im_func]
        # whereas __dict__ gives us a function
        im = instancemethod(meth, self.im_self, self.im_class)
        return im
        

class FunctionUnslicer(LeafUnslicer):
    name = None
    def receiveToken(self, token):
        assert self.name == None
        assert type(token) == types.StringType
        self.name = token
    def receiveClose(self):
        # TODO: taste here
        func = reflect.namedObject(self.name)
        return func

class NoneUnslicer(LeafUnslicer):
    def receiveToken(self, token):
        raise ValueError, "'%s' does not accept any tokens" % self
    def receiveClose(self):
        return None

class BooleanUnslicer(LeafUnslicer):
    value = None
    def receiveToken(self, token):
        assert self.value == None
        assert type(token) == types.IntType
        self.value = token
    def receiveClose(self):
        return bool(self.value)

        
UnslicerRegistry = {
    'unicode': UnicodeUnslicer,
    'list': ListUnslicer,
    'tuple': TupleUnslicer,
    'dict': DictUnslicer,
    'instance': InstanceUnslicer,
    'reference': ReferenceUnslicer,
    'none': NoneUnslicer,
    'boolean': BooleanUnslicer,
    # for testing
    'dict1': BrokenDictUnslicer,
    'dict2': ReallyBrokenDictUnslicer,
    }
        
UnslicerRegistry2 = {}
UnslicerRegistry2.update(UnslicerRegistry)
UnslicerRegistry2.update({
    'module': ModuleUnslicer,
    'class': ClassUnslicer,
    'method': MethodUnslicer,
    'function': FunctionUnslicer,
    'instance': InstanceUnslicer2,
    })


class RootUnslicer(BaseUnslicer):
    openRegistry = UnslicerRegistry
    constraint = None
    def __init__(self):
        self.objects = {}

    def start(self, count):
        pass

    def setConstraint(self, constraint):
        # this constraints top-level objects. E.g., if this is an
        # IntegerConstraint, then only integers will be accepted.
        self.constraint = constraint

    def checkToken(self, typebyte):
        if self.constraint:
            return self.constraint.checkToken(typebyte)
        return None

    def open(self, opentype):
        child = self.openRegistry[opentype]()
        return child

    def doOpen(self, opentype):
        if self.constraint:
            self.constraint.checkOpentype(opentype)
        if len(self.protocol.receiveStack) == 1 and opentype == "vocab":
            # only legal at top-level
            child = VocabUnslicer()
        else:
            child = self.open(opentype)
        if not child:
            # TODO: Violation? or should we just drop the connection?
            raise KeyError, "no such open type '%s'" % opentype
        child.opener = self.open
        if self.constraint:
            child.setConstraint(self.constraint)
        return child

    def receiveAbort(self, token):
        raise ValueError, "top-level should never receive ABORT tokens"

    def receiveChild(self, obj):
        if self.protocol.debug:
            print "RootUnslicer.receiveChild(%s)" % obj
        self.objects = {}
        if isinstance(obj, NewVocabulary):
            self.protocol.setIncomingVocabulary(obj.nv)
            return
        self.protocol.receivedObject(obj) # give finished object to Banana

    def receiveClose(self):
        raise ValueError, "top-level should never receive CLOSE tokens"

    def describe(self):
        return "root"


    def setObject(self, counter, obj):
        if self.protocol.debug:
            print "setObject(%s): %s{%s}" % (counter, obj, id(obj))
        self.objects[counter] = obj

    def getObject(self, counter):
        obj = self.objects.get(counter)
        if self.protocol.debug:
            print "getObject(%s) -> %s{%s}" % (counter, obj, id(obj))
        return obj
    


