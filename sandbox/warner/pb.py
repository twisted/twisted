#! /usr/bin/python

import weakref

from twisted.python import components, failure
from twisted.internet import defer

import slicer, schema, tokens, banana
from tokens import BananaError, Violation
from slicer import UnbananaFailure

class PendingRequest(object):
    def __init__(self, constraint=None):
        self.deferred = defer.Deferred()
        self.constraint = constraint # this constrains the results

class RemoteReference(object):
    def __init__(self, broker, refID, interfaces=None):
        self.broker = broker
        self.refID = refID
        self.interfaces = interfaces

    def __del__(self):
        self.broker.freeRemoteReference(self.refID)

    def callRemote(self, _name, *args, **kwargs):
        reqID = self.broker.newRequestID()

        # TODO: check args against arg constraint
        assert not args # TODO: turn positional arguments into kwargs

        resultConstraint = None # TODO: get return value constraint
        req = PendingRequest(resultConstraint)
        self.broker.waitingForAnswers[reqID] = req

        child = CallSlicer(self.broker)
        self.broker.slice2(child, (reqID, self.refID, _name, kwargs))

        return req.deferred

class BaseUnslicer(slicer.BaseUnslicer):
    def __init__(self, broker):
        self.broker = broker

class ReferenceUnslicer(BaseUnslicer):
    refID = None
    interfaces = None
    wantInterfaceList = False
    ilistConstraint = schema.ListOf(schema.TupleOf(str, int))

    def checkToken(self, typebyte):
        if self.refID == None:
            if typebyte != tokens.INT:
                raise BananaError("reference ID must be an INT")
        else:
            if self.wantInterfaceList:
                self.ilistConstraint.checkToken(typebyte)
            else:
                raise BananaError("interface list on non-initial receipt")

    def doOpen(self, opentype):
        # only for the interface list
        self.ilistConstraint.checkOpentype(opentype)
        unslicer = self.opener(opentype)
        unslicer.opener = self.opener
        unslicer.setConstraint(self.ilistConstraint)
        return unslicer

    def receiveChild(self, token):
        if isinstance(token, UnbananaFailure):
            self.abort(token)
            return # TODO: if possible, return an error to the other side
        if self.refID == None:
            self.refID = token
            # do we want an interface list? Only if this is the first time
            # this reference has been received
            if not self.broker.remoteReferences.has_key(self.refID):
                self.wantInterfaceList = True
        else:
            # must be the interface list
            assert self.wantInterfaceList
            assert type(token) == type([]) # TODO: perhaps a dict instead
            self.interfaces = token

    def receiveClose(self):
        if self.refID == None:
            raise BananaError("sequence ended too early")
        return self.broker.registerRemoteReference(self.refID,
                                                   self.interfaces)

class DecRefUnslicer(BaseUnslicer):
    refID = None

    def checkToken(self, typebyte):
        if self.refID == None:
            if typebyte != tokens.INT:
                raise BananaError("reference ID must be an INT")
        else:
            raise BananaError("stop talking already!")

    def receiveChild(self, token):
        if isinstance(token, UnbananaFailure):
            self.abort(token)
            return # TODO: log but otherwise ignore
        self.refID = token

    def receiveClose(self):
        if self.refID == None:
            raise BananaError("sequence ended too early")
        return self.broker.decref(self.refID)


