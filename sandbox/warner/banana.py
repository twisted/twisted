#! /usr/bin/python

from twisted.python.failure import Failure
from twisted.internet.defer import Deferred
from twisted.python import log, reflect
import types

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
                types.StringType, types.UnicodeType)

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
        if type(obj) in SimpleTokens:
            self.banana.sendToken(obj)
        else:
            self.banana.slice(obj)
            # does life stop while we wait for this?

    def start(self, obj):
        # refid is for reference tracking
        assert(self.openID == None)
        self.openID = self.banana.sendOpen(self.opentype)
        if self.trackReferences:
            self.banana.setRefID(obj, self.openID)

    def slice(self, obj):
        """Tokenize the object and send the tokens via
        self.banana.sendToken(). Will be called after open() and before
        finish().
        """
        raise NotImplementedError

    def finish(self, obj):
        assert(self.openID is not None)
        self.banana.sendClose(self.openID)
        self.openID = None

    def abort(self):
        """Stop trying to tokenize the object. Send an ABORT token, then a
        CLOSE. Producers may want to hook this to free up other resources,
        etc.
        """
        self.banana.sendAbort()
        self.banana.sendClose()


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

class InstanceSlicer(OrderedDictSlicer):
    opentype = 'instance'
    trackReferences = 1

    def slice(self, obj):
        self.banana.sendToken(reflect.qual(obj.__class__))
        OrderedDictSlicer.slice(self, getInstanceState(obj)) #DictSlicer

class ReferenceSlicer(BaseSlicer):
    opentype = 'reference'

    def __init__(self, refid):
        BaseSlicer.__init__(self)
        assert(type(refid) == types.IntType)
        self.refid = refid

    def slice(self, obj):
        self.banana.sendToken(self.refid)

class RootSlicer(BaseSlicer):
    # this lives at the bottom of the Slicer stack, at least for our testing
    # purposes

    def __init__(self):
        self.references = {}

    def start(self, obj):
        self.references = {}

    def slice(self, obj):
        self.banana.slice(obj)

    def finish(self, obj):
        self.references = {}

    def newSlicer(self, obj):
        refid = self.banana.getRefID(obj)
        if refid is not None:
            slicer = ReferenceSlicer(refid)
            return slicer
        slicerClass = SlicerRegistry[type(obj)]
        slicer = slicerClass()
        return slicer


    def setRefID(self, obj, refid):
        if self.banana.debug:
            print "setRefID(%s{%s}) -> %s" % (obj, id(obj), refid)
        self.references[id(obj)] = refid

    def getRefID(self, obj):
        refid = self.references.get(id(obj))
        if self.banana.debug:
            print "getObject(%s{%s}) -> %s{%s}" % (obj, id(obj), refid)
        return refid

SlicerRegistry = {
    types.ListType: ListSlicer,
    types.TupleType: TupleSlicer,
    types.DictType: OrderedDictSlicer, #DictSlicer
    types.InstanceType: InstanceSlicer,
    }

class Banana:
    def __init__(self):
        parent = RootSlicer()
        parent.banana = self
        self.stack = [parent]
        self.tokens = []
        self.openCount = 0
        self.debug = 0

    # sendOpen/sendToken/sendClose/sendAbort are called by Slicers to put
    # tokens into the stream

    def sendOpen(self, opentype):
        openID = self.openCount
        self.openCount += 1
        self.sendToken(("OPEN", opentype, openID))
        return openID

    def sendToken(self, token):
        self.tokens.append(token)

    def sendClose(self, openID):
        self.sendToken(("CLOSE", openID))

    def sendAbort(self):
        self.sendToken(("ABORT",))


    def slice(self, obj):
        # let everybody taste it
        for i in range(len(self.stack)-1, -1, -1):
            self.stack[i].taste(obj)
        # find the Slicer object
        child = None
        for i in range(len(self.stack)-1, -1, -1):
            child = self.stack[i].newSlicer(obj)
            if child:
                break
        if child == None:
            raise "nothing to send for obj '%s' (type '%s')" % (obj, type(obj))
        child.banana = self
        self.stack.append(child)
        self.doSlice(obj)
        self.stack.pop(-1)

    def doSlice(self, obj):
        slicer = self.stack[-1]
        slicer.start(obj)
        slicer.slice(obj)
        slicer.finish(obj)

    # setRefID/getRefID are used to walk the stack and handle references

    def setRefID(self, obj, refid):
        for i in range(len(self.stack)-1, -1, -1):
            self.stack[i].setRefID(obj, refid)
    def getRefID(self, refid):
        # this definitely needs to be optimized
        for i in range(len(self.stack)-1, -1, -1):
            obj = self.stack[i].getRefID(refid)
            if obj is not None:
                return obj
        return None


    def testSlice(self, obj):
        assert(len(self.stack) == 1)
        assert(isinstance(self.stack[0],RootSlicer))
        self.tokens = []
        self.doSlice(obj)
        return self.tokens

# flow of control is:
#  Banana.doSlice
#   Banana.slice(obj)
#    stack[0].newSlicer() -> stack[1]
#     stack[1].start, .slice, .finish
