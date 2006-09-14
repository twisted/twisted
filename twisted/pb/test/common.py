# -*- test-case-name: twisted.pb.test.test_pb -*-

from zope.interface import implements
from twisted.internet import defer, reactor
from twisted.pb import pb, schema, broker
from twisted.pb.negotiate import eventually, flushEventualQueue
from twisted.pb.remoteinterface import getRemoteInterface

from twisted.python import failure
from twisted.internet.main import CONNECTION_DONE, CONNECTION_LOST

def getRemoteInterfaceName(obj):
    i = getRemoteInterface(obj)
    return i.__remote_name__

class Loopback:
    # The transport's promise is that write() can be treated as a
    # synchronous, isolated function call: specifically, the Protocol's
    # dataReceived() and connectionLost() methods shall not be called during
    # a call to write().

    connected = True
    def write(self, data):
        eventually(data).addCallback(self._write)

    def _write(self, data):
        if not self.connected:
            return
        try:
            # isolate exceptions: if one occurred on a regular TCP transport,
            # they would hang up, so duplicate that here.
            self.peer.dataReceived(data)
        except:
            f = failure.Failure()
            log.err(f)
            print "Loopback.write exception:", f
            self.loseConnection(f)

    def loseConnection(self, why=failure.Failure(CONNECTION_DONE)):
        if self.connected:
            self.connected = False
            # this one is slightly weird because 'why' is a Failure
            eventually().addCallback(lambda res: self._loseConnection(why))

    def _loseConnection(self, why):
        self.protocol.connectionLost(why)
        self.peer.connectionLost(why)

    def flush(self):
        self.connected = False
        return eventually()


class RIHelper(pb.RemoteInterface):
    def set(obj=schema.Any()): return bool
    def set2(obj1=schema.Any(), obj2=schema.Any()): return bool
    def append(obj=schema.Any()): return schema.Any()
    def get(): return schema.Any()
    def echo(obj=schema.Any()): return schema.Any()
    def defer(obj=schema.Any()): return schema.Any()
    def hang(): return schema.Any()

class HelperTarget(pb.Referenceable):
    implements(RIHelper)
    d = None
    def __init__(self, name="unnamed"):
        self.name = name
    def __repr__(self):
        return "<HelperTarget %s>" % self.name
    def waitfor(self):
        self.d = defer.Deferred()
        return self.d

    def remote_set(self, obj):
        self.obj = obj
        if self.d:
            self.d.callback(obj)
        return True
    def remote_set2(self, obj1, obj2):
        self.obj1 = obj1
        self.obj2 = obj2
        return True

    def remote_append(self, obj):
        self.calls.append(obj)

    def remote_get(self):
        return self.obj

    def remote_echo(self, obj):
        self.obj = obj
        return obj

    def remote_defer(self, obj):
        d = defer.Deferred()
        reactor.callLater(0, d.callback, obj)
        return d

    def remote_hang(self):
        self.d = defer.Deferred()
        return self.d


class TargetMixin:

    def setUp(self):
        self.loopbacks = []

    def setupBrokers(self):

        self.targetBroker = broker.LoggingBroker()
        self.callingBroker = broker.LoggingBroker()

        t1 = Loopback()
        t1.peer = self.callingBroker
        t1.protocol = self.targetBroker
        self.targetBroker.transport = t1
        self.loopbacks.append(t1)

        t2 = Loopback()
        t2.peer = self.targetBroker
        t2.protocol = self.callingBroker
        self.callingBroker.transport = t2
        self.loopbacks.append(t2)

        self.targetBroker.connectionMade()
        self.callingBroker.connectionMade()

    def tearDown(self):
        # returns a Deferred which fires when the Loopbacks are drained
        dl = [l.flush() for l in self.loopbacks]
        dl.append(flushEventualQueue())
        return defer.DeferredList(dl)

    def setupTarget(self, target, txInterfaces=False):
        # txInterfaces controls what interfaces the sender uses
        #  False: sender doesn't know about any interfaces
        #  True: sender gets the actual interface list from the target
        #  (list): sender uses an artificial interface list
        puid = target.processUniqueID()
        tracker = self.targetBroker.getTrackerForMyReference(puid, target)
        tracker.send()
        clid = tracker.clid
        if txInterfaces:
            iname = getRemoteInterfaceName(target)
        else:
            iname = None
        rtracker = self.callingBroker.getTrackerForYourReference(clid, iname)
        rr = rtracker.getRef()
        return rr, target
