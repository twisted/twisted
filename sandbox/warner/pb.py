#! /usr/bin/python

import weakref, types

from twisted.python import components, failure, log
from twisted.internet import defer
registerAdapter = components.registerAdapter

import slicer, schema, tokens, banana
from tokens import BananaError, Violation, ISlicer
from slicer import UnbananaFailure, BaseUnslicer, ReferenceSlicer
ScopedSlicer = slicer.ScopedSlicer
from flavors import getRemoteInterfaces, getRemoteInterfaceNames
from flavors import Copyable, RemoteCopy, registerRemoteCopy
from flavors import Referenceable, IRemoteInterface, RemoteInterfaceRegistry

class PendingRequest(object):
    active = True
    def __init__(self, reqID):
        self.reqID = reqID
        self.deferred = defer.Deferred()
        self.constraint = None # this constrains the results
    def setConstraint(self, constraint):
        self.constraint = constraint
    def complete(self, res):
        if self.active:
            self.active = False
            self.deferred.callback(res)
        else:
            log.msg("PendingRequest.complete called on an inactive request")
    def fail(self, why):
        if self.active:
            self.active = False
            self.deferred.errback(why)
        else:
            log.msg("multiple failures")
            log.err(why)

class RemoteReference(object):
    def __init__(self, broker, refID, interfaceNames):
        self.broker = broker
        self.refID = refID
        self.interfaceNames = interfaceNames

        # attempt to find interfaces which match
        interfaces = {}
        for name in interfaceNames:
            interfaces[name] = RemoteInterfaceRegistry.get(name)

        self.schema = schema.RemoteReferenceSchema(interfaces)

    def __del__(self):
        self.broker.freeRemoteReference(self.refID)

    def getRemoteInterfaceNames(self):
        if not self.schema:
            return []
        return self.schema.interfaceNames

    def getRemoteMethodNames(self):
        if not self.schema:
            return []
        return self.schema.getMethods()

    def callRemote(self, _name, *args, **kwargs):
        # for consistency, *all* failures are reported asynchronously.
        req = None

        _resultConstraint = kwargs.get("_resultConstraint", "none")
        # remember that "none" is not a valid constraint, so we use it to
        # mean "not set by the caller", which means we fall back to whatever
        # the RemoteInterface says

        if _resultConstraint != "none":
            del kwargs["_resultConstraint"]

        try:
            # newRequestID() could fail with a StaleBrokerError
            reqID = self.broker.newRequestID()
        except:
            d = defer.Deferred()
            d.errback(failure.Failure())
            return d

        try:
            # in this clause, we validate the outbound arguments against our
            # notion of what the other end will accept (the RemoteInterface)
            req = PendingRequest(reqID)

            methodSchema = None
            if self.schema:
                # getMethodSchema() could raise KeyError for bad methodnames
                methodSchema = self.schema.getMethodSchema(_name)

            if methodSchema:
                # turn positional arguments into kwargs

                # mapArguments() could fail for bad argument names or
                # missing required parameters
                argsdict = methodSchema.mapArguments(args, kwargs)

                # check args against arg constraint. This could fail if
                # any arguments are of the wrong type
                methodSchema.checkAllArgs(kwargs)

                # the Interface gets to constraint the return value too, so
                # make a note of it to use later
                req.setConstraint(methodSchema.getResponseConstraint())
            else:
                assert not args
                argsdict = kwargs

            # if the caller specified a _resultConstraint, that overrides
            # the schema's one
            if _resultConstraint != "none":
                req.setConstraint(_resultConstraint) # overrides schema

        except: # TODO: merge this with the next try/except clause
            # we have not yet sent anything to the far end. A failure here
            # is entirely local: stale broker, bad method name, bad
            # arguments. We abandon the PendingRequest, but errback the
            # Deferred it was going to use
            req.fail(failure.Failure())
            return req.deferred

        try:
            # once we start sending the CallSlicer, we could get either a
            # local or a remote failure, so we must be prepared to accept an
            # answer. After this point, we assign all responsibility to the
            # PendingRequest structure.
            self.broker.addRequest(req)

            # TODO: there is a decidability problem here: if the reqID made
            # it through, the other end will send us an answer (possibly an
            # error if the remaining slices were aborted). If not, we will
            # not get an answer. To decide whether we should remove our
            # broker.waitingForAnswers[] entry, we need to know how far the
            # slicing process made it.

            slicer = CallSlicer(reqID, self.refID, _name, argsdict)
            
            # this could fail if any of the arguments (or their children)
            # are unsliceable
            d = self.broker.send(slicer)
            # d will fire when the last argument has been serialized. It
            # will errback if the arguments could not be serialized. We need
            # to catch this case and errback the caller.

        except:
            req.fail(failure.Failure())
            return req.deferred

        # if we got here, we have been able to start serializing the
        # arguments. If serialization fails, the PendingRequest needs to be
        # flunked (because we aren't guaranteed that the far end will do it).

        d.addErrback(req.fail)


        # the remote end could send back an error response for many reasons:
        #  bad method name
        #  bad argument types (violated their schema)
        #  exception during method execution
        #  method result violated the results schema
        # something else could occur to cause an errback:
        #  connection lost before response completely received
        #  exception during deserialization of the response
        #   [but only if it occurs after the reqID is received]
        #  method result violated our results schema
        # if none of those occurred, the callback will be run

        return req.deferred

