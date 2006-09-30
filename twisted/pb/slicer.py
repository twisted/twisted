# -*- test-case-name: twisted.pb.test.test_banana -*-

import types
from pickle import whichmodule  # used by FunctionSlicer
from new import instance, instancemethod
import sets

from twisted.python.components import registerAdapter
from zope.interface import implements
from twisted.internet.defer import Deferred
from twisted.python import log, reflect

import tokens
from tokens import Violation, BananaError, BananaFailure, tokenNames
import schema

def getInstanceState(inst):
    """Utility function to default to 'normal' state rules in serialization.
    """
    if hasattr(inst, "__getstate__"):
        state = inst.__getstate__()
    else:
        state = inst.__dict__
    return state

class SlicerClass(type):
    # auto-register Slicers
    def __init__(self, name, bases, dict):
        type.__init__(self, name, bases, dict)
        typ = dict.get('slices')
        #reg = dict.get('slicerRegistry')
        if typ:
            registerAdapter(self, typ, tokens.ISlicer)


class BaseSlicer:
    __metaclass__ = SlicerClass
    implements(tokens.ISlicer)

    slices = None

    parent = None
    sendOpen = True
    opentype = ()
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
        self.streamable = streamable
        assert self.opentype
        for o in self.opentype:
            yield o
        for t in self.sliceBody(streamable, banana):
            yield t
    def sliceBody(self, streamable, banana):
        raise NotImplementedError
    def childAborted(self, f):
        return f

    def describe(self):
        return "??"


class ScopedSlicer(BaseSlicer):
    """This Slicer provides a containing scope for referenceable things like
    lists. The same list will not be serialized twice within this scope, but
    it will not survive outside it."""

    def __init__(self, obj):
        BaseSlicer.__init__(self, obj)
        self.references = {} # maps id(obj) -> (obj,refid)

    def registerReference(self, refid, obj):
        # keep references here, not in the actual PBRootSlicer

        # This use of id(obj) requires a bit of explanation. We are making
        # the assumption that the object graph remains unmodified until
        # serialization is complete. In particular, we assume that all the
        # objects in it remain alive, and no new objects are added to it,
        # until serialization is complete. id(obj) is only unique for live
        # objects: once the object is garbage-collected, a new object may be
        # created with the same id(obj) value.
        #
        # The concern is that a custom Slicer will call something that
        # mutates the object graph before it has finished being serialized.
        # This might be one which calls some user-level function during
        # Slicing, or one which uses a Deferred to put off serialization for
        # a while, creating an opportunity for some other code to get
        # control.

        # The specific concern is that if, in the middle of serialization, an
        # object that was already serialized is gc'ed, and a new object is
        # created and attached to a portion of the object graph that hasn't
        # been serialized yet, and if the new object gets the same id(obj) as
        # the dead object, then we could be tricked into sending the
        # reference number of the old (dead) object. On the receiving end,
        # this would result in a mangled object graph.

        # User code isn't supposed to allow the object graph to change during
        # serialization, so this mangling "should not happen" under normal
        # circumstances. However, as a reasonably cheap way to mitigate the
        # worst sort of mangling when user code *does* mess up,
        # self.references maps from id(obj) to a tuple of (obj,refid) instead
        # of just the refid. This insures that the object will stay alive
        # until the ScopedSlicer dies, guaranteeing that we won't get
        # duplicate id(obj) values. If user code mutates the object graph
        # during serialization we might still get inconsistent results, but
        # they'll be the ordinary kind of inconsistent results (snapshots of
        # different branches of the object graph at different points in time)
        # rather than the blatantly wrong mangling that would occur with
        # re-used id(obj) values.
        
        self.references[id(obj)] = (obj,refid)

    def slicerForObject(self, obj):
        # check for an object which was sent previously or has at least
        # started sending
        obj_refid = self.references.get(id(obj), None)
        if obj_refid is not None:
            # we've started to send this object already, so just include a
            # reference to it
            return ReferenceSlicer(obj_refid[1])
        # otherwise go upstream so we can serialize the object completely
        return self.parent.slicerForObject(obj)


