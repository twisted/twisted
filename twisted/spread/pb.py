
# Twisted, the Framework of Your Internet
# Copyright (C) 2001 Matthew W. Lefkowitz
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of version 2.1 of the GNU Lesser General Public
# License as published by the Free Software Foundation.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

"""
Perspective Broker

    \"This isn\'t a professional opinion, but it's probably got enough
    internet to kill you.\" --glyph

 Introduction

  This is a broker for proxies for and copies of objects.  It provides a
  translucent interface layer to those proxies.

  The protocol is not opaque, because it provides objects which
  represent the remote proxies and require no context (server
  references, IDs) to operate on.

  It is not transparent because it does *not* attempt to make remote
  objects behave identically, or even similiarly, to local objects.
  Method calls are invoked asynchronously, and specific rules are
  applied when serializing arguments.

"""

# System Imports
import traceback
import cStringIO
import copy
import string
import sys
import types

# Twisted Imports
from twisted.python import log, defer, failure
from twisted.protocols import protocol
from twisted.internet import tcp
from twisted.cred import authorizer, service, perspective, identity
from twisted.persisted import styles

# Sibling Imports
from jelly import jelly, unjelly, globalSecurity
import banana

# Tightly coupled sibling import
from flavors import Serializable
from flavors import Referenceable
from flavors import Root
from flavors import ViewPoint
from flavors import Viewable
from flavors import Copyable
from flavors import Cacheable
from flavors import RemoteCopy
from flavors import RemoteCache
from flavors import RemoteCacheObserver
from flavors import copyTags
from flavors import setCopierForClass, setUnjellyableForClass
from flavors import setCopierForClassTree

MAX_BROKER_REFS = 1024

portno = 8787


class ProtocolError(Exception):
    """
    This error is raised when an invalid protocol statement is received.
    """

class Error(Exception):
    """
    This error can be raised to generate known error conditions.

    When a PB callable method (perspective_, remote_, view_) raises
    this error, it indicates that a traceback should not be printed,
    but instead, the string representation of the exception should be
    sent.
    """

def print_excFullStack(file=None):
    """Print exception traceback with the full stack.

    This is in contrast to traceback.print_exc which only prints
    the traceback between the frame where the error occoured and
    the frame where the exception was caught, but not the frames
    leading up to that one.

    The need for this function arises from the fact that several PB
    classes have the peculiar habit of discarding exceptions with
    bareword \"except:\"s.  This premature exception catching means
    tracebacks generated here don't tend to show what called upon
    the PB object.
    """
    (eType, eVal, tb) = sys.exc_info()
    s = (["Traceback (most recent call last):\n"]
         + traceback.format_stack(tb.tb_frame.f_back)
         + ["--- <exception caught here> ---\n"]
         + traceback.format_tb(tb)
         + traceback.format_exception_only(eType, eVal))
    del tb

    if not file:
        file = sys.stderr
    file.write(string.join(s,''))


class RemoteMethod:
    """This is a translucent reference to a remote message.
    """
    def __init__(self, obj, name):
        """Initialize with a RemoteReference and the name of this message.
        """
        self.obj = obj
        self.name = name

    def __cmp__(self, other):
        return cmp((self.obj, self.name), other)

    def __hash__(self):
        return hash((self.obj, self.name))

    def __call__(self, *args, **kw):
        """Asynchronously invoke a remote method.
        """
        return self.obj.broker._sendMessage('',self.obj.perspective, self.obj.luid,  self.name, args, kw)

def noOperation(*args, **kw):
    """Do nothing.

    Neque porro quisquam est qui dolorem ipsum quia dolor sit amet,
    consectetur, adipisci velit...
    """

PB_CONNECTION_LOST = 'Connection Lost'

def printTraceback(tb):
    """Print a traceback (string) to the standard log.
    """

    log.msg('Perspective Broker Traceback:' )
    log.msg(tb)

