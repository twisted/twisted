#! /usr/bin/python

import types
from pickle import whichmodule  # used by FunctionSlicer
from new import instance, instancemethod

from twisted.python.failure import Failure
from twisted.python.components import registerAdapter
from zope.interface import implements
from twisted.internet.defer import Deferred
from twisted.python import log, reflect

import tokens
from tokens import Violation, BananaError, tokenNames, UnbananaFailure
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
    implements(tokens.ISlicer)

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
        assert self.opentype
        for o in self.opentype:
            yield o
        for t in self.sliceBody(streamable, banana):
            yield t
    def sliceBody(self, streamable, banana):
        raise NotImplementedError
    def childAborted(self, v):
        raise v

    def describe(self):
        return "??"


class ScopedSlicer(BaseSlicer):
    """This Slicer provides a containing scope for referenceable things like
    lists. The same list will not be serialized twice within this scope, but
    it will not survive outside it."""

    def __init__(self, obj):
        BaseSlicer.__init__(self, obj)
        self.references = {}

    def registerReference(self, refid, obj):
        # keep references here, not in the actual PBRootSlicer
        self.references[id(obj)] = refid

    def slicerForObject(self, obj):
        # check for an object which was sent previously or has at least
        # started sending
        refid = self.references.get(id(obj), None)
        if refid is not None:
            return ReferenceSlicer(refid)
        # otherwise go upstream
        return self.parent.slicerForObject(obj)


class UnicodeSlicer(BaseSlicer):
    opentype = ("unicode",)
    def sliceBody(self, streamable, banana):
        yield self.obj.encode("UTF-8")
registerAdapter(UnicodeSlicer, unicode, tokens.ISlicer)

class ListSlicer(BaseSlicer):
    opentype = ("list",)
    trackReferences = True

    def sliceBody(self, streamable, banana):
        for i in self.obj:
            yield i
registerAdapter(ListSlicer, list, tokens.ISlicer)

class TupleSlicer(ListSlicer):
    opentype = ("tuple",)
registerAdapter(TupleSlicer, tuple, tokens.ISlicer)

class DictSlicer(BaseSlicer):
    opentype = ('dict',)
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
registerAdapter(OrderedDictSlicer, dict, tokens.ISlicer)

class NoneSlicer(BaseSlicer):
    opentype = ('none',)
    trackReferences = False
    def sliceBody(self, streamable, banana):
        # hmm, we need an empty generator. I think a sequence is the only way
        # to accomplish this, other than 'if 0: yield' or something silly
        return []
registerAdapter(NoneSlicer, types.NoneType, tokens.ISlicer)

class BooleanSlicer(BaseSlicer):
    opentype = ('boolean',)
    trackReferences = False
    def sliceBody(self, streamable, banana):
        if self.obj:
            yield 1
        else:
            yield 0

try:
    from types import BooleanType
    registerAdapter(BooleanSlicer, bool, tokens.ISlicer)
except ImportError:
    pass


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
    })


class RootSlicer:
    implements(tokens.ISlicer)

    producingDeferred = None
    objectSentDeferred = None
    slicerTable = {}
    debug = False

    def __init__(self, sendbanana):
        self.sendbanana = sendbanana
        self.sendQueue = []

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
        if self.debug: print "cannot serialize %s %s" % (obj, type(obj))
        raise Violation("cannot serialize %s (%s)" % (obj, type(obj)))

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
            return obj
        if self.sendbanana.debugSend:
            print "LAST BAG"
        self.producingDeferred = Deferred()
        return self.producingDeferred

    def childAborted(self, v):
        assert self.objectSentDeferred
        self.objectSentDeferred.errback(v)
        self.objectSentDeferred = None

    def send(self, obj):
        # obj can also be a Slicer, say, a CallSlicer. We return a Deferred
        # which fires when the object has been fully serialized.
        idle = (len(self.sendbanana.slicerStack) == 1) and not self.sendQueue
        objectSentDeferred = Deferred()
        self.sendQueue.append((obj, objectSentDeferred))
        if idle:
            # wake up
            if self.producingDeferred:
                d = self.producingDeferred
                self.producingDeferred = None
                # TODO: consider reactor.callLater(0, d.callback, None)
                # I'm not sure it's actually necessary, though
                d.callback(None)
        return objectSentDeferred

class UnsafeRootSlicer(RootSlicer):
    slicerTable = UnsafeSlicerTable

class StorageRootSlicer(UnsafeRootSlicer):
    # some pieces taken from ScopedSlicer
    def __init__(self, sendbanana):
        UnsafeRootSlicer.__init__(self, sendbanana)
        self.references = {}

    def registerReference(self, refid, obj):
        self.references[id(obj)] = refid

    def slicerForObject(self, obj):
        # check for an object which was sent previously or has at least
        # started sending
        refid = self.references.get(id(obj), None)
        if refid is not None:
            return ReferenceSlicer(refid)
        # otherwise go upstream
        return UnsafeRootSlicer.slicerForObject(self, obj)


