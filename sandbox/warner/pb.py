#! /usr/bin/python

import weakref, types

from twisted.python import components, failure, log
from twisted.internet import defer

import slicer, schema, tokens, banana
from tokens import BananaError, Violation
from slicer import UnbananaFailure, BaseUnslicer

class Referenceable(object):
    refschema = None
    # TODO: this wants to be in an adapter, not a base class
    def getSchema(self):
        # create and return a RemoteReferenceSchema for us
        if not self.refschema:
            interfaces = dict([
                (iface.__remote_name__ or iface.__name__, iface)
                for iface in getRemoteInterfaces(self)])
            self.refschema = schema.RemoteReferenceSchema(interfaces)
        return self.refschema

class Copyable(object):
    pass

class PendingRequest(object):
    active = True
    def __init__(self):
        self.deferred = defer.Deferred()
        self.constraint = None # this constrains the results
    def setConstraint(self, constraint):
        self.constraint = constraint

class RemoteReference(object):
    def __init__(self, broker, refID, interfaceNames):
        self.broker = broker
        self.refID = refID
        self.interfaceNames = interfaceNames

        # attempt to find interfaces which match
        interfaces = {}
        for name in interfaceNames:
            interfaces[name] = remoteInterfaceRegistry.get(name)

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
        # mean "not set by the caller"
        if _resultConstraint != "none":
            del kwargs["_resultConstraint"]

        try:
            # newRequestID() could fail with a StaleBrokerError
            reqID = self.broker.newRequestID()
            req = PendingRequest()

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

                # the Interface gets to constraint the return value too
                req.setConstraint(methodSchema.getResponseConstraint())
            else:
                assert not args
                argsdict = kwargs

            # if the caller specified a _resultConstraint, that overrides
            # the schema's one
            if _resultConstraint != "none":
                req.setConstraint(_resultConstraint) # overrides schema

            child = CallSlicer(self.broker)

            self.broker.waitingForAnswers[reqID] = req
            # TODO: there is a decidability problem here: if the reqID made
            # it through, the other end will send us an answer (possibly an
            # error if the remaining slices were aborted). If not, we will
            # not get an answer. To decide whether we should remove our
            # broker.waitingForAnswers[] entry, we need to know how far the
            # slicing process made it.

            # this could fail if any of the arguments (or their children)
            # are unsliceable
            self.broker.slice2(child, (reqID, self.refID, _name, argsdict))

        except:
            if req:
                d = req.deferred
            else:
                d = defer.Deferred()
            d.errback(failure.Failure())
            return d

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
            raise BananaError("sequence ended too early")
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


class PBRootUnslicer(slicer.RootUnslicer):
    # topRegistry defines what objects are allowed at the top-level. All of
    # these accept a Broker in their __init__ call
    topRegistry = {
        ("remote",): ReferenceUnslicer,
        ("decref",): DecRefUnslicer,
        ("call",): CallUnslicer,
        ("answer",): AnswerUnslicer,
        ("error",): ErrorUnslicer,
        }
    # openRegistry defines what objects are allowed at the second level and
    # below
    openRegistry = slicer.UnslicerRegistry
    logViolations = False

    def checkToken(self, typebyte, size):
        if typebyte != tokens.OPEN:
            raise BananaError("top-level must be OPEN")

    def openTop(self, opentype):
        child = self.open(opentype, self.topRegistry)
        if child:
            child.broker = self.broker
        return child

    def receiveChild(self, obj):
        if self.logViolations and isinstance(obj, UnbananaFailure):
            print "hey, something failed:", obj



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
        # TODO: need CopyableFailures
        self.send(f.getBriefTraceback())

remoteInterfaceRegistry = {}
def registerRemoteInterface(iface):
    """Call this to register each subclass of IRemoteInterface."""
    name = iface.__remote_name__ or iface.__name__
    remoteInterfaceRegistry[name] = iface

def getRemoteInterfaces(obj):
    """Get a list of all RemoteInterfaces supported by the object."""
    interfaces = components.getInterfaces(obj)
    # TODO: versioned Interfaces!
    ilist = []
    for i in interfaces:
        if issubclass(i, IRemoteInterface):
            if i not in ilist:
                ilist.append(i)
    def getname(i):
        return i.__remote_name__ or i.__name__
    ilist.sort(lambda x,y: cmp(getname(x), getname(y)))
    # TODO: really? both sides must match
    return ilist

def getRemoteInterfaceNames(obj):
    """Get the names of all RemoteInterfaces supported by the object."""
    return [i.__remote_name__ or i.__name__ for i in getRemoteInterfaces(obj)]

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
            self.send(getRemoteInterfaceNames(obj))
            # TODO: maybe create the RemoteReferenceSchema now
            # obj.getSchema()

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

PBSlicerRegistry = {}
PBSlicerRegistry.update(slicer.BaseSlicerRegistry)
del PBSlicerRegistry[types.InstanceType]

class PBRootSlicer(slicer.RootSlicer):
    SlicerRegistry = PBSlicerRegistry

    def slicerFactoryForObject(self, obj):
        if isinstance(obj, Referenceable):
            return ReferenceableSlicer
        if isinstance(obj, Copyable):
            return CopyableSlicer
        return slicer.RootSlicer.slicerFactoryForObject(self, obj)


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
        self.activeLocalCalls = {}

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
        assert req.active
        req.active = False
        req.deferred.callback(results)
    def gotError(self, req, failure):
        assert req.active
        req.active = False
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
        child = AnswerSlicer(self)
        # once the answer has started transmitting, any exceptions must be
        # logged and dropped, and not turned into an Error to be sent.
        try:
            self.slice2(child, (reqID, res))
        except:
            log.err()
        del self.activeLocalCalls[reqID]

    def sendError(self, f, reqID):
        assert self.activeLocalCalls[reqID]
        child = ErrorSlicer(self)
        self.slice2(child, (reqID, f))
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
            child = DecRefSlicer(self)
            self.slice2(child, refID)
        except:
            print "failure during freeRemoteReference"
            f = failure.Failure()
            print f.getTraceback()
            raise

class RemoteMetaInterface(components.MetaInterface):
    def __init__(self, iname, bases, dct):
        components.MetaInterface.__init__(self, iname, bases, dct)
        # determine all remotely-callable methods
        methods = [name for name in dct.keys()
                   if ((type(dct[name]) == types.FunctionType and
                        not name.startswith("_")) or
                       components.implements(dct[name], schema.IConstraint))]
        self.methods = methods
        # turn them into constraints
        for name in methods:
            m = dct[name]
            if not components.implements(m, schema.IConstraint):
                s = schema.RemoteMethodSchema(method=m)
                #dct[name] = s  # this doesn't work, dct is copied
                setattr(self, name, s)

class IRemoteInterface(components.Interface, object):
    __remote_name__ = None
    __metaclass__ = RemoteMetaInterface