class Perspective(perspective.Perspective):
    """A perspective on a service.

    per*spec*tive, n. : The relationship of aspects of a subject to each
    other and to a whole: 'a perspective of history'; 'a need to view
    the problem in the proper perspective'.

    A service represents a collection of state, plus a collection of
    perspectives.  Perspectives are the way that networked clients have
    a 'view' onto an object, or collection of objects on the server.

    Although you may have a service onto which there is only one
    perspective, the common case is that a Perspective will be
    analagous to (or the same as) a "user"; if you are creating a
    PB-enabled service, your User (or equivalent) class should subclass
    Perspective.

    Initially, a peer requesting a perspective will receive only a
    RemoteReference to a Perspective.  When a method is called on
    that RemoteReference, it will translate to a method on the remote
    perspective named 'perspective_methodname'.  (For more information
    on invoking methods on other objects, see ViewPoint.)
    """

    def brokerAttached(self, reference, identity, broker):
        """An intermediary method to override.

        Normally you will want to use 'attached', as described in
        twisted.cred.perspective.Perspective.attached; however, this method
        serves the same purpose, and in some circumstances, you are sure that
        the protocol that objects will be attaching to your Perspective with is
        Perspective Broker, and in that case you may wish to get the Broker
        object they are connecting with, for example, to determine what host
        they are connecting from.  Bear in mind that when overriding this
        method, other, non-PB protocols will not notify you of being attached
        or detached.
        """
        return self.attached(reference, identity)

    def brokerDetached(self, reference, identity, broker):
        """See brokerAttached.
        """
        return self.detached(reference, identity)

    def perspectiveMessageReceived(self, broker, message, args, kw):
        """This method is called when a network message is received.

        I will call::

            self.perspective_%(message)s(*broker.unserialize(args),
                                         **broker.unserialize(kw))

        to handle the method; subclasses of Perspective are expected to
        implement methods of this naming convention.
        """

        args = broker.unserialize(args, self)
        kw = broker.unserialize(kw, self)
        method = getattr(self, "perspective_%s" % message)
        try:
            state = apply(method, args, kw)
        except TypeError:
            log.msg("%s didn't accept %s and %s" % (method, args, kw))
            raise
        return broker.serialize(state, self, method, args, kw)


class Service(service.Service):
    """A service for Perspective Broker.

    On this Service, the result of a perspective request must be a
    pb.Perspective rather than a perspective.Perspective.
    """
    perspectiveClass = Perspective


class AsReferenceable(Referenceable):
    """AsReferenceable: a reference directed towards another object.
    """

    def __init__(self, object, messageType="remote"):
        """Initialize me with an object.
        """
        self.remoteMessageReceived = getattr(object, messageType + "MessageReceived")


class RemoteReference(Serializable, styles.Ephemeral):
    """This is a translucent reference to a remote object.

    I may be a reference to a ViewPoint, a Referenceable, or
    a Perspective.  From the client's perspective, it is not
    possible to tell which except by convention.

    I am a "translucent" reference because although no additional
    bookkeeping overhead is given to the application programmer for
    manipulating a reference, return values are asynchronous.

    See also twisted.python.defer.
    """

    def __init__(self, perspective, broker, luid, doRefCount):
        """(internal) Initialize me with a broker and a locally-unique ID.

        The ID is unique only to the particular Perspective Broker
        instance.
        """
        self.luid = luid
        self.broker = broker
        self.doRefCount = doRefCount
        self.perspective = perspective
        self.disconnectCallbacks = []

    def notifyOnDisconnect(self, callback):
        """Register a callback to be called if our broker gets disconnected.

        This callback will be called with one method, this instance.
        """
        assert callable(callback)
        self.disconnectCallbacks.append(callback)
        if len(self.disconnectCallbacks):
            self.broker.notifyOnDisconnect(self._disconnected)

    def dontNotifyOnDisconnect(self, callback):
        """Register a callback to be called if our broker gets disconnected."""
        self.disconnectCallbacks.remove(callback)
        if not self.disconnectCallbacks:
            self.broker.dontNotifyOnDisconnect(self._disconnected)

    def _disconnected(self):
        """Called if we are disconnected and have callbacks registered."""
        for callback in self.disconnectCallbacks:
            callback(self)
        self.disconnectCallbacks = None

    def jellyFor(self, jellier):
        """If I am being sent back to where I came from, serialize as a local backreference.
        """
        if jellier.invoker:
            assert self.broker == jellier.invoker, "Can't send references to brokers other than their own."
            return "local", self.luid
        else:
            return "unpersistable", "References cannot be serialized"

    def unjellyFor(self, unjellier, unjellyList):
        self.__init__(unjellier.invoker.unserializingPerspective, unjellier.invoker, unjellyList[1], 1)
        return self

    def callRemote(self, name, *args, **kw):
        """Asynchronously invoke a remote method.

        Arguments:

          * name: the name of the remote method to invoke

          * *args: arguments to serialize for the remote function

          * **kw: keyword arguments to serialize for the remote function.

        Returns:

          a Deferred which will be fired when the result of this remote call is
          received.
        """
        return self.broker._sendMessage('',self.perspective, self.luid, name, args, kw)

    def remoteMethod(self, key):
        """Get a RemoteMethod for this key.
        """
        return RemoteMethod(self, key)

    def __cmp__(self,other):
        """Compare me [to another RemoteReference].
        """
        if isinstance(other, RemoteReference):
            if other.broker == self.broker:
                return cmp(self.luid, other.luid)
        return cmp(self.broker, other)

    def __hash__(self):
        """Hash me.
        """
        return self.luid

    def __del__(self):
        """Do distributed reference counting on finalization.
        """
        if self.doRefCount:
            self.broker.sendDecRef(self.luid)