class CallUnslicer(BaseUnslicer):
    stage = 0 # 0:reqID, 1:objID, 2:methodname, 3: [(argname/value)]..
    reqID = None
    obj = None
    methodname = None
    methodSchema = None
    argname = None
    argConstraint = None

    def start(self, count):
        self.args = {}

    def checkToken(self, typebyte):
        if self.stage == 0:
            if typebyte != tokens.INT:
                raise BananaError("request ID must be an INT")
        elif self.stage == 1:
            if typebyte != tokens.INT:
                raise BananaError("object ID must be an INT")
        elif self.stage == 2:
            if typebyte not in (tokens.STRING, tokens.VOCAB):
                raise BananaError("method name must be a STRING")
        elif self.stage == 3:
            if self.argname == None:
                if typebyte not in (tokens.STRING, tokens.VOCAB):
                    raise BananaError("argument name must be a STRING")
            else:
                if self.argConstraint:
                    self.argConstraint.checkToken(typebyte)

    def doOpen(self, opentype):
        # this can only happen when we're receive an argument value, so
        # we don't have to bother checking self.stage or self.argname
        if self.argConstraint:
            self.argConstraint.checkOpentype(opentype)
        unslicer = self.opener(opentype)
        unslicer.opener = self.opener
        if self.argConstraint:
            unslicer.setConstraint(self.argConstraint)
        return unslicer

    def receiveChild(self, token):
        if isinstance(token, UnbananaFailure):
            self.abort(token)
            return # TODO: if possible, return an error to the other side
        if self.stage == 0:
            self.reqID = token
            self.stage += 1
        elif self.stage == 1:
            # this might raise an exception if objID is invalid
            self.obj = self.broker.getObj(token)
            self.stage += 1
        elif self.stage == 2:
            # validate the methodname, get the schema. This may raise an
            # exception for unknown methods
            methodname = token
            self.methodSchema = self.obj.getMethodSchema(methodname)
            self.methodname = methodname
            self.stage += 1
        elif self.stage == 3:
            if self.argname == None:
                ms = self.methodSchema
                if ms:
                    # if the argname is invalid, this may raise Violation
                    self.argConstraint = ms.getArgConstraint(token)
                self.argname = token
            else:
                self.args[self.argname] = token
                self.argname = None

    def receiveClose(self):
        if self.stage != 3 or self.argname != None:
            raise BananaError("sequence ended too early")
        # this is where we actually call the method. doCall will catch any
        # exceptions.
        self.broker.doCall(self.reqID, self.obj, self.methodname,
                           self.args, self.methodSchema)

    def describeSelf(self):
        if self.stage == 0:
            return "<methodcall>"
        elif self.stage == 1:
            return "<methodcall reqID=%d>" % self.reqID
        elif self.stage == 2:
            return "<methodcall reqID=%d obj=%s>" % (self.reqID, self.obj)
        elif self.stage == 3:
            base = "<methodcall reqID=%d obj=%s .%s>" % (self.reqID,
                                                         self.obj,
                                                         self.methodname)
            if self.argname != None:
                return base + "arg[%s]" % self.argname
            return base

class AnswerUnslicer(BaseUnslicer):
    request = None
    resultConstraint = None
    haveResults = False

    def checkToken(self, typebyte):
        if self.request == None:
            if typebyte != tokens.INT:
                raise BananaError("request ID must be an INT")
        elif not self.haveResults:
            if self.resultConstraint:
                try:
                    self.resultConstraint.checkToken(typebyte)
                except Violation:
                    # since we know which request was being sent, we
                    # can errback the deferred
                    self.broker.gotError(self.request, failure.Failure())
                    raise
        else:
            raise BananaError("stop sending me stuff!")

    def doOpen(self, opentype):
        if self.resultConstraint:
            self.resultConstraint.checkOpentype(opentype)
        unslicer = self.opener(opentype)
        unslicer.opener = self.opener
        if self.resultConstraint:
            unslicer.setConstraint(self.resultConstraint)
        return unslicer

    def receiveChild(self, token):
        if isinstance(token, UnbananaFailure):
            if self.request != None:
                self.broker.gotError(self.request, token)
            self.abort(token)
            return
        if self.request == None:
            reqID = token
            # may raise BananaError for bad reqIDs
            self.request = self.broker.getRequest(reqID)
            self.resultConstraint = self.request.constraint
        else:
            self.results = token
            self.haveResults = True

    def receiveClose(self):
        self.broker.gotAnswer(self.request, self.results)

