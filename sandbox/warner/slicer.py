#! /usr/bin/python

import types
from pickle import whichmodule  # used by FunctionSlicer
from new import instance, instancemethod

from twisted.python.failure import Failure
from twisted.python.components import registerAdapter
from twisted.internet.defer import Deferred
from twisted.python import log, reflect

import tokens
from tokens import Violation, BananaError, tokenNames, UnbananaFailure, \
     ISlicer
import schema

def getInstanceState(inst):
    """Utility function to default to 'normal' state rules in serialization.
    """
    if hasattr(inst, "__getstate__"):
        state = inst.__getstate__()
    else:
        state = inst.__dict__
    return state

class BaseSlicer:
    __implements__ = ISlicer,
    parent = None
    sendOpen = True
    openindex = ()
    trackReferences = False

    def __init__(self, obj):
        # this simplifies Slicers which are adapters
        self.obj = obj
        
    def registerReference(self, refid, obj):
        # optimize: most Slicers will delegate this up to the Root
        return self.parent.registerReference(refid, obj)
    def slicerForObject(self, obj):
        # optimize: most Slicers will delegate this up to the Root
        return self.parent.slicerForObject(obj)
    def slice(self, streamable, banana):
        # this is what makes us ISlicer
        assert self.openindex
        for o in self.openindex:
            yield o
        for t in self.sliceBody(streamable, banana):
            yield t
    def sliceBody(self, streamable, banana):
        raise NotImplementedError
    def childAborted(self):
        pass

    def describe(self):
        return "??"


class UnicodeSlicer(BaseSlicer):
    openindex = ("unicode",)
    def sliceBody(self, streamable, banana):
        yield self.obj.encode("UTF-8")
registerAdapter(UnicodeSlicer, unicode, ISlicer)

class ListSlicer(BaseSlicer):
    openindex = ("list",)
    trackReferences = True

    def sliceBody(self, streamable, banana):
        for i in self.obj:
            yield i
registerAdapter(ListSlicer, list, ISlicer)

class TupleSlicer(ListSlicer):
    openindex = ("tuple",)
registerAdapter(TupleSlicer, tuple, ISlicer)

class DictSlicer(BaseSlicer):
    openindex = ('dict',)
    trackReferences = True
    def sliceBody(self, streamable, banana):
        for key,value in self.obj.items():
            yield key
            yield value


class OrderedDictSlicer(DictSlicer):
    def sliceBody(self, streamable, banana):
        keys = self.obj.keys()
        keys.sort()
        for key in keys:
            value = self.obj[key]
            yield key
            yield value
registerAdapter(OrderedDictSlicer, dict, ISlicer)

class NoneSlicer(BaseSlicer):
    openindex = ('none',)
    trackReferences = False
    def sliceBody(self, streamable, banana):
        # hmm, we need an empty generator. I think a sequence is the only way
        # to accomplish this, other than 'if 0: yield' or something silly
        return []
registerAdapter(NoneSlicer, types.NoneType, ISlicer)

class BooleanSlicer(BaseSlicer):
    openindex = ('boolean',)
    trackReferences = False
    def sliceBody(self, streamable, banana):
        if self.obj:
            yield 1
        else:
            yield 0

try:
    from types import BooleanType
    registerAdapter(BooleanSlicer, bool, ISlicer)
except ImportError:
    pass


class ReferenceSlicer(BaseSlicer):
    # this is created explicitly, not as an adapter
    openindex = ('reference',)
    trackReferences = False

    def __init__(self, refid):
        assert type(refid) == int
        self.refid = refid
    def sliceBody(self, streamable, banana):
        yield self.refid

class VocabSlicer(OrderedDictSlicer):
    # this is created explicitly, but otherwise works just like a dictionary
    openindex = ('vocab',)
    trackReferences = False


# Extended types, not generally safe. The TrustingRoot checks for these with
# a separate table.

class InstanceSlicer(OrderedDictSlicer):
    openindex = ('instance',)
    trackReferences = True

    def sliceBody(self, streamable, banana):
        yield reflect.qual(self.obj.__class__) # really a second index token
        self.obj = getInstanceState(self.obj)
        for t in OrderedDictSlicer.sliceBody(self, streamable, banana):
            yield t