class UnicodeSlicer(BaseSlicer):
    opentype = ("unicode",)
    slices = unicode
    def sliceBody(self, streamable, banana):
        yield self.obj.encode("UTF-8")

class ListSlicer(BaseSlicer):
    opentype = ("list",)
    trackReferences = True
    slices = list

    def sliceBody(self, streamable, banana):
        for i in self.obj:
            yield i

class TupleSlicer(ListSlicer):
    opentype = ("tuple",)
    slices = tuple

class SetSlicer(ListSlicer):
    opentype = ("set",)
    trackReferences = True
    slices = sets.Set

    def sliceBody(self, streamable, banana):
        for i in self.obj:
            yield i

if __builtins__.has_key("set"):
    # python2.4 has a builtin 'set' type, which is mutable
    class BuiltinSetSlicer(SetSlicer):
        slices = set

class ImmutableSetSlicer(SetSlicer):
    opentype = ("immutable-set",)
    trackReferences = False
    slices = sets.ImmutableSet

class DictSlicer(BaseSlicer):
    opentype = ('dict',)
    trackReferences = True
    slices = None
    def sliceBody(self, streamable, banana):
        for key,value in self.obj.items():
            yield key
            yield value


class OrderedDictSlicer(DictSlicer):
    slices = dict
    def sliceBody(self, streamable, banana):
        keys = self.obj.keys()
        keys.sort()
        for key in keys:
            value = self.obj[key]
            yield key
            yield value

class NoneSlicer(BaseSlicer):
    opentype = ('none',)
    trackReferences = False
    slices = type(None)
    def sliceBody(self, streamable, banana):
        # hmm, we need an empty generator. I think a sequence is the only way
        # to accomplish this, other than 'if 0: yield' or something silly
        return []

class BooleanSlicer(BaseSlicer):
    opentype = ('boolean',)
    trackReferences = False
    def sliceBody(self, streamable, banana):
        if self.obj:
            yield 1
        else:
            yield 0
registerAdapter(BooleanSlicer, bool, tokens.ISlicer)


class ReferenceSlicer(BaseSlicer):
    # this is created explicitly, not as an adapter
    opentype = ('reference',)
    trackReferences = False

    def __init__(self, refid):
        assert type(refid) == int
        self.refid = refid
    def sliceBody(self, streamable, banana):
        yield self.refid

class VocabSlicer(OrderedDictSlicer):
    # this is created explicitly, but otherwise works just like a dictionary
    opentype = ('vocab',)
    trackReferences = False


# Extended types, not generally safe. The UnsafeRootSlicer checks for these
# with a separate table.

class InstanceSlicer(OrderedDictSlicer):
    opentype = ('instance',)
    trackReferences = True

    def sliceBody(self, streamable, banana):
        yield reflect.qual(self.obj.__class__) # really a second index token
        self.obj = getInstanceState(self.obj)
        for t in OrderedDictSlicer.sliceBody(self, streamable, banana):
            yield t

class ModuleSlicer(BaseSlicer):
    opentype = ('module',)
    trackReferences = True

    def sliceBody(self, streamable, banana):
        yield self.obj.__name__

class ClassSlicer(BaseSlicer):
    opentype = ('class',)
    trackReferences = True

    def sliceBody(self, streamable, banana):
        yield reflect.qual(self.obj)

class MethodSlicer(BaseSlicer):
    opentype = ('method',)
    trackReferences = True

    def sliceBody(self, streamable, banana):
        yield self.obj.im_func.__name__
        yield self.obj.im_self
        yield self.obj.im_class

class FunctionSlicer(BaseSlicer):
    opentype = ('function',)
    trackReferences = True

    def sliceBody(self, streamable, banana):
        name = self.obj.__name__
        fullname = str(whichmodule(self.obj, self.obj.__name__)) + '.' + name
        yield fullname