setUnjellyableForClass("remote", RemoteReference)

class Local:
    """(internal) A reference to a local object.
    """

    def __init__(self, object, perspective=None):
        """Initialize.
        """
        self.object = object
        self.perspective = perspective
        self.refcount = 1

    def __repr__(self):
        return "<pb.Local %r ref:%s>" % (self.object, self.refcount)

    def incref(self):
        """Increment and return my reference count.
        """
        self.refcount = self.refcount + 1
        return self.refcount

    def decref(self):
        """Decrement and return my reference count.
        """
        self.refcount = self.refcount - 1
        return self.refcount


class _RemoteCacheDummy:
    """Ignore.
    """


class Broker(banana.Banana):
    """I am a broker for objects.
    """

    version = 6
    username = None

    def __init__(self, isClient=1, security=globalSecurity):
        banana.Banana.__init__(self, isClient)
        self.disconnected = 0
        self.disconnects = []
        self.failures = []
        self.connects = []
        self.localObjects = {}
        self.security = security

    def expressionReceived(self, sexp):
        """Evaluate an expression as it's received.
        """
        if isinstance(sexp, types.ListType):
            command = sexp[0]
            methodName = "proto_%s" % command
            method = getattr(self, methodName, None)
            if method:
                apply(method, sexp[1:])
            else:
                self.sendCall("didNotUnderstand", command)
        else:
            raise ProtocolError("Non-list expression received.")


    def proto_version(self, vnum):
        """Protocol message: (version version-number)

        Check to make sure that both ends of the protocol are speaking
        the same version dialect.
        """

        if vnum != self.version:
            raise ProtocolError("Version Incompatibility: %s %s" % (self.version, vnum))


    def sendCall(self, *exp):
        """Utility method to send an expression to the other side of the connection.
        """
        self.sendEncoded(exp)

    def proto_didNotUnderstand(self, command):
        """Respond to stock 'didNotUnderstand' message.

        Log the command that was not understood and continue. (Note:
        this will probably be changed to close the connection or raise
        an exception in the future.)
        """
        log.msg("Didn't understand command: %r" % command)

    def connectionReady(self):
        """Initialize.
        """

        # Some terms:
        #  PUID: process unique ID; return value of id() function.  type "int".
        #  LUID: locally unique ID; an ID unique to an object mapped over this
        #        connection. type "int"
        #  GUID: (not used yet) globally unique ID; an ID for an object which
        #        may be on a redirected or meta server.  Type as yet undecided.
        self.sendCall("version", self.version)
        self.currentRequestID = 0
        self.currentLocalID = 0
        # Dictionary mapping LUIDs to local objects.
        # set above to allow root object to be assigned before connection is made
        # self.localObjects = {}
        # Dictionary mapping PUIDs to LUIDs.
        self.luids = {}
        # Dictionary mapping LUIDs to local (remotely cached) objects. Remotely
        # cached means that they're objects which originate here, and were
        # copied remotely.
        self.remotelyCachedObjects = {}
        # Dictionary mapping PUIDs to (cached) LUIDs
        self.remotelyCachedLUIDs = {}
        # Dictionary mapping (remote) LUIDs to (locally cached) objects.
        self.locallyCachedObjects = {}
        self.waitingForAnswers = {}
        for notifier in self.connects:
            try:
                notifier()
            except:
                log.deferr()

    def connectionFailed(self):
        for notifier in self.failures:
            try:
                notifier()
            except:
                log.deferr()
    waitingForAnswers = None
    def connectionLost(self):
        """The connection was lost.
        """

        self.disconnected = 1
        # nuke potential circular references.
        self.luids = None
        if self.waitingForAnswers:
            for d in self.waitingForAnswers.values():
                try:
                    d.errback(PB_CONNECTION_LOST)
                except:
                    print_excFullStack(file=log.logfile)
        for notifier in self.disconnects:
            try:
                notifier()
            except:
                print_excFullStack(file=log.logfile)
        self.disconnects = None
        self.waitingForAnswers = None
        self.localSecurity = None
        self.remoteSecurity = None
        self.remotelyCachedObjects = None
        self.remotelyCachedLUIDs = None
        self.locallyCachedObjects = None

    def notifyOnDisconnect(self, notifier):
        """Call the given callback when the Broker disconnects."""
        assert callable(notifier)
        self.disconnects.append(notifier)

    def notifyOnFail(self, notifier):
        """Call the given callback if the Broker fails to connect."""
        assert callable(notifier)
        self.failures.append(notifier)

    def notifyOnConnect(self, notifier):
        """Call the given callback when the Broker connects."""
        assert callable(notifier)
        self.connects.append(notifier)

    def dontNotifyOnDisconnect(self, notifier):
        """Remove a callback from list of disconnect callbacks."""
        try:
            self.disconnects.remove(notifier)
        except ValueError:
            pass

    def localObjectForID(self, luid):
        """Get a local object for a locally unique ID.

        I will return an object previously stored with
        self.registerReference, or None if XXX:Unfinished thought:XXX
        """

        lob = self.localObjects.get(luid)
        if lob is None:
            return
        return lob.object

    maxBrokerRefsViolations = 0

    def registerReference(self, object):
        """Get an ID for a local object.

        Store a persistent reference to a local object and map its id()
        to a generated, session-unique ID and return that ID.
        """

        assert object is not None
        puid = object.processUniqueID()
        luid = self.luids.get(puid)
        if luid is None:
            # print len(self.localObjects)
            if len(self.localObjects) > MAX_BROKER_REFS:
                # print 'EXCEEDED'
                self.maxBrokerRefsViolations = self.maxBrokerRefsViolations + 1
                if self.maxBrokerRefsViolations > 3:
                    self.transport.loseConnection()
                    raise Error("Maximum PB reference count exceeded.  "
                                "Goodbye.")
                raise Error("Maximum PB reference count exceeded.")

            luid = self.newLocalID()
            self.localObjects[luid] = Local(object)
            self.luids[puid] = luid
        else:
            self.localObjects[luid].incref()
        return luid

    def setNameForLocal(self, name, object):
        """Store a special (string) ID for this object.

        This is how you specify a 'base' set of objects that the remote
        protocol can connect to.
        """
        assert object is not None
        self.localObjects[name] = Local(object)

    def remoteForName(self, name):
        """Returns an object from the remote name mapping.

        Note that this does not check the validity of the name, only
        creates a translucent reference for it.
        """
        return RemoteReference(None, self, name, 0)

    def cachedRemotelyAs(self, instance, incref=0):
        """Returns an ID that says what this instance is cached as remotely, or None if it's not.
        """

        puid = instance.processUniqueID()
        luid = self.remotelyCachedLUIDs.get(puid)
        if (luid is not None) and (incref):
            # print 'caching remotely ', luid, instance
            self.remotelyCachedObjects[luid].incref()
        return luid

    def remotelyCachedForLUID(self, luid):
        """Returns an instance which is cached remotely, with this LUID.
        """
        return self.remotelyCachedObjects[luid].object

    def cacheRemotely(self, instance):
        """
        XXX"""
        puid = instance.processUniqueID()
        luid = self.newLocalID()
        if len(self.remotelyCachedObjects) > MAX_BROKER_REFS:
            # print 'EXCEEDED'
            self.maxBrokerRefsViolations = self.maxBrokerRefsViolations + 1
            if self.maxBrokerRefsViolations > 3:
                self.transport.loseConnection()
                raise Error("Maximum PB cache count exceeded.  "
                            "Goodbye.")
            raise Error("Maximum PB cache count exceeded.")

        self.remotelyCachedLUIDs[puid] = luid
        # This table may not be necessary -- for now, it's to make sure that no
        # monkey business happens with id(instance)
        self.remotelyCachedObjects[luid] = Local(instance, self.serializingPerspective)
        # print "caching remotely for the first time", luid
        return luid

    def cacheLocally(self, cid, instance):
        """(internal)

        Store a non-filled-out cached instance locally.
        """
        self.locallyCachedObjects[cid] = instance

    def cachedLocallyAs(self, cid):
        instance = self.locallyCachedObjects[cid]
        return instance

    def serialize(self, object, perspective=None, method=None, args=None, kw=None):
        """Jelly an object according to the remote security rules for this broker.
        """

        if isinstance(object, defer.Deferred):
            object.addCallbacks(self.serialize, lambda x: x,
                                callbackKeywords={
                'perspective': perspective,
                'method': method,
                'args': args,
                'kw': kw
                })
            return object

        # XXX This call is NOT REENTRANT and testing for reentrancy is just
        # crazy, so it likely won't be.  Don't ever write methods that call the
        # broker's serialize() method recursively (e.g. sending a method call
        # from within a getState (this causes concurrency problems anyway so
        # you really, really shouldn't do it))

        # self.jellier = _NetJellier(self)
        self.serializingPerspective = perspective
        self.jellyMethod = method
        self.jellyArgs = args
        self.jellyKw = kw
        try:
            return jelly(object, self.security, None, self)
        finally:
            self.serializingPerspective = None
            self.jellyMethod = None
            self.jellyArgs = None
            self.jellyKw = None

    def unserialize(self, sexp, perspective = None):
        """Unjelly an sexp according to the local security rules for this broker.
        """

        self.unserializingPerspective = perspective
        try:
            return unjelly(sexp, self.security, None, self)
        finally:
            self.unserializingPerspective = None

    def newLocalID(self):
        """Generate a new LUID.
        """
        self.currentLocalID = self.currentLocalID + 1
        return self.currentLocalID

    def newRequestID(self):
        """Generate a new request ID.
        """
        self.currentRequestID = self.currentRequestID + 1
        return self.currentRequestID

    def _sendMessage(self, prefix, perspective, objectID, message, args, kw):
        pbc = None
        pbe = None
        answerRequired = 1
        if kw.has_key('pbcallback'):
            pbc = kw['pbcallback']
            del kw['pbcallback']
        if kw.has_key('pberrback'):
            pbe = kw['pberrback']
            del kw['pberrback']
        if kw.has_key('pbanswer'):
            assert (not pbe) and (not pbc), "You can't specify a no-answer requirement."
            answerRequired = kw['pbanswer']
            del kw['pbanswer']
        if self.disconnected:
            raise ProtocolError("Calling Stale Broker")
        try:
            netArgs = self.serialize(args, perspective=perspective, method=message)
            netKw = self.serialize(kw, perspective=perspective, method=message)
        except:
            return defer.fail(failure.Failure())
        requestID = self.newRequestID()
        if answerRequired:
            rval = defer.Deferred()
            self.waitingForAnswers[requestID] = rval
            if pbc or pbe:
                log.msg('warning! using deprecated "pbcallback"')
                rval.addCallbacks(pbc, pbe)
        else:
            rval = None
        self.sendCall(prefix+"message", requestID, objectID, message, answerRequired, netArgs, netKw)
        return rval

    def proto_message(self, requestID, objectID, message, answerRequired, netArgs, netKw):
        self._recvMessage(self.localObjectForID, requestID, objectID, message, answerRequired, netArgs, netKw)
    def proto_cachemessage(self, requestID, objectID, message, answerRequired, netArgs, netKw):
        self._recvMessage(self.cachedLocallyAs, requestID, objectID, message, answerRequired, netArgs, netKw)

    def _recvMessage(self, findObjMethod, requestID, objectID, message, answerRequired, netArgs, netKw):
        """Received a message-send.

        Look up message based on object, unserialize the arguments, and
        invoke it with args, and send an 'answer' or 'error' response.
        """
        try:
            object = findObjMethod(objectID)
            if object is None:
                raise Error("Invalid Object ID")
            netResult = object.remoteMessageReceived(self, message, netArgs, netKw)
        except Error, e:
            if answerRequired:
                self._sendError(str(e), requestID)
        except:
            if answerRequired:
                io = cStringIO.StringIO()
                failure.Failure().printBriefTraceback(file=io)
                self._sendError(io.getvalue(), requestID)
                log.msg("Peer Will Receive PB Traceback:")
            else:
                log.msg("Peer Will Ignore PB Traceback:")
            log.deferr()
        else:
            if answerRequired:
                if isinstance(netResult, defer.Deferred):
                    args = (requestID,)
                    netResult.addCallbacks(self._sendAnswer, self._sendFormattedFailure,
                                           callbackArgs=args, errbackArgs=args)
                    # XXX Should this be done somewhere else?
                    netResult.arm()
                else:
                    self._sendAnswer(netResult, requestID)


    def _sendAnswer(self, netResult, requestID):
        """(internal) Send an answer to a previously sent message.
        """
        self.sendCall("answer", requestID, netResult)

    def _sendFormattedFailure(self, error, requestID):
        self._sendError(repr(error), requestID)

    def proto_answer(self, requestID, netResult):
        """(internal) Got an answer to a previously sent message.

        Look up the appropriate callback and call it.
        """
        d = self.waitingForAnswers[requestID]
        del self.waitingForAnswers[requestID]
        d.armAndCallback(self.unserialize(netResult))

    def _sendError(self, descriptiveString, requestID):
        """(internal) Send an error for a previously sent message.
        """
        self.sendCall("error", requestID, descriptiveString)

    def proto_error(self, requestID, descriptiveString):
        """(internal) Deal with an error.
        """
        d = self.waitingForAnswers[requestID]
        del self.waitingForAnswers[requestID]
        d.armAndErrback(descriptiveString)

    def sendDecRef(self, objectID):
        """(internal) Send a DECREF directive.
        """
        self.sendCall("decref", objectID)

    def decCacheRef(self, objectID):
        """(internal) Send a DECACHE directive.
        """
        self.sendCall("decache", objectID)

    def proto_decref(self, objectID):
        """(internal) Decrement the refernce count of an object.

        If the reference count is zero, it will free the reference to this
        object.
        """
        refs = self.localObjects[objectID].decref()
        # print "decref for %d #refs: %d" % (objectID, refs)
        if refs == 0:
            puid = self.localObjects[objectID].object.processUniqueID()
            del self.luids[puid]
            del self.localObjects[objectID]

    def proto_decache(self, objectID):
        """(internal) Decrement the reference count of a cached object.

        If the reference count is zero, free the reference, then send an
        'uncached' directive.
        """
        refs = self.remotelyCachedObjects[objectID].decref()
        # log.msg('decaching: %s #refs: %s' % (objectID, refs))
        if refs == 0:
            lobj = self.remotelyCachedObjects[objectID]
            cacheable = lobj.object
            perspective = lobj.perspective
            # TODO: force_decache needs to be able to force-invalidate a
            # cacheable reference.
            try:
                cacheable.stoppedObserving(perspective, RemoteCacheObserver(self, cacheable, perspective))
            except:
                log.deferr()
            puid = cacheable.processUniqueID()
            del self.remotelyCachedLUIDs[puid]
            del self.remotelyCachedObjects[objectID]
            self.sendCall("uncache", objectID)

    def proto_uncache(self, objectID):
        """(internal) Tell the client it is now OK to uncache an object.
        """
        # log.msg("uncaching locally %d" % objectID)
        obj = self.locallyCachedObjects[objectID]
        def reallyDel(obj=obj):
            obj.__really_del__()
        obj.__del__ = reallyDel
        del self.locallyCachedObjects[objectID]