class ModuleSlicer(BaseSlicer):
    openindex = ('module',)
    trackReferences = True

    def sliceBody(self, streamable, banana):
        yield self.obj.__name__

class ClassSlicer(BaseSlicer):
    openindex = ('class',)
    trackReferences = True

    def sliceBody(self, streamable, banana):
        yield reflect.qual(self.obj)

class MethodSlicer(BaseSlicer):
    openindex = ('method',)
    trackReferences = True

    def sliceBody(self, streamable, banana):
        yield self.obj.im_func.__name__
        yield self.obj.im_self
        yield self.obj.im_class

class FunctionSlicer(BaseSlicer):
    openindex = ('function',)
    trackReferences = True

    def sliceBody(self, streamable, banana):
        name = self.obj.__name__
        fullname = str(whichmodule(self.obj, self.obj.__name__)) + '.' + name
        yield fullname

ExtendedSlicerRegistry = {}
ExtendedSlicerRegistry.update({
    types.InstanceType: InstanceSlicer,
    types.ModuleType: ModuleSlicer,
    types.ClassType: ClassSlicer,
    types.MethodType: MethodSlicer,
    types.FunctionType: FunctionSlicer,
    })


class RootSlicer:
    __implements__ = ISlicer,
    deferred = None
    slicerTable = {}

    def __init__(self, sendbanana):
        self.sendbanana = sendbanana
        self.sendQueue = []
        self.references = {}

    def registerReference(self, refid, obj):
        if self.sendbanana.debug:
            print "registerReference[%d]=%s %s 0x%x" % (refid, obj, type(obj),
                                                        id(obj))
        self.references[id(obj)] = refid

    def slicerForObject(self, obj):
        if self.sendbanana.debug:
            print "slicerForObject(0x%x)" % id(obj)
        # check for an object which was sent previously or has at least
        # started sending
        refid = self.references.get(id(obj), None)
        if refid is not None:
            if self.sendbanana.debug:
                print "found Reference[%d]" % refid
            return ReferenceSlicer(refid)
        # could use a table here if you think it'd be faster than an
        # adapter lookup
        slicerFactory = self.slicerTable.get(type(obj))
        if slicerFactory:
            return slicerFactory(obj)
        return ISlicer(obj)

    def slice(self):
        return self
    def __iter__(self):
        return self # we are our own iterator
    def next(self):
        if self.sendQueue:
            return self.sendQueue.pop()
        if self.sendbanana.debug:
            print "LAST BAG"
        self.deferred = Deferred()
        return self.deferred

    def send(self, obj):
        # obj can also be a Slicer, say, a CallSlicer
        idle = (len(self.sendbanana.slicerStack) == 1) and not self.sendQueue
        self.sendQueue.append(obj)
        if idle:
            # wake up
            if self.deferred:
                d = self.deferred
                self.deferred = None
                d.callback(None)