UnsafeSlicerTable = {}
UnsafeSlicerTable.update({
    types.InstanceType: InstanceSlicer,
    types.ModuleType: ModuleSlicer,
    types.ClassType: ClassSlicer,
    types.MethodType: MethodSlicer,
    types.FunctionType: FunctionSlicer,
    #types.TypeType: NewstyleClassSlicer,
    # ???: NewstyleInstanceSlicer,  # pickle uses obj.__reduce__ to help
    # http://docs.python.org/lib/node68.html
    })


class RootSlicer:
    implements(tokens.ISlicer, tokens.IRootSlicer)

    streamableInGeneral = True
    producingDeferred = None
    objectSentDeferred = None
    slicerTable = {}
    debug = False

    def __init__(self, protocol):
        self.protocol = protocol
        self.sendQueue = []

    def allowStreaming(self, streamable):
        self.streamableInGeneral = streamable

    def registerReference(self, refid, obj):
        pass

    def slicerForObject(self, obj):
        # could use a table here if you think it'd be faster than an
        # adapter lookup
        if self.debug: print "slicerForObject(%s)" % type(obj)
        # do the adapter lookup first, so that registered adapters override
        # UnsafeSlicerTable's InstanceSlicer
        slicer = tokens.ISlicer(obj, None)
        if slicer:
            if self.debug: print "got ISlicer", slicer
            return slicer
        slicerFactory = self.slicerTable.get(type(obj))
        if slicerFactory:
            if self.debug: print " got slicerFactory", slicerFactory
            return slicerFactory(obj)
        if issubclass(type(obj), types.InstanceType):
            name = str(obj.__class__)
        else:
            name = str(type(obj))
        if self.debug: print "cannot serialize %s (%s)" % (obj, name)
        raise Violation("cannot serialize %s (%s)" % (obj, name))

    def slice(self):
        return self
    def __iter__(self):
        return self # we are our own iterator
    def next(self):
        if self.objectSentDeferred:
            self.objectSentDeferred.callback(None)
            self.objectSentDeferred = None
        if self.sendQueue:
            (obj, self.objectSentDeferred) = self.sendQueue.pop()
            self.streamable = self.streamableInGeneral
            return obj
        if self.protocol.debugSend:
            print "LAST BAG"
        self.producingDeferred = Deferred()
        self.streamable = True
        return self.producingDeferred

    def childAborted(self, f):
        assert self.objectSentDeferred
        self.objectSentDeferred.errback(f)
        self.objectSentDeferred = None
        return None

    def send(self, obj):
        # obj can also be a Slicer, say, a CallSlicer. We return a Deferred
        # which fires when the object has been fully serialized.
        idle = (len(self.protocol.slicerStack) == 1) and not self.sendQueue
        objectSentDeferred = Deferred()
        self.sendQueue.append((obj, objectSentDeferred))
        if idle:
            # wake up
            if self.protocol.debugSend:
                print " waking up to send"
            if self.producingDeferred:
                d = self.producingDeferred
                self.producingDeferred = None
                # TODO: consider reactor.callLater(0, d.callback, None)
                # I'm not sure it's actually necessary, though
                d.callback(None)
        return objectSentDeferred

    def describe(self):
        return "<RootSlicer>"

    def connectionLost(self, why):
        # abandon everything we wanted to send
        if self.objectSentDeferred:
            self.objectSentDeferred.errback(why)
            self.objectSentDeferred = None
        for obj, d in self.sendQueue:
            d.errback(why)
        self.sendQueue = []
            



UnslicerRegistry = {}
UnsafeUnslicerRegistry = {}

def registerUnslicer(opentype, factory, registry=None):
    if registry is None:
        registry = UnslicerRegistry
    assert not registry.has_key(opentype)
    registry[opentype] = factory