class ErrorUnslicer(BaseUnslicer):
    request = None
    fConstraint = schema.FailureConstraint()
    gotFailure = False

    def checkToken(self, typebyte):
        if self.request == None:
            if typebyte != tokens.INT:
                raise BananaError("request ID must be an INT")
        elif not self.gotFailure:
            self.fConstraint.checkToken(typebyte)
        else:
            raise BananaError("stop sending me stuff!")

    def doOpen(self, opentype):
        self.fConstraint.checkOpentype(opentype)
        unslicer = self.opener(opentype)
        unslicer.opener = self.opener
        unslicer.setConstraint(self.fConstraint)
        return unslicer

    def receiveChild(self, token):
        if isinstance(token, UnbananaFailure):
            # a failure while receiving the failure. A bit daft, really.
            if self.request != None:
                self.broker.gotError(self.request, token)
            self.abort(token)
            return
        if self.request == None:
            reqID = token
            # may raise BananaError for bad reqIDs
            self.request = self.broker.getRequest(reqID)
        else:
            # TODO: need real failures
            #self.failure = token
            self.failure = failure.Failure(RuntimeError(token))
            self.gotFailure = True

    def receiveClose(self):
        self.broker.gotError(self.request, self.failure)


class PBRootUnslicer(slicer.RootUnslicer):
    # topRegistry defines what objects are allowed at the top-level
    topRegistry = {
        "remote": ReferenceUnslicer,
        "decref" : DecRefUnslicer,
        "call": CallUnslicer,
        "answer": AnswerUnslicer,
        "error": ErrorUnslicer,
        }
    # openRegistry defines what objects are allowed at the second level and
    # below
    openRegistry = slicer.UnslicerRegistry

    def checkToken(self, typebyte):
        if typebyte != tokens.OPEN:
            raise BananaError("top-level must be OPEN")

    def doOpen(self, opentype):
        # TODO: refactor this with RootUnslicer.doOpen
        if len(self.protocol.receiveStack) == 1 and opentype == "vocab":
            # only legal at top-level
            child = VocabUnslicer()
        else:
            try:
                child = self.topRegistry[opentype](self.broker)
            except KeyError:
                raise BananaError("unknown OPEN type '%s'" % opentype,
                                  self.where() + ".<OPEN(%s)>" % opentype)
        if not child:
            # TODO: Violation? or should we just drop the connection?
            raise KeyError, "no such open type '%s'" % opentype
        child.opener = self.open
        return child

    def receiveChild(self, obj):
        pass


class BaseSlicer(slicer.BaseSlicer):
    def __init__(self, broker):
        slicer.BaseSlicer.__init__(self)
        self.broker = broker

class AnswerSlicer(BaseSlicer):
    opentype = "answer"

    def slice(self, (reqID, results)):
        self.send(reqID)
        self.send(results)

class ErrorSlicer(AnswerSlicer):
    opentype = "error"

    def slice(self, (reqID, f)):
        self.send(reqID)
        self.send(f)

class ReferenceableSlicer(BaseSlicer):
    """I handle pb.Referenceable objects (things with remotely invokable
    methods, which are copied by reference).
    """
    opentype = "remote"

    def slice(self, obj):
        puid = obj.processUniqueID()
        firstTime = self.broker.luids.has_key(puid)
        luid = self.broker.registerReference(obj)
        self.send(luid)
        if not firstTime:
            # this is the first time the Referenceable has crossed this
            # wire. In addition to the luid, send the interface list to the
            # far end.
            interfaces = components.getInterfaces(obj)
            # TODO: versioned Interfaces!
            ilist = [(name, 0) for name in interfaces]
            self.send(ilist)

class DecRefSlicer(BaseSlicer):
    opentype = "decref"

    def slice(self, refID):
        self.send(refID)

class CopyableSlicer(BaseSlicer):
    """I handle pb.Copyable objects (things which are copied by value)."""

    opentype = "instance"
    # ???

class CallSlicer(BaseSlicer):
    opentype = "call"

    def slice(self, (reqID, refID, methodname, args)):
        self.send(refID)
        self.send(refID)
        self.send(methodname)
        keys = args.keys()
        keys.sort()
        for argname in keys:
            self.send(argname)
            self.send(args[argname])

class PBRootSlicer(slicer.RootSlicer):
    pass