class BrokerFactory(protocol.Factory, styles.Versioned):
    """I am a server for object brokerage.
    """
    persistenceVersion = 3
    def __init__(self, objectToBroker):
        self.objectToBroker = objectToBroker

    configTypes = {'objectToBroker': Root}
    configName = 'PB Broker Factory'

    def configInit(self, container, name):
        self.__init__(AuthRoot(container.app))

    def config_objectToBroker(self, newObject):
        self.objectToBroker = newObject

    def getConfiguration(self):
        return {"objectToBroker": self.objectToBroker}

    def upgradeToVersion2(self):
        app = self.app
        del self.app
        self.__init__(AuthRoot(app))

    def buildProtocol(self, addr):
        """Return a Broker attached to me (as the service provider).
        """
        proto = Broker(0)
        proto.factory = self
        proto.setNameForLocal("root",
                              self.objectToBroker.rootObject(proto))
        return proto


### AUTH STUFF

class AuthRoot(Root):
    """I provide AuthServs as root objects to Brokers for a BrokerFactory.
    """

    def __init__(self, app):
        self.app = app

    def rootObject(self, broker):
        return AuthServ(self.app, broker)

class _Detacher:
    def __init__(self, perspective, remoteRef, identity, broker):
        self.perspective = perspective
        self.remoteRef = remoteRef
        self.identity = identity
        self.broker = broker

    def detach(self):
        self.perspective.brokerDetached(self.remoteRef,
                                        self.identity,
                                        self.broker)