def setInstanceState(inst, state):
    """Utility function to default to 'normal' state rules in unserialization.
    """
    if hasattr(inst, "__setstate__"):
        inst.__setstate__(state)
    else:
        inst.__dict__ = state
    return inst

class UnslicerClass(type):
    # auto-register Unslicers
    def __init__(self, name, bases, dict):
        type.__init__(self, name, bases, dict)
        opentype = dict.get('opentype')
        reg = dict.get('unslicerRegistry')
        if opentype:
            registerUnslicer(opentype, self, reg)

class BaseUnslicer:
    __metaclass__ = UnslicerClass
    opentype = None
    implements(tokens.IUnslicer)

    def __init__(self):
        pass

    def describe(self):
        return "??"

    def setConstraint(self, constraint):
        pass

    def start(self, count):
        pass

    def checkToken(self, typebyte, size):
        return # no restrictions

    def openerCheckToken(self, typebyte, size, opentype):
        return self.parent.openerCheckToken(typebyte, size, opentype)

    def open(self, opentype):
        """Return an IUnslicer object based upon the 'opentype' tuple.
        Subclasses that wish to change the way opentypes are mapped to
        Unslicers can do so by changing this behavior.

        This method does not apply constraints, it only serves to map
        opentype into Unslicer. Most subclasses will implement this by
        delegating the request to their parent (and thus, eventually, to the
        RootUnslicer), and will set the new child's .opener attribute so
        that they can do the same. Subclasses that wish to change the way
        opentypes are mapped to Unslicers can do so by changing this
        behavior."""

        return self.parent.open(opentype)

    def doOpen(self, opentype):
        """Return an IUnslicer object based upon the 'opentype' tuple. This
        object will receive all tokens destined for the subnode. 

        If you want to enforce a constraint, you must override this method
        and do two things: make sure your constraint accepts the opentype,
        and set a per-item constraint on the new child unslicer.

        This method gets the IUnslicer from our .open() method. That might
        return None instead of a child unslicer if the they want a
        multi-token opentype tuple, so be sure to check for Noneness before
        adding a per-item constraint.
        """

        return self.open(opentype)

    def receiveChild(self, obj, ready_deferred=None):
        pass

    def reportViolation(self, why):
        return why

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
        # TODO: examine how abandoned child objects could mess up this
        # counter
        pass

    def getObject(self, counter):
        """'None' means 'ask our parent instead'.
        """
        return None

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

class ScopedUnslicer(BaseUnslicer):
    """This Unslicer provides a containing scope for referenceable things
    like lists. It corresponds to the ScopedSlicer base class."""

    def __init__(self):
        BaseUnslicer.__init__(self)
        self.references = {}

    def setObject(self, counter, obj):
        if self.protocol.debugReceive:
            print "setObject(%s): %s{%s}" % (counter, obj, id(obj))
        self.references[counter] = obj

    def getObject(self, counter):
        obj = self.references.get(counter)
        if self.protocol.debugReceive:
            print "getObject(%s) -> %s{%s}" % (counter, obj, id(obj))
        return obj


class LeafUnslicer(BaseUnslicer):
    # inherit from this to reject any child nodes

    # .checkToken in LeafUnslicer subclasses should reject OPEN tokens

    def doOpen(self, opentype):
        raise Violation("'%s' does not accept sub-objects" % self)

class UnicodeUnslicer(LeafUnslicer):
    # accept a UTF-8 encoded string
    opentype = ("unicode",)
    string = None
    constraint = None

    def setConstraint(self, constraint):
        if isinstance(constraint, schema.Any):
            return
        assert isinstance(constraint, schema.StringConstraint)
        self.constraint = constraint

    def checkToken(self, typebyte, size):
        if typebyte != tokens.STRING:
            raise BananaError("UnicodeUnslicer only accepts strings")
        if self.constraint:
            self.constraint.checkToken(typebyte, size)

    def receiveChild(self, obj, ready_deferred=None):
        assert not isinstance(obj, Deferred)
        assert ready_deferred is None
        if self.string != None:
            raise BananaError("already received a string")
        self.string = unicode(obj, "UTF-8")

    def receiveClose(self):
        return self.string, None
    def describe(self):
        return "<unicode>"