def setInstanceState(inst, state):
    """Utility function to default to 'normal' state rules in unserialization.
    """
    if hasattr(inst, "__setstate__"):
        inst.__setstate__(state)
    else:
        inst.__dict__ = state
    return inst

class BaseUnslicer:
    implements(tokens.IUnslicer)

    def __init__(self):
        pass

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
        self.key = None

    def checkToken(self, typebyte, size):
        if self.key is None:
            if typebyte != tokens.INT:
                raise BananaError("VocabUnslicer only accepts INT keys",
                                  self.where())
        else:
            if typebyte != tokens.STRING:
                raise BananaError("VocabUnslicer only accepts STRING values",
                                  self.where())

    def receiveChild(self, token):
        self.propagateUnbananaFailures(token)
        if self.key is None:
            if self.d.has_key(token):
                raise BananaError("duplicate key '%s'" % token,
                                  self.where())
            self.key = token
        else:
            self.d[self.key] = token
            self.key = None

    def receiveClose(self):
        return NewVocabulary(self.d)

    def describeSelf(self):
        if self.key is not None:
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
    # this is an unsafe unslicer: an attacker could induce you to create
    # instances of arbitrary classes with arbitrary attributes: VERY
    # DANGEROUS!
    
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
                raise BananaError("InstanceUnslicer classname must be string",
                                  self.where())
        elif self.attrname is None:
            if typebyte not in (tokens.STRING, tokens.VOCAB):
                raise BananaError("InstanceUnslicer keys must be STRINGs",
                                  self.where())

    def receiveChild(self, obj):
        self.propagateUnbananaFailures(obj)
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
                raise BananaError("unreferenceable object in attribute",
                                  self.where())
            if self.d.has_key(self.attrname):
                raise BananaError("duplicate attribute name '%s'" % name,
                                  self.where())
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
        return obj

    def describeSelf(self):
        if self.classname is None:
            return "<??>"
        me = "<%s>" % self.classname
        if self.attrname is None:
            return "%s.attrname??" % me
        else:
            return "%s.%s" % (me, self.attrname)

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
    ('reference',): ReferenceUnslicer,
    ('none',): NoneUnslicer,
    ('boolean',): BooleanUnslicer,
    # for testing
    ('dict1',): BrokenDictUnslicer,
    ('dict2',): ReallyBrokenDictUnslicer,
    }
        
UnsafeUnslicerRegistry = UnslicerRegistry.copy()
UnsafeUnslicerRegistry.update({
    ('instance',): InstanceUnslicer,
    ('module',): ModuleUnslicer,
    ('class',): ClassUnslicer,
    ('method',): MethodUnslicer,
    ('function',): FunctionUnslicer,
    })


class RootUnslicer(BaseUnslicer):
    # topRegistry is used for top-level objects
    topRegistry = UnslicerRegistry
    # openRegistry is used for everything at lower levels
    openRegistry = UnslicerRegistry
    constraint = None

    def __init__(self):
        self.objects = {}
        maxLength = reduce(max,
                           [len(k[0]) for k in (self.openRegistry.keys() +
                                                self.topRegistry.keys()) ])
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
            return
        else:
            # TODO: hack for testing
            raise Violation("index token 0x%02x not STRING or VOCAB" % \
                              ord(typebyte))
            raise BananaError("index token 0x%02x not STRING or VOCAB" % \
                              ord(typebyte))

    def open(self, opentype):
        # called (by delegation) by the top Unslicer on the stack,
        # regardless of what kind of unslicer it is.
        assert len(self.protocol.receiveStack) > 1
        try:
            opener = self.openRegistry[opentype]
            child = opener()
        except KeyError:
            raise Violation("unknown OPEN type %s" % (opentype,))
        return child

    def doOpen(self, opentype):
        # this is only called for top-level objects
        assert len(self.protocol.receiveStack) == 1
        if self.constraint:
            self.constraint.checkOpentype(opentype)
        if opentype == ("vocab",):
            # only legal at top-level
            return VocabUnslicer()
        try:
            opener = self.topRegistry[opentype]
            child = opener()
        except KeyError:
            raise Violation("unknown top-level OPEN type %s" % (opentype,))
            
        if self.constraint:
            child.setConstraint(self.constraint)
        return child

    def receiveChild(self, obj):
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

    def describeSelf(self):
        return "root"

    def setObject(self, counter, obj):
        pass

    def getObject(self, counter):
        return None


class UnsafeRootUnslicer(RootUnslicer):
    topRegistry = UnsafeUnslicerRegistry
    openRegistry = UnsafeUnslicerRegistry

class StorageRootUnslicer(UnsafeRootUnslicer, ScopedUnslicer):
    # this version tracks references for the entire lifetime of the protocol
    def __init__(self):
        ScopedUnslicer.__init__(self)
        UnsafeRootUnslicer.__init__(self)
    
    def setObject(self, counter, obj):
        return ScopedUnslicer.setObject(self, counter, obj)
    def getObject(self, counter):
        return ScopedUnslicer.getObject(self, counter)
