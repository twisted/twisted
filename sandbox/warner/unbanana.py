#! /usr/bin/python

from twisted.python.failure import Failure
from twisted.internet.defer import Deferred
from twisted.python import log
import types

class IBananaUnslicer:
    # .parent

    # start/receiveToken/receiveChild/receiveAbort/finish are the main "here
    # are some tokens, make an object out of them" entry points used by
    # Unbanana

    def start(self, count):
        """Called to initialize the new slice. The 'count' argument is the
        reference id: if this object might be shared (and therefore the
        target of a 'reference' token), it should call
        self.unbanana.setObject(count, obj) with the object being created.
        If this object is not available yet (tuples), it should save a
        Deferred there instead.
        """

    def receiveToken(self, token):
        """token will be a number or a string."""

    def receiveChild(self, childobject):
        """The unslicer returned in receiveOpen has finished. 'childobject'
        is the object created by that unslicer. It might be an
        UnjellyingFailure if something went wrong, in which card it may be
        appropriate to do self.unbanana.startDiscarding(childobject, self).
        It might also be a Deferred, in which case you should add a callback
        that will fill in the appropriate object later."""

    def receiveAbort(self):
        """An 'abort' token was received (indicating something went wrong in
        the sender). The new object being created should be abandoned. The
        unslicer can do self.unbanana.startDiscarding(failure, self) to
        have itself replaced with a DiscardUnslicer object."""

    def finish(self):
        """Called when the Close token is received. Should return the object
        just created, or an UnjellyingFailure if something went wrong. If
        necessary, unbanana.setObject should be called, then the Deferred
        created in start() should be fired with the new object."""


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

class BaseUnslicer:
    def __init__(self):
        pass

    def describe(self):
        return "??"


    def start(self, count):
        pass

    def receiveAbort(self):
        here = self.unbanana.describe()
        failure = UnbananaFailure(here)
        self.unbanana.startDiscarding(failure, self)

    def receiveToken(self, token):
        raise NotImplementedError

    def finish(self):
        raise NotImplementedError

    def childFinished(self, obj):
        if isinstance(obj, UnbananaFailure):
            if self.unbanana.debug: print "%s .childFinished for UF" % self
            self.unbanana.startDiscarding(obj, self)
        self.receiveChild(obj)

    def receiveChild(self, obj):
        pass


    def doOpen(self, opentype):
        """Return an IBananaUnslicer object based upon the 'opentype'
        string. This object will receive all tokens destined for the
        subnode. The first node to return something other than None will
        stop the search. To get the default behavior (bypassing deeper
        nodes), return UnslicerParent.doOpen() directly.
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
        UnslicerParent, but child slices could do it too if they wished.
        """
        pass

    def getObject(self, counter):
        """'None' means 'ask our parent instead'.
        """
        return None


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
    def childFinished(self, o):
        pass
    def receiveAbort(self):
        pass # we're already discarding
    def finish(self):
        if self.unbanana.debug: print "DiscardUnslicer.finish"
        return self.failure

    def describe(self):
        return "discard"
    def doOpen(self, opentype):
        return DiscardUnslicer()

class ListUnslicer(BaseUnslicer):
    debug = 0
    
    def start(self, count):
        self.list = []
        self.count = count
        if self.debug:
            print "%s[%d].start with %s" % (self, self.count, self.list)
        self.unbanana.setObject(count, self.list)

    def update(self, obj, index):
        if self.debug:
            print "%s[%d].update: [%d]=%s" % (self, self.count, index, obj)
        assert(type(index) == types.IntType)
        self.list[index] = obj

    def receiveToken(self, token):
        if self.unbanana.debug or self.debug:
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

    def finish(self):
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
        self.unbanana.setObject(count, self.deferred)

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
        self.unbanana.setObject(self.count, t)
        self.deferred.callback(t)
        return t

    def finish(self):
        if self.debug:
            print "%s[%d].finish" % (self, self.count)
        self.stoppedAdding = 1
        return self.checkComplete()