class ListUnslicer(BaseUnslicer):
    opentype = ("list",)

    maxLength = None
    itemConstraint = None
    debug = False

    def setConstraint(self, constraint):
        if isinstance(constraint, schema.Any):
            return
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
        return obj

    def receiveChild(self, obj, ready_deferred=None):
        assert ready_deferred is None
        if self.debug:
            print "%s[%d].receiveChild(%s)" % (self, self.count, obj)
        # obj could be a primitive type, a Deferred, or a complex type like
        # those returned from an InstanceUnslicer. However, the individual
        # object has already been through the schema validation process. The
        # only remaining question is whether the larger schema will accept
        # it.
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
            self.list.append("placeholder")
        else:
            self.list.append(obj)

    def printErr(self, why):
        print "ERR!"
        print why.getBriefTraceback()
        log.err(why)

    def receiveClose(self):
        return self.list, None

    def describe(self):
        return "[%d]" % len(self.list)

class TupleUnslicer(BaseUnslicer):
    opentype = ("tuple",)

    debug = False
    constraints = None

    def setConstraint(self, constraint):
        if isinstance(constraint, schema.Any):
            return
        assert isinstance(constraint, schema.TupleConstraint)
        self.constraints = constraint.constraints

    def start(self, count):
        self.list = []
        # indices of .list which are unfilled because of children that could
        # not yet be referenced
        self.num_unreferenceable_children = 0
        self.count = count
        if self.debug:
            print "%s[%d].start with %s" % (self, self.count, self.list)
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
        self.num_unreferenceable_children -= 1
        if self.finished:
            self.checkComplete()
        return obj

    def receiveChild(self, obj, ready_deferred=None):
        assert ready_deferred is None
        if isinstance(obj, Deferred):
            obj.addCallback(self.update, len(self.list))
            obj.addErrback(self.explode)
            self.num_unreferenceable_children += 1
            self.list.append("placeholder")
        else:
            self.list.append(obj)

    def checkComplete(self):
        if self.debug:
            print "%s[%d].checkComplete: %d pending" % \
                  (self, self.count, self.num_unreferenceable_children)
        if self.num_unreferenceable_children:
            # not finished yet, we'll fire our Deferred when we are
            if self.debug:
                print " not finished yet"
            return self.deferred, None
        # list is now complete. We can finish.
        t = tuple(self.list)
        if self.debug:
            print " finished! tuple:%s{%s}" % (t, id(t))
        self.protocol.setObject(self.count, t)
        self.deferred.callback(t)
        return t, None

    def receiveClose(self):
        if self.debug:
            print "%s[%d].receiveClose" % (self, self.count)
        self.finished = 1
        return self.checkComplete()

    def describe(self):
        return "[%d]" % len(self.list)

class SetUnslicer(ListUnslicer):
    opentype = ("set",)
    def receiveClose(self):
        return sets.Set(self.list), None
    
class ImmutableSetUnslicer(ListUnslicer):
    opentype = ("immutable-set",)
    def receiveClose(self):
        return sets.ImmutableSet(self.list), None