class IdentityWrapper(Referenceable):
    """I delegate most functionality to a identity.Identity.
    """

    def __init__(self, broker, identity):
        """Initialize, specifying an identity to wrap.
        """
        self.identity = identity
        self.broker = broker

    def remote_attach(self, serviceName, perspectiveName, remoteRef):
        """Attach the remote reference to a requested perspective.
        """
        return self.identity.requestPerspectiveForKey(
            serviceName, perspectiveName).addCallbacks(
            self._attached, lambda x: x,
            callbackArgs = [remoteRef])

    def _attached(self, perspective, remoteRef):
        perspective = perspective.brokerAttached(remoteRef,
                                                 self.identity,
                                                 self.broker)
        # Make sure that when connectionLost happens, this perspective
        # will be tracked in order that 'detached' will be called.
        self.broker.notifyOnDisconnect(_Detacher(perspective,
                                                 remoteRef,
                                                 self.identity,
                                                 self.broker).detach)
        return AsReferenceable(perspective, "perspective")

    # (Possibly?) TODO: Implement 'remote_detach' as well.


class AuthChallenger(Referenceable):
    """XXX

    See also: AuthServ
    """

    def __init__(self, ident, serv, challenge):
        self.ident = ident
        self.challenge = challenge
        self.serv = serv

    def remote_respond(self, response):
        if self.ident:
            d = defer.Deferred()
            pwrq = self.ident.verifyPassword(self.challenge, response)
            pwrq.addCallback(self._authOk, d)
            pwrq.addErrback(self._authFail, d)
            pwrq.arm()
            return d

    def _authOk(self, result, d):
        d.callback(IdentityWrapper(self.serv.broker, self.ident))

    def _authFail(self, result, d):
        d.callback(None)