class ReferenceUnslicer(BaseUnslicer):
    refID = None
    interfaces = []
    wantInterfaceList = False
    ilistConstraint = schema.ListOf(schema.TupleOf(str, int))

    def checkToken(self, typebyte, size):
        if self.refID == None:
            if typebyte != tokens.INT:
                raise BananaError("reference ID must be an INT")
        else:
            if self.wantInterfaceList:
                self.ilistConstraint.checkToken(typebyte, size)
            else:
                raise BananaError("interface list on non-initial receipt")

    def doOpen(self, opentype):
        # only for the interface list
        self.ilistConstraint.checkOpentype(opentype)
        unslicer = self.open(opentype)
        if unslicer:
            unslicer.setConstraint(self.ilistConstraint)
        return unslicer

    def receiveChild(self, token):
        self.propagateUnbananaFailures(token)
        # TODO: if possible, return an error to the other side

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

    def checkToken(self, typebyte, size):
        if self.refID == None:
            if typebyte != tokens.INT:
                raise BananaError("reference ID must be an INT")
        else:
            raise BananaError("stop talking already!")

    def receiveChild(self, token):
        self.propagateUnbananaFailures(token)
        # TODO: log but otherwise ignore
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
    methodSchema = None # will be a MethodArgumentsConstraint
    argname = None
    argConstraint = None

    def start(self, count):
        self.args = {}

    def checkToken(self, typebyte, size):
        # TODO: limit strings by returning a number instead of None
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
                    self.argConstraint.checkToken(typebyte, size)

    def doOpen(self, opentype):
        # this can only happen when we're receiving an argument value, so
        # we don't have to bother checking self.stage or self.argname
        if self.argConstraint:
            self.argConstraint.checkOpentype(opentype)
        unslicer = self.open(opentype)
        if unslicer:
            if self.argConstraint:
                unslicer.setConstraint(self.argConstraint)
        return unslicer

    def receiveChild(self, token):
        self.propagateUnbananaFailures(token)
        # TODO: if possible, return an error to the other side
        if self.stage == 0:
            self.reqID = token
            self.stage += 1
            assert not self.broker.activeLocalCalls.get(self.reqID)
            self.broker.activeLocalCalls[self.reqID] = self
        elif self.stage == 1:
            # this might raise an exception if objID is invalid
            self.obj = self.broker.getObj(token)
            self.stage += 1
        elif self.stage == 2:
            # validate the methodname, get the schema. This may raise an
            # exception for unknown methods
            methodname = token
            # must find the schema, using the interfaces
            
            # TODO: getSchema should probably be in an adapter instead of in
            # a pb.Referenceable base class. Old-style (unconstrained)
            # flavors.Referenceable should be adapted to something which
            # always returns None

            # TODO: make this faster. A likely optimization is to take a
            # tuple of components.getInterfaces(obj) and use it as a cache
            # key. It would be even faster to use obj.__class__, but that
            # would probably violate the expectation that instances can
            # define their own __implements__ (independently from their
            # class). If this expectation were to go away, a quick
            # obj.__class__ -> RemoteReferenceSchema cache could be built.

            refschema = self.obj.getSchema()
            self.methodSchema = refschema.getMethodSchema(methodname)

            self.methodname = methodname
            self.stage += 1
        elif self.stage == 3:
            if self.argname == None:
                argname = token
                if self.args.has_key(argname):
                    raise BananaError("duplicate argument '%s'" % argname)
                ms = self.methodSchema
                if ms:
                    # if the argname is invalid, this may raise Violation
                    accept, self.argConstraint = ms.getArgConstraint(argname)
                    assert accept # TODO: discard if not
                self.argname = argname
            else:
                argvalue = token
                self.args[self.argname] = argvalue
                self.argname = None
    def receiveClose(self):
        if self.stage != 3 or self.argname != None:
            raise BananaError("'call' sequence ended too early")
        self.stage = 4
        if self.methodSchema:
            # ask them again so they can look for missing arguments
            self.methodSchema.checkArgs(self.args)
        # this is where we actually call the method. doCall must now take
        # responsibility for the request (specifically for catching any
        # exceptions and doing sendError)
        self.broker.doCall(self.reqID, self.obj, self.methodname,
                           self.args, self.methodSchema)

    def reportViolation(self, f):
        # if the Violation was raised after we know the reqID, we can send
        # back an Error.
        if self.stage > 0:
            self.broker.sendError(f, self.reqID)
        return f

    def describeSelf(self):
        if self.stage == 0:
            return "<methodcall>"
        elif self.stage == 1:
            return "<methodcall reqID=%d>" % self.reqID
        elif self.stage == 2:
            return "<methodcall reqID=%d obj=%s>" % (self.reqID, self.obj)
        elif self.stage == 3:
            base = "<methodcall reqID=%d obj=%s .%s>" % \
                   (self.reqID, self.obj, self.methodname)
            if self.argname != None:
                return base + "arg[%s]" % self.argname
            return base
        elif self.stage == 4:
            base = "<methodcall reqID=%d obj=%s .%s .close>" % \
                   (self.reqID, self.obj, self.methodname)
            return base

