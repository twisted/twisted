

# This module is responsible for the per-connection Broker object

import types
from itertools import count

from zope.interface import implements
from twisted.python import failure, log
from twisted.internet import defer, error, reactor

from twisted.pb import schema, banana, tokens, ipb
from twisted.pb import call, slicer, referenceable, copyable, remoteinterface
from twisted.pb.tokens import Violation, BananaError
from twisted.pb.ipb import DeadReferenceError

try:
    from twisted.pb import crypto
except ImportError:
    crypto = None
if crypto and not crypto.available:
    crypto = None


PBTopRegistry = {
    ("call",): call.CallUnslicer,
    ("answer",): call.AnswerUnslicer,
    ("error",): call.ErrorUnslicer,
    }

PBOpenRegistry = {
    ('my-reference',): referenceable.ReferenceUnslicer,
    ('your-reference',): referenceable.YourReferenceUnslicer,
    ('their-reference',): referenceable.TheirReferenceUnslicer,
    # ('copyable', classname) is handled inline, through the CopyableRegistry
    }

class PBRootUnslicer(slicer.RootUnslicer):
    # topRegistry defines what objects are allowed at the top-level
    topRegistry = [PBTopRegistry]
    # openRegistry defines what objects are allowed at the second level and
    # below
    openRegistry = [slicer.UnslicerRegistry, PBOpenRegistry]
    logViolations = False

    def checkToken(self, typebyte, size):
        if typebyte != tokens.OPEN:
            raise BananaError("top-level must be OPEN")

    def openerCheckToken(self, typebyte, size, opentype):
        if typebyte == tokens.STRING:
            if len(opentype) == 0:
                if size > self.maxIndexLength:
                    why = "first opentype STRING token is too long, %d>%d" % \
                          (size, self.maxIndexLength)
                    raise Violation(why)
            if opentype == ("copyable",):
                # TODO: this is silly, of course (should pre-compute maxlen)
                maxlen = reduce(max,
                                [len(cname) \
                                 for cname in copyable.CopyableRegistry.keys()]
                                )
                if size > maxlen:
                    why = "copyable-classname token is too long, %d>%d" % \
                          (size, maxlen)
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
        # used for lower-level objects, delegated up from childunslicer.open
        assert len(self.protocol.receiveStack) > 1
        if opentype[0] == 'copyable':
            if len(opentype) > 1:
                classname = opentype[1]
                try:
                    factory = copyable.CopyableRegistry[classname]
                except KeyError:
                    raise Violation("unknown RemoteCopy class '%s'" \
                                    % classname)
                child = factory()
                child.broker = self.broker
                return child
            else:
                return None # still need classname
        for reg in self.openRegistry:
            opener = reg.get(opentype)
            if opener is not None:
                child = opener()
                break
        else:
            raise Violation("unknown OPEN type %s" % (opentype,))
        child.broker = self.broker
        return child

    def doOpen(self, opentype):
        child = slicer.RootUnslicer.doOpen(self, opentype)
        if child:
            child.broker = self.broker
        return child

    def reportViolation(self, f):
        if self.logViolations:
            print "hey, something failed:", f
        return None # absorb the failure

    def receiveChild(self, token, ready_deferred=None):
        pass

class PBRootSlicer(slicer.RootSlicer):
    slicerTable = {types.MethodType: referenceable.CallableSlicer,
                   types.FunctionType: referenceable.CallableSlicer,
                   }
    def registerReference(self, refid, obj):
        assert 0

    def slicerForObject(self, obj):
        # zope.interface doesn't do transitive adaptation, which is a shame
        # because we want to let people register ICopyable adapters for
        # third-party code, and there is an ICopyable->ISlicer adapter
        # defined in copyable.py, but z.i won't do the transitive
        #  ThirdPartyClass -> ICopyable -> ISlicer
        # so instead we manually do it here
        s = tokens.ISlicer(obj, None)
        if s:
            return s
        copier = copyable.ICopyable(obj, None)
        if copier:
            s = tokens.ISlicer(copier)
            return s
        return slicer.RootSlicer.slicerForObject(self, obj)