class DictUnslicer(BaseUnslicer):
    opentype = ('dict',)

    gettingKey = True
    keyConstraint = None
    valueConstraint = None
    maxKeys = None

    def setConstraint(self, constraint):
        if isinstance(constraint, schema.Any):
            return
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

    def receiveChild(self, obj, ready_deferred=None):
        assert not isinstance(obj, Deferred)
        assert ready_deferred is None
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
            raise BananaError("incomplete object as dictionary key")
        try:
            if self.d.has_key(key):
                raise BananaError("duplicate key '%s'" % key)
        except TypeError:
            raise BananaError("unhashable key '%s'" % key)
        self.key = key

    def receiveValue(self, value):
        if isinstance(value, Deferred):
            value.addCallback(self.update, self.key)
            value.addErrback(log.err)
        self.d[self.key] = value # placeholder

    def receiveClose(self):
        return self.d, None

    def describe(self):
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
        self.key = None

    def checkToken(self, typebyte, size):
        if self.key is None:
            if typebyte != tokens.INT:
                raise BananaError("VocabUnslicer only accepts INT keys")
        else:
            if typebyte != tokens.STRING:
                raise BananaError("VocabUnslicer only accepts STRING values")

    def receiveChild(self, token, ready_deferred=None):
        assert not isinstance(token, Deferred)
        assert ready_deferred is None
        if self.key is None:
            if self.d.has_key(token):
                raise BananaError("duplicate key '%s'" % token)
            self.key = token
        else:
            self.d[self.key] = token
            self.key = None

    def receiveClose(self):
        return NewVocabulary(self.d), None

    def describe(self):
        if self.key is not None:
            return "<vocabdict>[%s]" % self.key
        else:
            return "<vocabdict>"



class Dummy:
    def __repr__(self):
        return "<Dummy %s>" % self.__dict__
    def __cmp__(self, other):
        if not type(other) == type(self):
            return -1
        return cmp(self.__dict__, other.__dict__)


class InstanceUnslicer(BaseUnslicer):
    # this is an unsafe unslicer: an attacker could induce you to create
    # instances of arbitrary classes with arbitrary attributes: VERY
    # DANGEROUS!
    opentype = ('instance',)
    unslicerRegistry = UnsafeUnslicerRegistry
    
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
        self.classname = None
        self.attrname = None
        self.deferred = Deferred()
        self.protocol.setObject(count, self.deferred)

    def checkToken(self, typebyte, size):
        if self.classname is None:
            if typebyte not in (tokens.STRING, tokens.VOCAB):
                raise BananaError("InstanceUnslicer classname must be string")
        elif self.attrname is None:
            if typebyte not in (tokens.STRING, tokens.VOCAB):
                raise BananaError("InstanceUnslicer keys must be STRINGs")

    def receiveChild(self, obj, ready_deferred=None):
        assert ready_deferred is None
        if self.classname is None:
            self.classname = obj
            self.attrname = None
        elif self.attrname is None:
            self.attrname = obj
        else:
            if isinstance(obj, Deferred):
                # TODO: this is an artificial restriction, and it might
                # be possible to remove it, but I need to think through
                # it carefully first
                raise BananaError("unreferenceable object in attribute")
            if self.d.has_key(self.attrname):
                raise BananaError("duplicate attribute name '%s'" % name)
            self.setAttribute(self.attrname, obj)
            self.attrname = None

    def setAttribute(self, name, value):
        self.d[name] = value

    def receiveClose(self):
        # you could attempt to do some value-checking here, but there would
        # probably still be holes

        #obj = Dummy()
        klass = reflect.namedObject(self.classname)
        assert type(klass) == types.ClassType # TODO: new-style classes
        obj = instance(klass, {})

        setInstanceState(obj, self.d)

        self.protocol.setObject(self.count, obj)
        self.deferred.callback(obj)
        return obj, None

    def describe(self):
        if self.classname is None:
            return "<??>"
        me = "<%s>" % self.classname
        if self.attrname is None:
            return "%s.attrname??" % me
        else:
            return "%s.%s" % (me, self.attrname)

class ReferenceUnslicer(LeafUnslicer):
    opentype = ('reference',)

    constraint = None
    finished = False

    def setConstraint(self, constraint):
        self.constraint = constraint

    def checkToken(self, typebyte,size):
        if typebyte != tokens.INT:
            raise BananaError("ReferenceUnslicer only accepts INTs")

    def receiveChild(self, obj, ready_deferred=None):
        assert not isinstance(obj, Deferred)
        assert ready_deferred is None
        if self.finished:
            raise BananaError("ReferenceUnslicer only accepts one int")
        self.obj = self.protocol.getObject(obj)
        self.finished = True
        # assert that this conforms to the constraint
        if self.constraint:
            self.constraint.checkObject(self.obj)
        # TODO: it might be a Deferred, but we should know enough about the
        # incoming value to check the constraint. This requires a subclass
        # of Deferred which can give us the metadata.

    def receiveClose(self):
        return self.obj, None