class AnswerUnslicer(BaseUnslicer):
    request = None
    resultConstraint = None
    haveResults = False

    def checkToken(self, typebyte, size):
        if self.request == None:
            if typebyte != tokens.INT:
                raise BananaError("request ID must be an INT")
        elif not self.haveResults:
            if self.resultConstraint:
                try:
                    self.resultConstraint.checkToken(typebyte, size)
                except Violation, v:
                    # improve the error message
                    if v.args:
                        # this += gives me a TypeError "object doesn't
                        # support item assignment", which confuses me
                        #v.args[0] += " in inbound method results"
                        why = v.args[0] + " in inbound method results"
                        v.args = why,
                    else:
                        v.args = ("in inbound method results",)
                    raise v # this will errback the request
        else:
            raise BananaError("stop sending me stuff!")

    def doOpen(self, opentype):
        if self.resultConstraint:
            self.resultConstraint.checkOpentype(opentype)
            # TODO: improve the error message
        unslicer = self.open(opentype)
        if unslicer:
            if self.resultConstraint:
                unslicer.setConstraint(self.resultConstraint)
        return unslicer

    def receiveChild(self, token):
        self.propagateUnbananaFailures(token)
        if self.request == None:
            reqID = token
            # may raise BananaError for bad reqIDs
            self.request = self.broker.getRequest(reqID)
            self.resultConstraint = self.request.constraint
        else:
            self.results = token
            self.haveResults = True

    def reportViolation(self, f):
        # if the Violation was received after we got the reqID, we can tell
        # the broker it was an error
        if self.request != None:
            self.broker.gotError(self.request, f)
        return f

    def receiveClose(self):
        self.broker.gotAnswer(self.request, self.results)

class ErrorUnslicer(BaseUnslicer):
    request = None
    fConstraint = schema.FailureConstraint()
    gotFailure = False

    def checkToken(self, typebyte, size):
        if self.request == None:
            if typebyte != tokens.INT:
                raise BananaError("request ID must be an INT")
        elif not self.gotFailure:
            self.fConstraint.checkToken(typebyte, size)
        else:
            raise BananaError("stop sending me stuff!")

    def doOpen(self, opentype):
        self.fConstraint.checkOpentype(opentype)
        unslicer = self.open(opentype)
        if unslicer:
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