class TrustingRootSlicer(RootSlicer):
    slicerTable = ExtendedSlicerRegistry




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
        etc.). It must not be None.

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

    def checkToken(self, typebyte, size):
        """Check to see if the given token is acceptable (does it conform to
        the constraint?). It will not be asked about ABORT or CLOSE tokens,
        but it *will* be asked about OPEN. It should enfore a length limit
        for long tokens (STRING and LONGINT/LONGNEG types). If STRING is
        acceptable, then VOCAB should be too. It should return None if the
        token and the size are acceptable. Should raise Violation if the
        schema indiates the token is not acceptable. Should raise
        BananaError if the type byte violates the basic Banana protocol. (if
        no schema is in effect, this should never raise Violation, but might
        still raise BananaError).
        """

    def openerCheckToken(self, typebyte, size, opentype):
        """'typebyte' is the type of an incoming index token. 'size' is the
        value of header associated with this typebyte. 'opentype' is a list
        of open tokens that we've received so far, not including the one
        that this token hopes to create.

        This method should ask the current opener if this index token is
        acceptable, and is used in lieu of checkToken() when the receiver is
        in the index phase. Usually implemented by calling
        self.opener.openerCheckToken, thus delegating the question to the
        RootUnslicer. """

    def doOpen(self, opentype):
        """opentype is a tuple. Return None if more index tokens are
        required. Check to see if this kind of child object conforms to the
        constraint, raise Violation if not. Create a new Unslicer (usually
        by calling self.opener.doOpen, which delegates the
        opentype-to-Unslicer mapping to the RootUnslicer). Set a constraint
        on the child unslicer, if any. Set the child's .opener attribute
        (usually to self.opener).
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

    def describeSelf(self):
        """Return a short string describing where in the object tree this
        unslicer is sitting, relative to its parent. These strings are
        obtained from every unslicer in the stack, and joined to describe
        where any problems occurred."""

    def where(self):
        """This returns a string that describes the location of this
        unslicer, starting at the root of the object tree."""


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
        self.opener = None # must be chained by our parent

    def describeSelf(self):
        return "??"

    def where(self):
        return self.protocol.describe()

    def setConstraint(self, constraint):
        pass

    def start(self, count):
        pass

    def checkToken(self, typebyte, size):
        return # no restrictions

    def openerCheckToken(self, typebyte, size, opentype):
        return self.opener.openerCheckToken(typebyte, size, opentype)

    def open(self, opentype):
        """Return an IBananaUnslicer object based upon the 'opentype' tuple.

        This method does not apply constraints, it only serves to map
        opentypes into Unslicers. Most subclasses will implement this by
        delegating the request to their .opener (which usually points to the
        RootUnslicer), and will set the new child's .opener attribute so
        that they can do the same. Subclasses that wish to change the way
        opentypes are mapped to Unslicers can do so by changing this
        behavior.
        """

        unslicer = self.opener.open(opentype)
        if unslicer:
            unslicer.opener = self.opener
        return unslicer

        
    def doOpen(self, opentype):
        """Return an IBananaUnslicer object based upon the 'opentype' tuple.
        This object will receive all tokens destined for the subnode.

        If you want to enforce a constraint, you must override this method
        and do two things: make sure your constraint accepts the opentype,
        and set a per-item constraint on the new child unslicer.

        This method calls self.open() to obtain the unslicer. That may
        return None instead of a child unslicer if the opener wants a
        multi-token opentype tuple, so be sure to check for Noneness before
        adding a per-item constraint.
        """

        return self.open(opentype)

    def receiveChild(self, obj):
        pass

    def receiveClose(self):
        raise NotImplementedError

    def reportViolation(self, why):
        """If this unslicer raises a Violation, this method is given a
        chance to do some cleanup or error-reporting. 'why' is the
        UnbananaFailure that wraps the Violation: this method may modify it
        or return a different one.
        """
        return why

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
        # TODO: examine how abandoned child objects could mess up this
        # counter
        pass

    def getObject(self, counter):
        """'None' means 'ask our parent instead'.
        """
        return None

    def propagateUnbananaFailures(self, obj):
        """Call this from receiveChild() if you want to deal with failures
        in your children by reporting a failure to your parent.
        """
        if isinstance(obj, UnbananaFailure):
            raise Violation(failure=obj)

    def explode(self, failure):
        """If something goes wrong in a Deferred callback, it may be too
        late to reject the token and to normal error handling. I haven't
        figured out how to do sensible error-handling in this situation.
        This method exists to make sure that the exception shows up
        *somewhere*. If this is called, it is also likely that a placeholder
        (probably a Deferred) will be left in the unserialized object about
        to be handed to the RootUnslicer.
        """
        print "KABOOM"
        print failure
        self.protocol.exploded = failure

class LeafUnslicer(BaseUnslicer):
    # inherit from this to reject any child nodes

    # checkToken should reject OPEN tokens

    def doOpen(self, opentype):
        raise Violation("'%s' does not accept sub-objects" % self)

class UnicodeUnslicer(LeafUnslicer):
    # accept a UTF-8 encoded string
    string = None
    constraint = None
    def setConstraint(self, constraint):
        assert isinstance(constraint, schema.StringConstraint)
        self.constraint = constraint

    def checkToken(self, typebyte, size):
        if typebyte != tokens.STRING:
            raise BananaError("UnicodeUnslicer only accepts strings",
                              self.where())
        if self.constraint:
            self.constraint.checkToken(typebyte, size)

    def receiveChild(self, obj):
        self.propagateUnbananaFailures(obj)
        if self.string != None:
            raise BananaError("already received a string", self.where())
        self.string = unicode(obj, "UTF-8")

    def receiveClose(self):
        return self.string
    def describeSelf(self):
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

    def start(self, count):
        #self.opener = foo # could replace it if we wanted to
        self.list = []
        self.count = count
        if self.debug:
            print "%s[%d].start with %s" % (self, self.count, self.list)
        self.protocol.setObject(count, self.list)

    def checkToken(self, typebyte, size):
        if self.maxLength != None and len(self.list) >= self.maxLength:
            # list is full, no more tokens accepted
            # this is hit if the max+1 item is a primitive type
            raise Violation("the list is full")
        if self.itemConstraint:
            self.itemConstraint.checkToken(typebyte, size)

    def doOpen(self, opentype):
        # decide whether the given object type is acceptable here. Raise a
        # Violation exception if not, otherwise give it to our opener (which
        # will normally be the RootUnslicer). Apply a constraint to the new
        # unslicer.
        if self.maxLength != None and len(self.list) >= self.maxLength:
            # this is hit if the max+1 item is a non-primitive type
            raise Violation("the list is full")
        if self.itemConstraint:
            self.itemConstraint.checkOpentype(opentype)
        unslicer = self.open(opentype)
        if unslicer:
            if self.itemConstraint:
                unslicer.setConstraint(self.itemConstraint)
        return unslicer

    def update(self, obj, index):
        # obj has already passed typechecking
        if self.debug:
            print "%s[%d].update: [%d]=%s" % (self, self.count, index, obj)
        assert(type(index) == types.IntType)
        self.list[index] = obj

    def receiveChild(self, obj):
        if self.debug:
            print "%s[%d].receiveChild(%s)" % (self, self.count, obj)
        self.propagateUnbananaFailures(obj)
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
            raise Violation("the list is full")
        if isinstance(obj, Deferred):
            if self.debug:
                print " adding my update[%d] to %s" % (len(self.list), obj)
            obj.addCallback(self.update, len(self.list))
            obj.addErrback(self.printErr)
            self.list.append(obj) # placeholder
        else:
            self.list.append(obj)

    def printErr(self, why):
        print "ERR!"
        print why.getBriefTraceback()
        log.err(why)

    def receiveClose(self):
        return self.list

    def describeSelf(self):
        return "[%d]" % len(self.list)

class TupleUnslicer(BaseUnslicer):
    debug = False
    constraints = None

    def setConstraint(self, constraint):
        assert isinstance(constraint, schema.TupleConstraint)
        self.constraints = constraint.constraints

    def start(self, count):
        self.list = []
        self.count = count
        if self.debug:
            print "%s[%d].start with %s" % (self, self.count, self.list)
        # TODO: optimize by keeping count of child Deferreds rather than
        # scanning the whole self.list each time
        self.finished = False
        self.deferred = Deferred()
        self.protocol.setObject(count, self.deferred)

    def checkToken(self, typebyte, size):
        if self.constraints == None:
            return
        if len(self.list) >= len(self.constraints):
            raise Violation("the tuple is full")
        self.constraints[len(self.list)].checkToken(typebyte, size)

    def doOpen(self, opentype):
        where = len(self.list)
        if self.constraints != None:
            if where >= len(self.constraints):
                raise Violation("the tuple is full")
            self.constraints[where].checkOpentype(opentype)
        unslicer = self.open(opentype)
        if unslicer:
            if self.constraints != None:
                unslicer.setConstraint(self.constraints[where])
        return unslicer

    def update(self, obj, index):
        if self.debug:
            print "%s[%d].update: [%d]=%s" % (self, self.count, index, obj)
        self.list[index] = obj
        if self.finished:
            self.checkComplete()

    def receiveChild(self, obj):
        self.propagateUnbananaFailures(obj)
        if isinstance(obj, Deferred):
            obj.addCallback(self.update, len(self.list))
            obj.addErrback(self.explode)
            self.list.append(obj) # placeholder
        else:
            self.list.append(obj)
        
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
        self.finished = 1
        return self.checkComplete()

    def describeSelf(self):
        return "[%d]" % len(self.list)


class DictUnslicer(BaseUnslicer):
    gettingKey = True
    keyConstraint = None
    valueConstraint = None
    maxKeys = None

    def setConstraint(self, constraint):
        assert isinstance(constraint, schema.DictConstraint)
        self.keyConstraint = constraint.keyConstraint
        self.valueConstraint = constraint.valueConstraint
        self.maxKeys = constraint.maxKeys

    def start(self, count):
        self.d = {}
        self.protocol.setObject(count, self.d)
        self.key = None

    def checkToken(self, typebyte, size):
        if self.maxKeys != None:
            if len(self.d) >= self.maxKeys:
                raise Violation("the dict is full")
        if self.gettingKey:
            if self.keyConstraint:
                self.keyConstraint.checkToken(typebyte, size)
        else:
            if self.valueConstraint:
                self.valueConstraint.checkToken(typebyte, size)

    def doOpen(self, opentype):
        if self.maxKeys != None:
            if len(self.d) >= self.maxKeys:
                raise Violation("the dict is full")
        if self.gettingKey:
            if self.keyConstraint:
                self.keyConstraint.checkOpentype(opentype)
        else:
            if self.valueConstraint:
                self.valueConstraint.checkOpentype(opentype)
        unslicer = self.open(opentype)
        if unslicer:
            if self.gettingKey:
                if self.keyConstraint:
                    unslicer.setConstraint(self.keyConstraint)
            else:
                if self.valueConstraint:
                    unslicer.setConstraint(self.valueConstraint)
        return unslicer

    def update(self, value, key):
        # this is run as a Deferred callback, hence the backwards arguments
        self.d[key] = value

    def receiveChild(self, obj):
        self.propagateUnbananaFailures(obj)
        if self.gettingKey:
            self.receiveKey(obj)
        else:
            self.receiveValue(obj)
        self.gettingKey = not self.gettingKey

    def receiveKey(self, key):
        # I don't think it is legal (in python) to use an incomplete object
        # as a dictionary key, because you must have all the contents to
        # hash it. Someone could fake up a token stream to hit this case,
        # however: OPEN(dict), OPEN(tuple), OPEN(reference), 0, CLOSE, CLOSE,
        # "value", CLOSE
        if isinstance(key, Deferred):
            raise BananaError("incomplete object as dictionary key",
                              self.where())
        try:
            if self.d.has_key(key):
                raise BananaError("duplicate key '%s'" % key, self.where())
        except TypeError:
            raise BananaError("unhashable key '%s'" % key, self.where())
        self.key = key

    def receiveValue(self, value):
        if isinstance(value, Deferred):
            value.addCallback(self.update, self.key)
            value.addErrback(log.err)
        self.d[self.key] = value # placeholder

    def receiveClose(self):
        return self.d

    def describeSelf(self):
        if self.gettingKey:
            return "{}"
        else:
            return "{}[%s]" % self.key

class NewVocabulary:
    def __init__(self, newvocab):
        self.nv = newvocab

class VocabUnslicer(LeafUnslicer):
    """Much like DictUnslicer, but keys must be numbers, and values must
    be strings"""
    
    def start(self, count):
        self.d = {}
        self.gettingKey = True
        self.key = None

    def checkToken(self, typebyte, size):
        if self.gettingKey:
            if typebyte != tokens.INT:
                raise BananaError("VocabUnslicer only accepts INT keys",
                                  self.where())
        else:
            if typebyte != tokens.STRING:
                raise BananaError("VocabUnslicer only accepts STRING values",
                                  self.where())

    def receiveChild(self, token):
        self.propagateUnbananaFailures(token)
        if self.gettingKey:
            if self.d.has_key(token):
                raise BananaError("duplicate key '%s'" % token,
                                  self.where())
            self.key = token
        else:
            self.d[self.key] = token
        self.gettingKey = not self.gettingKey

    def receiveClose(self):
        return NewVocabulary(self.d)

    def describeSelf(self):
        if self.gettingKey:
            return "<vocabdict>[%s]" % self.key
        else:
            return "<vocabdict>"


class BrokenDictUnslicer(DictUnslicer):
    dieInFinish = 0

    def receiveKey(self, key):
        if key == "die":
            raise Violation("aaagh")
        if key == "please_die_in_finish":
            self.dieInFinish = 1
        DictUnslicer.receiveKey(self, key)

    def receiveValue(self, value):
        if value == "die":
            raise Violation("aaaaaaaaargh")
        DictUnslicer.receiveValue(self, value)

    def receiveClose(self):
        if self.dieInFinish:
            raise Violation("dead in receiveClose()")
        DictUnslicer.receiveClose(self)

class ReallyBrokenDictUnslicer(DictUnslicer):
    def start(self, count):
        raise Violation("dead in start")


class Dummy:
    def __repr__(self):
        return "<Dummy %s>" % self.__dict__
    def __cmp__(self, other):
        if not type(other) == type(self):
            return -1
        return cmp(self.__dict__, other.__dict__)


class InstanceUnslicer(BaseUnslicer):
    # danger: instances are mutable containers. If an attribute value is not
    # yet available, __dict__ will hold a Deferred until it is. Other
    # objects might be created and use our object before this is fixed.
    # TODO: address this. Note that InstanceUnslicers aren't used in PB
    # (where we have pb.Referenceable and pb.Copyable which have schema
    # constraints and could have different restrictions like not being
    # allowed to participate in reference loops).

    def start(self, count):
        self.d = {}
        self.count = count
        self.gettingClassname = True
        self.gettingAttrname = False
        self.deferred = Deferred()
        self.protocol.setObject(count, self.deferred)
        self.classname = None
        self.attrname = None

    def checkToken(self, typebyte, size):
        if self.gettingClassname:
            if typebyte not in (tokens.STRING, tokens.VOCAB):
                raise BananaError("InstanceUnslicer classname must be string",
                                  self.where())
        if self.gettingAttrname:
            if typebyte not in (tokens.STRING, tokens.VOCAB):
                raise BananaError("InstanceUnslicer keys must be STRINGs",
                                  self.where())
        # TODO: use schema to determine attribute value constraint

    def receiveChild(self, obj):
        self.propagateUnbananaFailures(obj)
        if self.gettingClassname:
            self.classname = obj
            self.gettingClassname = False
            self.gettingAttrname = True
        else:
            if self.gettingAttrname:
                self.attrname = obj
            else:
                if isinstance(obj, Deferred):
                    # TODO: this is an artificial restriction, and it might
                    # be possible to remove it, but I need to think through
                    # it carefully first
                    raise BananaError("unreferenceable object in attribute",
                                      self.where())
                if self.d.has_key(self.attrname):
                    raise BananaError("duplicate attribute name '%s'" % name,
                                      self.where())
                self.setAttribute(self.attrname, obj)
            self.gettingAttrname = not self.gettingAttrname

    def setAttribute(self, name, value):
        self.d[name] = value

    def receiveClose(self):
        # TODO: TASTE HERE IF YOU WANT TO LIVE!
        inst = Dummy()
        #inst.__classname__ = self.classname
        setInstanceState(inst, self.d)
        self.protocol.setObject(self.count, inst)
        self.deferred.callback(inst)
        return inst

    def describeSelf(self):
        if self.classname == None:
            return "<??>"
        me = "<%s>" % self.classname
        if self.gettingAttrname:
            return "%s.attrname??" % me
        else:
            return "%s.%s" % (me, self.attrname)

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
    finished = False
    def setConstraint(self, constraint):
        self.constraint = constraint

    def checkToken(self, typebyte,size):
        if typebyte != tokens.INT:
            raise BananaError("ReferenceUnslicer only accepts INTs",
                              self.where())

    def receiveChild(self, num):
        self.propagateUnbananaFailures(num)
        if self.finished:
            raise BananaError("ReferenceUnslicer only accepts one int",
                              self.where())
        self.obj = self.protocol.getObject(num)
        self.finished = True
        # assert that this conforms to the constraint
        if self.constraint:
            self.constraint.checkObject(self.obj)
        # TODO: it might be a Deferred, but we should know enough about the
        # incoming value to check the constraint. This requires a subclass
        # of Deferred which can give us the metadata.

    def receiveClose(self):
        return self.obj

class ModuleUnslicer(LeafUnslicer):
    finished = False

    def checkToken(self, typebyte, size):
        if typebyte not in (tokens.STRING, tokens.VOCAB):
            raise BananaError("ModuleUnslicer only accepts strings",
                              self.where())

    def receiveChild(self, name):
        self.propagateUnbananaFailures(name)
        if self.finished:
            raise BananaError("ModuleUnslicer only accepts one string",
                              self.where())
        self.finished = True
        # TODO: taste here!
        mod = __import__(moduleName, {}, {}, "x")
        self.mod = mod

    def receiveClose(self):
        if not self.finished:
            raise BananaError("ModuleUnslicer requires a string",
                              self.where())
        return self.mod

class ClassUnslicer(LeafUnslicer):
    finished = False

    def checkToken(self, typebyte, size):
        if typebyte not in (tokens.STRING, tokens.VOCAB):
            raise BananaError("ClassUnslicer only accepts strings",
                              self.where())

    def receiveChild(self, name):
        self.propagateUnbananaFailures(name)
        if self.finished:
            raise BananaError("ClassUnslicer only accepts one string",
                              self.where())
        self.finished = True
        # TODO: taste here!
        self.klass = reflect.namedObject(name)

    def receiveClose(self):
        if not self.finished:
            raise BananaError("ClassUnslicer requires a string",
                              self.where())
        return self.klass

class MethodUnslicer(BaseUnslicer):
    state = 0
    im_func = None
    im_self = None
    im_class = None

    # self.state:
    # 0: expecting a string with the method name
    # 1: expecting an instance (or None for unbound methods)
    # 2: expecting a class

    def checkToken(self, typebyte, size):
        if self.state == 0:
            if typebyte not in (tokens.STRING, tokens.VOCAB):
                raise BananaError("MethodUnslicer methodname must be a string",
                                  self.where())
        elif self.state == 1:
            if typebyte != tokens.OPEN:
                raise BananaError("MethodUnslicer instance must be OPEN",
                                  self.where())
        elif self.state == 2:
            if typebyte != tokens.OPEN:
                raise BananaError("MethodUnslicer class must be an OPEN",
                                  self.where())

    def doOpen(self, opentype):
        # check the opentype
        if self.state == 1:
            if opentype[0] not in ("instance", "none"):
                raise BananaError("MethodUnslicer instance must be " +
                                  "instance or None",
                                  self.where())
        elif self.state == 2:
            if opentype[0] != "class":
                raise BananaError("MethodUnslicer class must be a class",
                                  self.where())
        unslicer = self.open(opentype)
        # TODO: apply constraint
        return unslicer

    def receiveChild(self, obj):
        self.propagateUnbananaFailures(obj)
        if self.state == 0:
            self.im_func = obj
            self.state = 1
        elif self.state == 1:
            assert type(obj) in (types.InstanceType, types.NoneType)
            self.im_self = obj
            self.state = 2
        elif self.state == 2:
            assert type(obj) == types.ClassType # TODO: new-style classes?
            self.im_class = obj
            self.state = 3
        else:
            raise BananaError("MethodUnslicer only accepts three objects",
                              self.where())

    def receiveClose(self):
        if self.state != 3:
            raise BananaError("MethodUnslicer requires three objects",
                              self.where())
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
    finished = False

    def checkToken(self, typebyte, size):
        if typebyte not in (tokens.STRING, tokens.VOCAB):
            raise BananaError("FunctionUnslicer only accepts strings",
                              self.where())

    def receiveChild(self, name):
        self.propagateUnbananaFailures(name)
        if self.finished:
            raise BananaError("FunctionUnslicer only accepts one string",
                              self.where())
        self.finished = True
        # TODO: taste here!
        self.func = reflect.namedObject(name)

    def receiveClose(self):
        if not self.finished:
            raise BananaError("FunctionUnslicer requires a string",
                              self.where())
        return self.func

class NoneUnslicer(LeafUnslicer):
    def checkToken(self, typebyte, size):
        raise BananaError("NoneUnslicer does not accept any tokens",
                          self.where())
    def receiveClose(self):
        return None

class BooleanUnslicer(LeafUnslicer):
    value = None
    constraint = None

    def setConstraint(self, constraint):
        assert isinstance(constraint, schema.BooleanConstraint)
        self.constraint = constraint

    def checkToken(self, typebyte, size):
        if typebyte != tokens.INT:
            raise BananaError("BooleanUnslicer only accepts an INT token",
                              self.where())
        if self.value != None:
            raise BananaError("BooleanUnslicer only accepts one token",
                              self.where())

    def receiveChild(self, obj):
        self.propagateUnbananaFailures(obj)
        assert type(obj) == int
        if self.constraint:
            if self.constraint.value != None:
                if bool(obj) != self.constraint.value:
                    raise Violation("This boolean can only be %s" % \
                                    self.constraint.value)
        self.value = bool(obj)

    def receiveClose(self):
        return self.value

    def describeSelf(self):
        return "<bool>"
        
UnslicerRegistry = {
    ('unicode',): UnicodeUnslicer,
    ('list',): ListUnslicer,
    ('tuple',): TupleUnslicer,
    ('dict',): DictUnslicer,
    ('instance',): InstanceUnslicer,
    ('reference',): ReferenceUnslicer,
    ('none',): NoneUnslicer,
    ('boolean',): BooleanUnslicer,
    # for testing
    ('dict1',): BrokenDictUnslicer,
    ('dict2',): ReallyBrokenDictUnslicer,
    }
        
UnslicerRegistry2 = UnslicerRegistry.copy()
UnslicerRegistry2.update({
    ('module',): ModuleUnslicer,
    ('class',): ClassUnslicer,
    ('method',): MethodUnslicer,
    ('function',): FunctionUnslicer,
    ('instance',): InstanceUnslicer2,
    })


class RootUnslicer(BaseUnslicer):
    openRegistry = UnslicerRegistry
    topRegistry = UnslicerRegistry
    constraint = None

    def __init__(self):
        self.objects = {}
        maxLength = reduce(max, [len(k[0]) for k in self.openRegistry.keys()])
        self.maxIndexLength = maxLength

    def start(self, count):
        pass

    def setConstraint(self, constraint):
        # this constraints top-level objects. E.g., if this is an
        # IntegerConstraint, then only integers will be accepted.
        self.constraint = constraint

    def checkToken(self, typebyte, size):
        if self.constraint:
            self.constraint.checkToken(typebyte, size)

    def openerCheckToken(self, typebyte, size, opentype):
        if typebyte == tokens.STRING:
            if size > self.maxIndexLength:
                why = "STRING token is too long, %d>%d" % \
                      (size, self.maxIndexLength)
                raise Violation(why)
        elif typebyte == tokens.VOCAB:
            return None
        else:
            raise BananaError("index token 0x%02x not STRING or VOCAB" % \
                              ord(typebyte))

    def open(self, opentype, typemap=None):
        """Accept an opentype tuple and produce a new Unslicer. This
        function is generally called (by delegation) by the top Unslicer on
        the stack, regardless of what kind of unslicer it is.
        """

        if typemap == None:
            typemap = self.openRegistry

        try:
            opener = typemap[opentype]
            child = opener()
            # do not set .opener here, but leave it for the caller. Unslicer
            # subclasses will set it to their parent in their own .open()
            # call. The RootUnslicer will set it (to itself) in
            # RootUnslicer.doOpen() .
        except KeyError:
            raise Violation("unknown OPEN type '%s'" % (opentype,))
        return child

    def openTop(self, opentype):
        return self.open(opentype, self.topRegistry)

    def doOpen(self, opentype):
        if self.constraint:
            self.constraint.checkOpentype(opentype)
        if len(self.protocol.receiveStack) == 1 and opentype[0] == "vocab":
            # only legal at top-level
            child = VocabUnslicer()
        else:
            child = self.openTop(opentype)
        if child:
            child.opener = self
            if self.constraint:
                child.setConstraint(self.constraint)
        return child

    def receiveChild(self, obj):
        if self.protocol.debug:
            print "RootUnslicer.receiveChild(%s)" % (obj,)
        self.objects = {}
        if isinstance(obj, NewVocabulary):
            self.protocol.setIncomingVocabulary(obj.nv)
            return
        if self.protocol.exploded:
            print "protocol exploded, can't deliver object"
            print self.protocol.exploded
            self.protocol.receivedObject(self.protocol.exploded)
            return
        self.protocol.receivedObject(obj) # give finished object to Banana

    def receiveClose(self):
        raise BananaError("top-level should never receive CLOSE tokens")

    def describeSelf(self):
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
    