class AuthServ(Referenceable):
    """XXX

    See also: AuthRoot
    """

    def __init__(self, app, broker):
        self.app = app
        self.broker = broker

    def remote_username(self, username):
        defr = self.app.authorizer.getIdentityRequest(username)
        defr.addCallback(self.mkchallenge)
        return defr

    def mkchallenge(self, ident):
        if type(ident) == types.StringType:
            # it's an error, so we must fail.
            challenge = identity.challenge()
            return challenge, AuthChallenger(None, self, challenge)
        else:
            challenge = ident.challenge()
            return challenge, AuthChallenger(ident, self, challenge)

class _ObjectRetrieval:
    """(Internal) Does callbacks for getObjectAt.
    """

    def __init__(self, broker, d):
        self.deferred = d
        self.term = 0
        self.broker = broker
        # XXX REFACTOR: this seems weird.
        # I'm not inheriting because I have to delegate at least 2 of these
        # things anyway.
        broker.notifyOnFail(self.connectionFailed)
        broker.notifyOnConnect(self.connectionMade)
        broker.notifyOnDisconnect(self.connectionLost)

    def connectionLost(self):
        if not self.term:
            self.term = 1
            del self.broker
            self.deferred.armAndErrback("connection lost")

    def connectionMade(self):
        assert not self.term, "How did this get called?"
        x = self.broker.remoteForName("root")
        del self.broker
        self.term = 1
        self.deferred.armAndCallback(x)

    def connectionFailed(self):
        if not self.term:
            self.term = 1
            del self.broker
            self.deferred.armAndErrback("connection failed")