class DictUnslicer(BaseUnslicer):
    haveKey = 0

    def start(self, count):
        self.d = {}
        self.unbanana.setObject(count, self.d)
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


    def finish(self):
        return self.d

    def describe(self):
        if self.haveKey:
            return "{}[%s]" % self.key
        else:
            return "{}"


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

    def finish(self):
        if self.dieInFinish:
            raise "dead in finish()"
        DictUnslicer.finish(self)

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
        self.unbanana.setObject(count, self.deferred)
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

    def finish(self):
        o = Dummy()
        #o.__classname__ = self.classname
        o.__dict__ = self.d
        self.unbanana.setObject(self.count, o)
        self.deferred.callback(o)
        return o

    def describe(self):
        if self.classname == None:
            return "<??>"
        me = "<%s>" % self.classname
        if self.haveKey:
            return "%s.%s" % (me, self.key)
        return "%s.attrname??" % me


class ReferenceUnslicer(BaseUnslicer):

    def receiveToken(self, token):
        if hasattr(self, 'obj'):
            raise ValueError, "'reference' token already got number"
        if type(token) != types.IntType:
            raise ValueError, "'reference' token requires integer"
        self.obj = self.unbanana.getObject(token)

    def receiveChild(self, obj):
        raise ValueError, "'reference' token requires integer"

    def doOpen(self, opentype):
        raise ValueError, "'reference' token requires integer"

    def finish(self):
        return self.obj
        

        
UnslicerRegistry = {
    'list': ListUnslicer,
    'tuple': TupleUnslicer,
    'dict': DictUnslicer,
    'instance': InstanceUnslicer,
    'reference': ReferenceUnslicer,
    # for testing
    'dict1': BrokenDictUnslicer,
    'dict2': ReallyBrokenDictUnslicer,
    }

    
class UnslicerParent(BaseUnslicer):
    def __init__(self):
        self.objects = {}

    def start(self, count):
        pass

    def doOpen(self, opentype):
        return UnslicerRegistry[opentype]()

    def receiveToken(self, token):
        raise ValueError, "top-level should never receive non-OPEN tokens"

    def receiveAbort(self, token):
        raise ValueError, "top-level should never receive ABORT tokens"

    def childFinished(self, o):
        self.objects = {}
        self.unbanana.childFinished(o) # send it somewhere

    def finish(self):
        raise ValueError, "top-level should never receive CLOSE tokens"

    def describe(self):
        return "root"


    def setObject(self, counter, obj):
        if self.unbanana.debug:
            print "setObject(%s): %s{%s}" % (counter, obj, id(obj))
        self.objects[counter] = obj

    def getObject(self, counter):
        obj = self.objects.get(counter)
        if self.unbanana.debug:
            print "getObject(%s) -> %s{%s}" % (counter, obj, id(obj))
        return obj