class Broker(banana.Banana):
    slicerClass = PBRootSlicer
    unslicerClass = PBRootUnslicer

    def __init__(self):
        banana.Banana.__init__(self)
        self.rootSlicer.broker = self
        self.rootUnslicer.broker = self
        self.remoteReferences = weakref.WeakValueDictionary()

        self.currentRequestID = 0
        self.waitingForAnswers = {}

        self.currentLocalID = 0
        self.localObjects = {} # things which are available to our peer.
                               # These are reference counted and removed
                               # when the last decref message is received.

    def newLocalID(self):
        """Generate a new LUID.
        """
        self.currentLocalID = self.currentLocalID + 1
        return self.currentLocalID

    def putObj(self, obj):
        # TODO: give duplicates the same objID
        objID = self.newLocalID()
        self.localObjects[objID] = obj
        return objID

    def getObj(self, objID):
        """objID is a number which refers to a object that the remote end is
        allowed to invoke methods upon.
        """
        obj = self.localObjects[objID]
        # obj = tokens.IReferenceable(obj)
        #assert isinstance(obj, pb.Referenceable)
        # obj needs .getMethodSchema, which needs .getArgConstraint
        return obj

    # RemoteReference.callRemote, gotAnswer, and gotError are run on the
    # calling side
    def newRequestID(self):
        self.currentRequestID = self.currentRequestID + 1
        return self.currentRequestID

    def getRequest(self, reqID):
        try:
            req = self.waitingForAnswers[reqID]
            del self.waitingForAnswers[reqID]
            return req
        except KeyError:
            raise BananaError("non-existent reqID '%d'" % reqID)

    def gotAnswer(self, req, results):
        req.deferred.callback(results)
    def gotError(self, req, failure):
        req.deferred.errback(failure)

    # decref is also invoked on the calling side (the pb.Referenceable
    # holder) when the other side sends us a decref message
    def decref(self, refID):
        del self.localObjects[refID]


    # doCall, callFinished, sendError are run on the target side
    def doCall(self, reqID, obj, methodname, args, methodSchema):
        try:
            meth = getattr(obj, "remote_%s" % methodname)
            res = meth(**args)
        except:
            # TODO: implement CopyableFailure and FailureConstraint
            #f = failure.CopyableFailure()
            f = failure.Failure()
            #print "doCall failure", f
            msg = f.getErrorMessage() + f.getBriefTraceback()
            #msg = "ooga booga"
            self.sendError(msg, reqID)
        else:
            if not isinstance(res, defer.Deferred):
                res = defer.succeed(res)
            res.addCallback(self.callFinished, reqID, methodSchema)
            res.addErrback(self.sendError, reqID)

    def callFinished(self, res, reqID, methodSchema):
        if methodSchema:
            methodSchema.checkResults(res) # may raise Violation
        child = AnswerSlicer(self)
        self.slice2(child, (reqID, res))

    def sendError(self, f, reqID):
        child = ErrorSlicer(self)
        self.slice2(child, (reqID, f))

    # registerRemoteReference and freeRemoteReference are also run on the
    # target side (the side that has the RemoteReference)

    def registerRemoteReference(self, refID, interfaces):
        """The far end holds a Referenceable and has just sent us a
        reference to it (expressed as a small integer). If this is a new
        reference, they will give us an interface list too. Obtain a
        RemoteReference object (creating it if necessary) to give to the
        local recipient. There is exactly one RemoteReference object for
        each refID. We hold a weakref to the RemoteReference so we can
        provide the same object later but so we can detect when the Broker
        is the only thing left that knows about it.

        The sender remembers that we hold a reference to their object. When
        our RemoteReference goes away, its __del__ method will tell us to
        send a decref message so they can possibly free their object.
        """

        obj = self.remoteReferences.get(refID)
        if not obj:
            obj = RemoteReference(self, refID, interfaces)
            self.remoteReferences[refID] = obj
        return obj

    def freeRemoteReference(self, refID):
        # this is called by RemoteReference.__del__

        # the WeakValueDictionary means we don't have to explicitly remove it
        #del self.remoteReferences[refID]

        try:
            child = DecRefSlicer(self)
            self.slice2(child, refID)
        except:
            f = failure.Failure()
            f.printTraceback()
            raise