def getObjectAt(host, port, timeout=None):
    """Establishes a PB connection and returns with a RemoteReference.

    Arguments:

      host: the host to connect to

      port: the port number to connect to

      timeout (optional): a value in milliseconds to wait before failing by
      default.

    Returns:

      A Deferred which will be passed a remote reference to the root object of
      a PB server.x
    """
    d = defer.Deferred()
    b = Broker(1)
    _ObjectRetrieval(b, d)
    tcp.Client(host, port, b, timeout)
    return d

def connect(host, port, username, password, serviceName,
            perspectiveName=None, client=None, timeout=None):
    """Connects and authenticates, then retrieves a PB service.

    Required arguments:
        host -- the host the service is running on
        port -- the port on the host to connect to
        username -- the name you will be identified as to the authorizer
        password -- the password for this username
        serviceName -- name of the service to request

    Optional (keyword) arguments:
        perspectiveName -- the name of the perspective to request, if
            different than the username
        client -- XXX the "reference" argument to
                  perspective.Perspective.attached
        timeout -- see twisted.internet.tcp.Client

    Returns:

        A Deferred instance that gets a callback when the final Perspective is
        connected, and an errback when an error occurs at any stage of
        connecting.

    """
    d = defer.Deferred()
    getObjectAt(host,port,timeout).addCallbacks(
        _connGotRoot, d.armAndErrback,
        callbackArgs=[d, client, serviceName,
                      username, password, perspectiveName])
    return d