class Unbanana:
    debug = 0

    def __init__(self):
        parent = UnslicerParent()
        parent.unbanana = self
        self.stack = [parent]
        self.objectCounter = 0
        self.objects = {}

    def startDiscarding(self, failure, leaf):
        """Begin discarding everything in the current node. When the node is
        complete, the given failure is handed to the parent. This is
        implemented by replacing the current node with a DiscardUnslicer.
        
        Slices call startDiscarding in response to an ABORT token or when
        their receiveChild() method is handed a failure object. The Unslicer
        will do startDiscarding when a slice raises an exception.

        The 'leaf' argument is just for development paranoia and will go
        away soon.
        """
        if self.debug:
            print "startDiscarding", failure.where
            import traceback
            traceback.print_stack()
            if failure.failure:
                print failure.failure.getBriefTraceback()
        assert(self.stack[-1] == leaf)
        d = DiscardUnslicer(failure)
        d.unbanana = self
        d.openCount = self.stack[-1].openCount
        self.stack[-1] = d
        if self.debug:
            self.printStack()


    def setObject(self, count, obj):
        for i in range(len(self.stack)-1, -1, -1):
            self.stack[i].setObject(count, obj)

    def getObject(self, count):
        for i in range(len(self.stack)-1, -1, -1):
            obj = self.stack[i].getObject(count)
            if obj is not None:
                return obj
        raise ValueError, "dangling reference '%d'" % count


    def printStack(self, verbose=0):
        print "STACK:"
        for s in self.stack:
            if verbose:
                d = s.__dict__.copy()
                del d['unbanana']
                print " %s: %s" % (s, d)
            else:
                print " %s" % s


    def handleOpen(self, token):
        openCount = token[2]
        objectCount = self.objectCounter
        self.objectCounter += 1
        opentype = token[1]
        try:
            # ask openers what to use
            child = None
            for i in range(len(self.stack)-1, -1, -1):
                child = self.stack[i].doOpen(opentype)
                if child:
                    break
            if child == None:
                raise "nothing to open"
            if self.debug:
                print "opened[%d] with %s" % (openCount, child)
        except:
            if self.debug:
                print "failed to open anything, pushing DiscardUnslicer"
            where = self.describe() + ".<OPEN%s>" % opentype
            uf = UnbananaFailure(where, Failure())
            child = DiscardUnslicer(uf)
        child.unbanana = self
        child.openCount = openCount
        self.stack.append(child)
        try:
            child.start(objectCount)
        except:
            where = self.describe() + ".<START>"
            f = UnbananaFailure(where, Failure())
            self.startDiscarding(f, child)

    def handleClose(self, token):
        closeCount = token[1]
        if self.stack[-1].openCount != closeCount:
            print "LOST SYNC"
            self.printStack()
            assert(0)
        try:
            if self.debug:
                print "finish()"
            o = self.stack[-1].finish()
        except:
            where = self.describe() + ".<CLOSE>"
            o = UnbananaFailure(where, Failure())
        if self.debug: print "finish returned", o
        self.stack.pop()
        try:
            if self.debug: print "receiveChild()"
            self.stack[-1].childFinished(o)
        except:
            where = self.describe()
            # this is just like receiveToken failing
            f = UnbananaFailure(where, Failure())
            self.startDiscarding(f, self.stack[-1])

    def receiveToken(self, token):
        # future optimization note: most Unslicers on the stack will not
        # override .taste or .doOpen, so it would be faster to have the few
        # that *do* add themselves to a separate .openers and/or .tasters
        # stack. The issue is robustness: if the Unslicer is thrown out
        # because of an exception or an ABORT token (i.e. startDiscarding is
        # called), we must be sure to clean out their opener/taster too and
        # not leave it dangling. Having them implemented as methods inside
        # the Unslicer makes that easy, but means a full traversal of the
        # stack for each token even when nobody is doing any tasting.

        for i in range(len(self.stack)-1, -1, -1):
            self.stack[i].taste(token)

        if self.debug:
            print "receiveToken(%s)" % (token,)

        if type(token) == types.TupleType and token[0] == "OPEN":
            self.handleOpen(token)
            return

        if type(token) == types.TupleType and token[0] == "CLOSE":
            self.handleClose(token)
            return

        if type(token) == types.TupleType and token[0] == "ABORT":
            # let the unslicer decide what to do. The default is to do
            # self.startDiscarding()
            if self.debug: print "receiveAbort()"
            self.stack[-1].receiveAbort()
            return

        top = self.stack[-1]
        if self.debug: print "receivetoken(%s)" % token
        try:
            top.receiveToken(token)
        except:
            # need to give up on the current stack top
            f = UnbananaFailure(self.describe(), Failure())
            self.startDiscarding(f, top)
            return


    def describe(self):
        where = []
        for i in self.stack:
            try:
                piece = i.describe()
            except:
                piece = "???"
            where.append(piece)
        return ".".join(where)

    def childFinished(self, o):
        self.object = o

    def processTokens(self, tokens):
        self.object = None
        for t in tokens:
            self.receiveToken(t)
        return self.object

    def step(self, token):
        rv = self.processTokens([token])
        self.printStack(1)
        return rv


def Tester():
    u = Unbanana()
    u.object = None
    return u