PBTopRegistry = {
    ("remote",): ReferenceUnslicer,
    ("decref",): DecRefUnslicer,
    ("call",): CallUnslicer,
    ("answer",): AnswerUnslicer,
    ("error",): ErrorUnslicer,
    }

PBOpenRegistry = slicer.UnslicerRegistry.copy()
PBOpenRegistry.update({
    ('remote',): ReferenceUnslicer,
    # ('copyable', classname) is handled inline, through the CopyableRegistry
    })

class PBRootUnslicer(slicer.RootUnslicer):
    # topRegistry defines what objects are allowed at the top-level
    topRegistry = PBTopRegistry
    # openRegistry defines what objects are allowed at the second level and
    # below
    openRegistry = slicer.UnslicerRegistry
    logViolations = False

    def checkToken(self, typebyte, size):
        if typebyte != tokens.OPEN:
            raise BananaError("top-level must be OPEN")

    def open(self, opentype):
        # used for lower-level objects, delegated up from childunslicer.open
        assert len(self.protocol.receiveStack) > 1
        if opentype[0] == 'copyable':
            if len(opentype) > 1:
                classname = opentype[1]
                try:
                    factory = flavors.CopyableRegistry[classname]
                    child = flavors.RemoteCopyUnslicer(factory)
                    return child
                except KeyError:
                    raise Violation("unknown RemoteCopy class '%s'" \
                                    % classname)
            else:
                return None # still need classname
        try:
            opener = self.openRegistry[opentype]
            child = opener()
        except KeyError:
            raise Violation("unknown OPEN type '%s'" % (opentype,))
        return child

    def doOpen(self, opentype):
        child = slicer.RootUnslicer.doOpen(self, opentype)
        if child:
            child.broker = self.broker
        return child

    def receiveChild(self, obj):
        if self.logViolations and isinstance(obj, UnbananaFailure):
            print "hey, something failed:", obj



class AnswerSlicer(ScopedSlicer):
    opentype = ('answer',)

    def __init__(self, reqID, results):
        ScopedSlicer.__init__(self, None)
        self.reqID = reqID
        self.results = results

    def sliceBody(self, streamable, banana):
        yield self.reqID
        yield self.results

class ErrorSlicer(ScopedSlicer):
    opentype = ('error',)

    def __init__(self, reqID, f):
        ScopedSlicer.__init__(self, None)
        self.reqID = reqID
        self.f = f

    def sliceBody(self, streamable, banana):
        yield self.reqID
        # TODO: need CopyableFailures
        yield self.f.getBriefTraceback()

# failures are treated as Copyables
class FailureSlicer(slicer.BaseSlicer):
    classname = "twisted.python.failure.Failure"

    def slice(self, streamable, banana):
        yield 'copyable'
        yield self.classname
        state = self.getStateToCopy(self.obj, banana)
        for k,v in state.iteritems():
            yield k
            yield v
    def describe(self):
        return "<%s>" % self.classname
        
    def getStateToCopy(self, obj, banana):
        state = obj.__dict__.copy()
        state['tb'] = None
        state['frames'] = []
        state['stack'] = []
        if isinstance(self.value, failure.Failure):
            # TODO: how can this happen? I got rid of failure2Copyable, so
            # if this case is possible, something needs to replace it
            state['value'] = failure2Copyable(self.value,
                                              banana.unsafeTracebacks)
        else:
            state['value'] = str(self.value) # Exception instance
        state['type'] = str(self.type) # Exception class
        if banana.unsafeTracebacks:
            io = StringIO.StringIO()
            self.printTraceback(io)
            state['traceback'] = io.getvalue()
        else:
            state['traceback'] = 'Traceback unavailable\n'
        return state
registerAdapter(FailureSlicer, failure.Failure, ISlicer)

class CopiedFailure(RemoteCopy, failure.Failure):
    def printTraceback(self, file=None):
        if not file: file = log.logfile
        file.write("Traceback from remote host -- ")
        file.write(self.traceback)

    printBriefTraceback = printTraceback
    printDetailedTraceback = printTraceback