def _connGotRoot(root, d, client, serviceName,
                 username, password, perspectiveName):
    logIn(root, client, serviceName, username, password, perspectiveName).armAndChain(d)

def authIdentity(authServRef, username, password):
    """Return a Deferred which will do the challenge-response dance and
    return a remote Identity reference.
    """
    d = defer.Deferred()
    authServRef.callRemote('username', username).addCallbacks(
        _cbRespondToChallenge, d.armAndErrback,
        callbackArgs=(password,d))
    return d

def _cbRespondToChallenge((challenge, challenger), password, d):
    challenger.callRemote("respond", identity.respond(challenge, password)).addCallbacks(
        d.armAndCallback, d.armAndErrback)

def logIn(authServRef, client, service, username, password, perspectiveName=None):
    """I return a Deferred which will be called back with a Perspective.
    """
    d = defer.Deferred()
    authServRef.callRemote('username', username).addCallbacks(
        _cbLogInRespond, d.armAndErrback,
        callbackArgs=(d, client, service, password,
                      perspectiveName or username))
    return d

def _cbLogInRespond((challenge, challenger), d, client, service, password, perspectiveName):
    challenger.callRemote('respond',
        identity.respond(challenge, password)).addCallbacks(
        _cbLogInResponded, d.armAndErrback,
        callbackArgs=(d, client, service, perspectiveName))

def _cbLogInResponded(identity, d, client, serviceName, perspectiveName):
    if identity:
        identity.callRemote("attach", serviceName, perspectiveName, client).armAndChain(d)
    else:
        d.armAndErrback("invalid username or password")