class ModuleUnslicer(LeafUnslicer):
    opentype = ('module',)
    unslicerRegistry = UnsafeUnslicerRegistry

    finished = False

    def checkToken(self, typebyte, size):
        if typebyte not in (tokens.STRING, tokens.VOCAB):
            raise BananaError("ModuleUnslicer only accepts strings")

    def receiveChild(self, obj, ready_deferred=None):
        assert not isinstance(obj, Deferred)
        assert ready_deferred is None
        if self.finished:
            raise BananaError("ModuleUnslicer only accepts one string")
        self.finished = True
        # TODO: taste here!
        mod = __import__(obj, {}, {}, "x")
        self.mod = mod

    def receiveClose(self):
        if not self.finished:
            raise BananaError("ModuleUnslicer requires a string")
        return self.mod, None

class ClassUnslicer(LeafUnslicer):
    opentype = ('class',)
    unslicerRegistry = UnsafeUnslicerRegistry

    finished = False

    def checkToken(self, typebyte, size):
        if typebyte not in (tokens.STRING, tokens.VOCAB):
            raise BananaError("ClassUnslicer only accepts strings")

    def receiveChild(self, obj, ready_deferred=None):
        assert not isinstance(obj, Deferred)
        assert ready_deferred is None
        if self.finished:
            raise BananaError("ClassUnslicer only accepts one string")
        self.finished = True
        # TODO: taste here!
        self.klass = reflect.namedObject(obj)

    def receiveClose(self):
        if not self.finished:
            raise BananaError("ClassUnslicer requires a string")
        return self.klass, None

class MethodUnslicer(BaseUnslicer):
    opentype = ('method',)
    unslicerRegistry = UnsafeUnslicerRegistry

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
                raise BananaError("MethodUnslicer methodname must be a string")
        elif self.state == 1:
            if typebyte != tokens.OPEN:
                raise BananaError("MethodUnslicer instance must be OPEN")
        elif self.state == 2:
            if typebyte != tokens.OPEN:
                raise BananaError("MethodUnslicer class must be an OPEN")

    def doOpen(self, opentype):
        # check the opentype
        if self.state == 1:
            if opentype[0] not in ("instance", "none"):
                raise BananaError("MethodUnslicer instance must be " +
                                  "instance or None")
        elif self.state == 2:
            if opentype[0] != "class":
                raise BananaError("MethodUnslicer class must be a class")
        unslicer = self.open(opentype)
        # TODO: apply constraint
        return unslicer

    def receiveChild(self, obj, ready_deferred=None):
        assert not isinstance(obj, Deferred)
        assert ready_deferred is None
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
            raise BananaError("MethodUnslicer only accepts three objects")

    def receiveClose(self):
        if self.state != 3:
            raise BananaError("MethodUnslicer requires three objects")
        if self.im_self is None:
            meth = getattr(self.im_class, self.im_func)
            # getattr gives us an unbound method
            return meth, None
        # TODO: late-available instances
        #if isinstance(self.im_self, NotKnown):
        #    im = _InstanceMethod(self.im_name, self.im_self, self.im_class)
        #    return im
        meth = self.im_class.__dict__[self.im_func]
        # whereas __dict__ gives us a function
        im = instancemethod(meth, self.im_self, self.im_class)
        return im, None
        