registerRemoteCopy(FailureSlicer.classname, CopiedFailure)

class DecRefSlicer(slicer.BaseSlicer):
    opentype = ('decref',)
    def __init__(self, refID):
        self.refID = refID
    def sliceBody(self, streamable, banana):
        yield self.refID

class CallSlicer(ScopedSlicer):
    opentype = ('call',)

    def __init__(self, reqID, refID, methodname, args):
        ScopedSlicer.__init__(self, None)
        self.reqID = reqID
        self.refID = refID
        self.methodname = methodname
        self.args = args

    def sliceBody(self, streamable, banana):
        yield self.reqID
        yield self.refID
        yield self.methodname
        keys = self.args.keys()
        keys.sort()
        for argname in keys:
            yield argname
            yield self.args[argname]

class PBRootSlicer(slicer.RootSlicer):
    def registerReference(self, refid, obj):
        assert 0


class Broker(banana.BaseBanana):
    slicerClass = PBRootSlicer
    unslicerClass = PBRootUnslicer

    def __init__(self):
        banana.BaseBanana.__init__(self)
        self.rootSlicer.broker = self
        self.rootUnslicer.broker = self
        self.remoteReferences = weakref.WeakValueDictionary()

        self.currentRequestID = 0
        self.waitingForAnswers = {}

        self.currentLocalID = 0
        self.localObjects = {} # things which are available to our peer.
                               # These are reference counted and removed
                               # when the last decref message is received.
        self.activeLocalCalls = {}

    def connectionLost(self, why):
        self.abandonAllRequests(why)
        banana.BaseBanana.connectionLost(self, why)

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

    def addRequest(self, req):
        self.waitingForAnswers[req.reqID] = req

    def getRequest(self, reqID):
        try:
            return self.waitingForAnswers[reqID]
        except KeyError:
            raise BananaError("non-existent reqID '%d'" % reqID)

    def gotAnswer(self, req, results):
        del self.waitingForAnswers[req.reqID]
        req.complete(results)
    def gotError(self, req, failure):
        del self.waitingForAnswers[req.reqID]
        req.fail(failure)
    def abandonAllRequests(self, why):
        for req in self.waitingForAnswers.values():
            req.fail(why)
        self.waitingForAnswers = {}

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
            #msg = f.getErrorMessage() + f.getBriefTraceback()
            #msg = "ooga booga"
            self.sendError(f, reqID)
        else:
            if not isinstance(res, defer.Deferred):
                res = defer.succeed(res)
            # interesting case: if the method completes successfully, but
            # our schema prohibits us from sending the result (perhaps the
            # method returned an int but the schema insists upon a string).
            res.addCallback(self.callFinished, reqID, methodSchema)
            res.addErrback(self.sendError, reqID)

    def callFinished(self, res, reqID, methodSchema):
        assert self.activeLocalCalls[reqID]
        if methodSchema:
            methodSchema.checkResults(res) # may raise Violation
        answer = AnswerSlicer(reqID, res)
        # once the answer has started transmitting, any exceptions must be
        # logged and dropped, and not turned into an Error to be sent.
        try:
            self.send(answer)
            # TODO: .send should return a Deferred that fires when the last
            # byte has been queued, and we should delete the local note then
        except:
            log.err()
        del self.activeLocalCalls[reqID]

    def sendError(self, f, reqID):
        assert self.activeLocalCalls[reqID]
        self.send(ErrorSlicer(reqID, f))
        del self.activeLocalCalls[reqID]

    # registerRemoteReference and freeRemoteReference are also run on the
    # target side (the side that has the RemoteReference)

    def registerRemoteReference(self, refID, interfaceNames=[]):
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

        for i in interfaceNames:
            assert type(i) == str
        obj = self.remoteReferences.get(refID)
        if not obj:
            obj = RemoteReference(self, refID, interfaceNames)
            self.remoteReferences[refID] = obj
        return obj

    def freeRemoteReference(self, refID):
        # this is called by RemoteReference.__del__

        # the WeakValueDictionary means we don't have to explicitly remove it
        #del self.remoteReferences[refID]

        try:
            self.send(DecRefSlicer(refID))
        except:
            print "failure during freeRemoteReference"
            f = failure.Failure()
            print f.getTraceback()
            raise
