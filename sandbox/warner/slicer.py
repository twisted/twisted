#! /usr/bin/python

from twisted.python.failure import Failure
from twisted.internet.defer import Deferred
from twisted.python import log, reflect
import types
from pickle import whichmodule  # used by FunctionSlicer
from new import instance, instancemethod

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

    # start/receiveToken/receiveChild/receiveAbort/receiveClose are the main
    # "here are some tokens, make an object out of them" entry points used
    # by Unbanana

    def start(self, count):
        """Called to initialize the new slice. The 'count' argument is the
        reference id: if this object might be shared (and therefore the
        target of a 'reference' token), it should call
        self.protocol.setObject(count, obj) with the object being created.
        If this object is not available yet (tuples), it should save a
        Deferred there instead.
        """

    def receiveToken(self, token):
        """token will be a number or a string."""

    def receiveChild(self, childobject):
        """The unslicer returned in receiveOpen has finished. 'childobject'
        is the object created by that unslicer. It might be an
        UnjellyingFailure if something went wrong, in which card it may be
        appropriate to do self.protocol.startDiscarding(childobject, self).
        It might also be a Deferred, in which case you should add a callback
        that will fill in the appropriate object later."""

    def receiveAbort(self):
        """An 'abort' token was received (indicating something went wrong in
        the sender). The new object being created should be abandoned. The
        unslicer can do self.protocol.startDiscarding(failure, self) to
        have itself replaced with a DiscardUnslicer object."""

    def receiveClose(self):
        """Called when the Close token is received. Should return the object
        just created, or an UnjellyingFailure if something went wrong. If
        necessary, unbanana.setObject should be called, then the Deferred
        created in start() should be fired with the new object."""

    def finish(self):
        """Called when the unslicer is popped off the stack. This is called
        even if the pop is because of an exception. The unslicer should
        perform cleanup and remove itself from any other stacks it may have
        added itself to."""

    def description(self):
        """Return a short string describing where in the object tree this
        unslicer is sitting. A list of these strings will be used to
        describe where any problems occurred."""

    def receiveOpen(self, opentype):
        """this Unslicer gets to decide what should be pushed on the stack.
        Return None to defer the request to someone deeper in the stack.
        Otherwise return a new IBananaUnslicer-capable object"""



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


    def start(self, count):
        pass

    def receiveAbort(self):
        here = self.protocol.describe()
        failure = UnbananaFailure(here)
        self.protocol.startDiscarding(failure, self)

    def receiveToken(self, token):
        raise NotImplementedError

    def receiveClose(self):
        raise NotImplementedError

    def childFinished(self, unslicer, obj):
        if isinstance(obj, UnbananaFailure):
            if self.protocol.debug: print "%s .childFinished for UF" % self
            self.protocol.startDiscarding(obj, self)
        self.receiveChild(obj)

    def receiveChild(self, obj):
        pass

    def finish(self):
        pass

    def doOpen(self, opentype):
        """Return an IBananaUnslicer object based upon the 'opentype'
        string. This object will receive all tokens destined for the
        subnode. The first node to return something other than None will
        stop the search. To get the default behavior (bypassing deeper
        nodes), return RootUnslicer.doOpen() directly.
        """
        return None # means "defer to the node above me"

    def taste(self, token):
        """All tasters on the taster stack get to pass judgement upon the
        incoming tokens. If they don't like what they see, they should raise
        an InsecureUnbanana exception.
        """
        # TODO: This isn't really all that useful. A hook that made it easy
        # to catch instances of certain classes would probably have more
        # real-world applications
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
    def receiveChild(self, obj):
        raise ValueError, "'%s' does not accept sub-objects" % self
    def doOpen(self, opentype):
        raise ValueError, "'%s' does not accept sub-objects" % self
    