class FunctionUnslicer(LeafUnslicer):
    opentype = ('function',)
    unslicerRegistry = UnsafeUnslicerRegistry

    finished = False

    def checkToken(self, typebyte, size):
        if typebyte not in (tokens.STRING, tokens.VOCAB):
            raise BananaError("FunctionUnslicer only accepts strings")

    def receiveChild(self, obj, ready_deferred=None):
        assert not isinstance(obj, Deferred)
        assert ready_deferred is None
        if self.finished:
            raise BananaError("FunctionUnslicer only accepts one string")
        self.finished = True
        # TODO: taste here!
        self.func = reflect.namedObject(obj)

    def receiveClose(self):
        if not self.finished:
            raise BananaError("FunctionUnslicer requires a string")
        return self.func, None

class NoneUnslicer(LeafUnslicer):
    opentype = ('none',)

    def checkToken(self, typebyte, size):
        raise BananaError("NoneUnslicer does not accept any tokens")
    def receiveClose(self):
        return None, None

class BooleanUnslicer(LeafUnslicer):
    opentype = ('boolean',)

    value = None
    constraint = None

    def setConstraint(self, constraint):
        if isinstance(constraint, schema.Any):
            return
        assert isinstance(constraint, schema.BooleanConstraint)
        self.constraint = constraint

    def checkToken(self, typebyte, size):
        if typebyte != tokens.INT:
            raise BananaError("BooleanUnslicer only accepts an INT token")
        if self.value != None:
            raise BananaError("BooleanUnslicer only accepts one token")

    def receiveChild(self, obj, ready_deferred=None):
        assert not isinstance(obj, Deferred)
        assert ready_deferred is None
        assert type(obj) == int
        if self.constraint:
            if self.constraint.value != None:
                if bool(obj) != self.constraint.value:
                    raise Violation("This boolean can only be %s" % \
                                    self.constraint.value)
        self.value = bool(obj)

    def receiveClose(self):
        return self.value, None

    def describe(self):
        return "<bool>"


class RootUnslicer(BaseUnslicer):
    # topRegistry is used for top-level objects
    topRegistry = [UnslicerRegistry]
    # openRegistry is used for everything at lower levels
    openRegistry = [UnslicerRegistry]
    constraint = None
    openCount = None

    def __init__(self):
        self.objects = {}
        keys = []
        for r in self.topRegistry + self.openRegistry:
            for k in r.keys():
                keys.append(len(k[0]))
        self.maxIndexLength = reduce(max, keys)

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
            return
        else:
            # TODO: hack for testing
            raise Violation("index token 0x%02x not STRING or VOCAB" % \
                              ord(typebyte))
            raise BananaError("index token 0x%02x not STRING or VOCAB" % \
                              ord(typebyte))

    def open(self, opentype):
        # called (by delegation) by the top Unslicer on the stack, regardless
        # of what kind of unslicer it is. This is only used for "internal"
        # objects: non-top-level nodes
        assert len(self.protocol.receiveStack) > 1
        for reg in self.openRegistry:
            opener = reg.get(opentype)
            if opener is not None:
                child = opener()
                return child
        else:
            raise Violation("unknown OPEN type %s" % (opentype,))

    def doOpen(self, opentype):
        # this is only called for top-level objects
        assert len(self.protocol.receiveStack) == 1
        if self.constraint:
            self.constraint.checkOpentype(opentype)
        if opentype == ("vocab",):
            # only legal at top-level
            return VocabUnslicer()
        for reg in self.topRegistry:
            opener = reg.get(opentype)
            if opener is not None:
                child = opener()
                break
        else:
            raise Violation("unknown top-level OPEN type %s" % (opentype,))

        if self.constraint:
            child.setConstraint(self.constraint)
        return child

    def receiveChild(self, obj, ready_deferred=None):
        assert not isinstance(obj, Deferred)
        assert ready_deferred is None
        if self.protocol.debugReceive:
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

    def reportViolation(self, why):
        return self.protocol.reportViolation(why)

    def describe(self):
        return "<RootUnslicer>"

    def setObject(self, counter, obj):
        pass

    def getObject(self, counter):
        return None