class RIBroker(remoteinterface.RemoteInterface):
    def getReferenceByName(name=str):
        """If I have published an object by that name, return a reference to
        it."""
        # return Remote(interface=any)
        return schema.Any()
    def decref(clid=int, count=int):
        """Release some references to my-reference 'clid'. I will return an
        ack when the operation has completed."""
        return schema.Nothing()
    def decgift(giftID=int, count=int):
        """Release some reference to a their-reference 'giftID' that was
        sent earlier."""
        return schema.Nothing()


class Broker(banana.Banana, referenceable.Referenceable):
    """I manage a connection to a remote Broker.

    @ivar tub: the L{PBService} which contains us
    @ivar yourReferenceByCLID: maps your CLID to a RemoteReferenceData
    #@ivar yourReferenceByName: maps a per-Tub name to a RemoteReferenceData
    @ivar yourReferenceByURL: maps a global URL to a RemoteReferenceData

    """

    implements(RIBroker)
    slicerClass = PBRootSlicer
    unslicerClass = PBRootUnslicer
    unsafeTracebacks = True
    requireSchema = False
    disconnected = False
    factory = None
    tub = None
    remote_broker = None
    startingTLS = False
    startedTLS = False

    def __init__(self, params={}):
        banana.Banana.__init__(self, params)
        self.initBroker()

    def initBroker(self):
        self.rootSlicer.broker = self
        self.rootUnslicer.broker = self

        # tracking Referenceables
        # sending side uses these
        self.nextCLID = count(1).next # 0 is for the broker
        self.myReferenceByPUID = {} # maps ref.processUniqueID to a tracker
        self.myReferenceByCLID = {} # maps CLID to a tracker
        # receiving side uses these
        self.yourReferenceByCLID = {}
        self.yourReferenceByURL = {}

        # tracking Gifts
        self.nextGiftID = count().next
        self.myGifts = {} # maps (broker,clid) to (rref, giftID, count)
        self.myGiftsByGiftID = {} # maps giftID to (broker,clid)

        # remote calls
        # sending side uses these
        self.nextReqID = count().next
        self.waitingForAnswers = {} # we wait for the other side to answer
        self.disconnectWatchers = []
        # receiving side uses these
        self.activeLocalCalls = {} # the other side wants an answer from us

    def setTub(self, tub):
        from twisted.pb import pb
        assert isinstance(tub, pb.PBService)
        self.tub = tub

    def connectionMade(self):
        banana.Banana.connectionMade(self)
        # create the remote_broker object. We don't use the usual
        # reference-counting mechanism here, because this is a synthetic
        # object that lives forever.
        tracker = referenceable.RemoteReferenceTracker(self, 0, None,
                                                       "RIBroker")
        self.remote_broker = referenceable.RemoteReference(tracker)

    def connectionLost(self, why):
        self.disconnected = True
        self.remote_broker = None
        self.abandonAllRequests(why)
        self.myReferenceByPUID = {}
        self.myReferenceByCLID = {}
        self.yourReferenceByCLID = {}
        self.yourReferenceByURL = {}
        self.myGifts = {}
        self.myGiftsByGiftID = {}
        dw, self.disconnectWatchers = self.disconnectWatchers, []
        for d in dw:
            d()
        banana.Banana.connectionLost(self, why)
        if self.tub:
            # TODO: remove the conditional. It is only here to accomodate
            # some tests: test_pb.TestCall.testDisconnect[123]
            self.tub.brokerDetached(self, why)

    def notifyOnDisconnect(self, callback):
        self.disconnectWatchers.append(callback)
    def dontNotifyOnDisconnect(self, callback):
        self.disconnectWatchers.remove(callback)

    # methods to handle RemoteInterfaces
    def getRemoteInterfaceByName(self, name):
        return remoteinterfaces.RemoteInterfaceRegistry[name]

    # methods to send my Referenceables to the other side

    def getTrackerForMyReference(self, puid, obj):
        tracker = self.myReferenceByPUID.get(puid)
        if not tracker:
            # need to add one
            clid = self.nextCLID()
            tracker = referenceable.ReferenceableTracker(self.tub,
                                                         obj, puid, clid)
            self.myReferenceByPUID[puid] = tracker
            self.myReferenceByCLID[clid] = tracker
        return tracker

    def getTrackerForMyCall(self, puid, obj):
        # just like getTrackerForMyReference, but with a negative clid
        tracker = self.myReferenceByPUID.get(puid)
        if not tracker:
            # need to add one
            clid = self.nextCLID()
            clid = -clid
            tracker = referenceable.ReferenceableTracker(self.tub,
                                                         obj, puid, clid)
            self.myReferenceByPUID[puid] = tracker
            self.myReferenceByCLID[clid] = tracker
        return tracker

    # methods to handle inbound 'my-reference' sequences

    def getTrackerForYourReference(self, clid, interfaceName=None, url=None):
        """The far end holds a Referenceable and has just sent us a reference
        to it (expressed as a small integer). If this is a new reference,
        they will give us an interface name too, and possibly a global URL
        for it. Obtain a RemoteReference object (creating it if necessary) to
        give to the local recipient.
        
        The sender remembers that we hold a reference to their object. When
        our RemoteReference goes away, we send a decref message to them, so
        they can possibly free their object. """

        assert type(interfaceName) is str or interfaceName is None
        if url is not None:
            assert type(url) is str
        tracker = self.yourReferenceByCLID.get(clid)
        if not tracker:
            # TODO: translate interfaceNames to RemoteInterfaces
            if clid >= 0:
                trackerclass = referenceable.RemoteReferenceTracker
            else:
                trackerclass = referenceable.RemoteMethodReferenceTracker
            tracker = trackerclass(self, clid, url, interfaceName)
            self.yourReferenceByCLID[clid] = tracker
            if url:
                self.yourReferenceByURL[url] = tracker
        return tracker
        
    def freeYourReference(self, tracker, count):
        # this is called when the RemoteReference is deleted
        if not self.remote_broker: # tests do not set this up
            self.freeYourReferenceTracker(None, tracker)
            return
        try:
            d = self.remote_broker.callRemote("decref",
                                              clid=tracker.clid, count=count)
            # if the connection was lost before we can get an ack, we're
            # tearing this down anyway
            d.addErrback(lambda f: f.trap(DeadReferenceError))
            d.addErrback(lambda f: f.trap(error.ConnectionLost))
            d.addErrback(lambda f: f.trap(error.ConnectionDone))
            # once the ack comes back, or if we know we'll never get one,
            # release the tracker
            d.addCallback(self.freeYourReferenceTracker, tracker)
        except:
            log.msg("failure during freeRemoteReference")
            log.err()

    def freeYourReferenceTracker(self, res, tracker):
        if tracker.received_count != 0:
            return
        if self.yourReferenceByCLID.has_key(tracker.clid):
            del self.yourReferenceByCLID[tracker.clid]
        if tracker.url and self.yourReferenceByURL.has_key(tracker.url):
            del self.yourReferenceByURL[tracker.url]


    # methods to handle inbound 'your-reference' sequences

    def getMyReferenceByCLID(self, clid):
        """clid is the connection-local ID of the Referenceable the other
        end is trying to invoke or point to. If it is a number, they want an
        implicitly-created per-connection object that we sent to them at
        some point in the past. If it is a string, they want an object that
        was registered with our Factory.
        """

        obj = None
        assert type(clid) is int
        if clid == 0:
            return self
        return self.myReferenceByCLID[clid].obj
        # obj = IReferenceable(obj)
        # assert isinstance(obj, pb.Referenceable)
        # obj needs .getMethodSchema, which needs .getArgConstraint

    def remote_decref(self, clid, count):
        # invoked when the other side sends us a decref message
        assert type(clid) is int
        assert clid != 0
        tracker = self.myReferenceByCLID[clid]
        done = tracker.decref(count)
        if done:
            del self.myReferenceByPUID[tracker.puid]
            del self.myReferenceByCLID[clid]

    # methods to send RemoteReference 'gifts' to third-parties

    def makeGift(self, rref):
        # return the giftid
        broker, clid = rref.tracker.broker, rref.tracker.clid
        i = (broker, clid)
        old = self.myGifts.get(i)
        if old:
            rref, giftID, count = old
            self.myGifts[i] = (rref, giftID, count+1)
        else:
            giftID = self.nextGiftID()
            self.myGiftsByGiftID[giftID] = i
            self.myGifts[i] = (rref, giftID, 1)
        return giftID

    def remote_decgift(self, giftID, count):
        broker, clid = self.myGiftsByGiftID[giftID]
        rref, giftID, gift_count = self.myGifts[(broker, clid)]
        gift_count -= count
        if gift_count == 0:
            del self.myGiftsByGiftID[giftID]
            del self.myGifts[(broker, clid)]
        else:
            self.myGifts[(broker, clid)] = (rref, giftID, gift_count)

    # methods to deal with URLs

    def getYourReferenceByName(self, name):
        d = self.remote_broker.callRemote("getReferenceByName", name=name)
        return d

    def remote_getReferenceByName(self, name):
        return self.tub.getReferenceForName(name)

    # remote-method-invocation methods, calling side, invoked by
    # RemoteReference.callRemote and CallSlicer

    def newRequestID(self):
        if self.disconnected:
            raise DeadReferenceError("Calling Stale Broker")
        return self.nextReqID()

    def addRequest(self, req):
        req.broker = self
        self.waitingForAnswers[req.reqID] = req

    def removeRequest(self, req):
        del self.waitingForAnswers[req.reqID]

    def getRequest(self, reqID):
        # invoked by AnswerUnslicer and ErrorUnslicer
        try:
            return self.waitingForAnswers[reqID]
        except KeyError:
            raise Violation("non-existent reqID '%d'" % reqID)

    def abandonAllRequests(self, why):
        for req in self.waitingForAnswers.values():
            req.fail(why)
        self.waitingForAnswers = {}

    # target-side, invoked by CallUnslicer

    def getRemoteInterfaceByName(self, riname):
        # this lives in the broker because it ought to be per-connection
        return remoteinterface.RemoteInterfaceRegistry[riname]

    def getSchemaForMethod(self, rifaces, methodname):
        # this lives in the Broker so it can override the resolution order,
        # not that overlapping RemoteInterfaces should be allowed to happen
        # all that often
        for ri in rifaces:
            m = ri.get(methodname)
            if m:
                return m
        return None

    def doCall(self, reqID, obj, methodname, kwargs, methodSchema):
        if methodname is None:
            assert callable(obj)
            d = defer.maybeDeferred(obj, **kwargs)
        else:
            obj = ipb.IRemotelyCallable(obj)
            d = defer.maybeDeferred(obj.doRemoteCall, methodname, kwargs)
        # interesting case: if the method completes successfully, but
        # our schema prohibits us from sending the result (perhaps the
        # method returned an int but the schema insists upon a string).
        d.addCallback(self._callFinished, reqID, methodSchema)
        # TODO: move the return-value schema check into
        # Referenceable.doRemoteCall, so the exception's traceback will be
        # attached to the object that caused it
        d.addErrback(self.callFailed, reqID)

    def _callFinished(self, res, reqID, methodSchema):
        assert self.activeLocalCalls[reqID]
        if methodSchema:
            methodSchema.checkResults(res) # may raise Violation
        answer = call.AnswerSlicer(reqID, res)
        # once the answer has started transmitting, any exceptions must be
        # logged and dropped, and not turned into an Error to be sent.
        try:
            self.send(answer)
            # TODO: .send should return a Deferred that fires when the last
            # byte has been queued, and we should delete the local note then
        except:
            log.err()
        del self.activeLocalCalls[reqID]

    def callFailed(self, f, reqID):
        # this may be called either when an inbound schema is violated, or
        # when the method is run and raises an exception
        assert self.activeLocalCalls[reqID]
        self.send(call.ErrorSlicer(reqID, f))
        del self.activeLocalCalls[reqID]
        

import debug
class LoggingBroker(debug.LoggingBananaMixin, Broker):
    pass