class DiscardUnslicer(BaseUnslicer):
    """This Unslicer throws out all incoming tokens. It is used to deal
    cleanly with failures: the failing Unslicer is replaced with a
    DiscardUnslicer to eat the rest of its contents without losing sync.
    """
    def __init__(self, failure):
        self.failure = failure

    def start(self, count):
        pass
    def receiveToken(self, token):
        pass
    def childFinished(self, unslicer, obj):
        pass
    def receiveAbort(self):
        pass # we're already discarding
    def receiveClose(self):
        if self.protocol.debug: print "DiscardUnslicer.receiveClose"
        return self.failure

    def describe(self):
        return "discard"
    def doOpen(self, opentype):
        return DiscardUnslicer()

class UnicodeUnslicer(BaseUnslicer):
    def receiveToken(self, token):
        self.string = unicode(token, "UTF-8")
    def receiveChild(self, obj):
        raise ValueError, "UnicodeUnslicer only accepts a single string"
    def receiveClose(self):
        return self.string
    def describe(self):
        return "<unicode>"

class ListUnslicer(BaseUnslicer):
    debug = 0
    
    def start(self, count):
        self.list = []
        self.count = count
        if self.debug:
            print "%s[%d].start with %s" % (self, self.count, self.list)
        self.protocol.setObject(count, self.list)

    def update(self, obj, index):
        if self.debug:
            print "%s[%d].update: [%d]=%s" % (self, self.count, index, obj)
        assert(type(index) == types.IntType)
        self.list[index] = obj

    def receiveToken(self, token):
        if self.protocol.debug or self.debug:
            print "%s[%d].receiveToken(%s{%s})" % (self, self.count,
                                                   token, id(token))
        self.list.append(token)

    def receiveChild(self, obj):
        if self.debug:
            print "%s[%d].receiveChild(%s)" % (self, self.count, obj)
        if isinstance(obj, Deferred):
            if self.debug:
                print " adding my update[%d] to %s" % (len(self.list), obj)
            obj.addCallback(self.update, len(self.list))
            obj.addErrback(self.printErr)
        self.receiveToken(obj)

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
        return self.d

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

    def receiveToken(self, token):
        if hasattr(self, 'obj'):
            raise ValueError, "'reference' token already got number"
        if type(token) != types.IntType:
            raise ValueError, "'reference' token requires integer"
        self.obj = self.protocol.getObject(token)

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
        meth = getattr(self.im_class, self.im_func)
        if self.im_self is None:
            return meth
        # TODO: late-available instances
        #if isinstance(self.im_self, NotKnown):
        #    im = _InstanceMethod(self.im_name, self.im_self, self.im_class)
        #    return im
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

        
UnslicerRegistry = {
    'unicode': UnicodeUnslicer,
    'list': ListUnslicer,
    'tuple': TupleUnslicer,
    'dict': DictUnslicer,
    'instance': InstanceUnslicer,
    'reference': ReferenceUnslicer,
    'none': NoneUnslicer,
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
    def __init__(self):
        self.objects = {}

    def start(self, count):
        pass

    def doOpen(self, opentype):
        if len(self.protocol.receiveStack) == 1 and opentype == "vocab":
            # only legal at top-level
            return VocabUnslicer()
        return UnslicerRegistry[opentype]()

    def receiveToken(self, token):
        raise ValueError, "top-level should never receive non-OPEN tokens"

    def receiveAbort(self, token):
        raise ValueError, "top-level should never receive ABORT tokens"

    def childFinished(self, unslicer, obj):
        self.objects = {}
        if isinstance(unslicer, VocabUnslicer):
            self.protocol.setIncomingVocabulary(obj)
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

class RootUnslicer2(RootUnslicer):

    def doOpen(self, opentype):
        if len(self.protocol.receiveStack) == 1 and opentype == "vocab":
            # only legal at top-level
            return VocabUnslicer()
        return UnslicerRegistry2[opentype]()

    def receiveToken(self, token):
        self.protocol.receivedObject(token)
    
