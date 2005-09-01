# -*- test-case-name: twisted.test.test_pb -*-
#
# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.


"""
Perspective Broker

\"This isn\'t a professional opinion, but it's probably got enough
internet to kill you.\" --glyph

Stability: semi-stable

Future Plans: The connection APIs will be extended with support for
URLs, that will be able to extend resource location and discovery
conversations and specify different authentication mechanisms besides
username/password.  This should only add to, and not change, the
existing protocol.


Important Changes
=================

New APIs have been added for serving and connecting. On the client
side, use PBClientFactory.getPerspective() instead of connect(), and
PBClientFactory.getRootObject() instead of getObjectAt().  Server side
should switch to updated cred APIs by using PBServerFactory, at which
point clients would switch to PBClientFactory.login().

The new cred support means a different method is sent for login,
although the protocol is compatible on the binary level. When we
switch to pluggable credentials this will introduce another change,
although the current change will still be supported.

The Perspective class is now deprecated, and has been replaced with
Avatar, which does not rely on the old cred APIs.


Introduction
============

This is a broker for proxies for and copies of objects.  It provides a
translucent interface layer to those proxies.

The protocol is not opaque, because it provides objects which
represent the remote proxies and require no context (server
references, IDs) to operate on.

It is not transparent because it does I{not} attempt to make remote
objects behave identically, or even similiarly, to local objects.
Method calls are invoked asynchronously, and specific rules are
applied when serializing arguments.

@author: U{Glyph Lefkowitz<mailto:glyph@twistedmatrix.com>}
"""

__version__ = "$Revision: 1.157 $"[11:-2]


# System Imports
try:
    import cStringIO as StringIO
except ImportError:
    import StringIO

import sys
import types
import warnings

# Twisted Imports
from twisted.python import log, failure, components, reflect
from twisted.internet import reactor, defer, protocol, error
from twisted.cred import authorizer, service, perspective, identity
from twisted.cred.portal import Portal
from twisted.persisted import styles
from twisted.python.components import Interface, registerAdapter, backwardsCompatImplements
from twisted.python.components import backwardsCompatImplements

from zope.interface import implements

# Sibling Imports
from twisted.spread.interfaces import IJellyable, IUnjellyable
from jelly import jelly, unjelly, globalSecurity
import banana

# Tightly coupled sibling import
from flavors import Serializable
from flavors import Referenceable, NoSuchMethod
from flavors import Root, IPBRoot
from flavors import ViewPoint
from flavors import Viewable
from flavors import Copyable
from flavors import Jellyable
from flavors import Cacheable
from flavors import RemoteCopy
from flavors import RemoteCache
from flavors import RemoteCacheObserver
from flavors import copyTags
from flavors import setCopierForClass, setUnjellyableForClass
from flavors import setFactoryForClass
from flavors import setCopierForClassTree

MAX_BROKER_REFS = 1024

portno = 8787


class ProtocolError(Exception):
    """
    This error is raised when an invalid protocol statement is received.
    """

class DeadReferenceError(ProtocolError):
    """
    This error is raised when a method is called on a dead reference (one whose
    broker has been disconnected).
    """

class Error(Exception):
    """
    This error can be raised to generate known error conditions.

    When a PB callable method (perspective_, remote_, view_) raises
    this error, it indicates that a traceback should not be printed,
    but instead, the string representation of the exception should be
    sent.
    """

class RemoteMethod:
    """This is a translucent reference to a remote message.
    """
    def __init__(self, obj, name):
        """Initialize with a L{RemoteReference} and the name of this message.
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

class PBConnectionLost(Exception):
    pass

def printTraceback(tb):
    """Print a traceback (string) to the standard log.
    """

    log.msg('Perspective Broker Traceback:' )
    log.msg(tb)

class IPerspective(Interface):
    """
    per*spec*tive, n. : The relationship of aspects of a subject to each
    other and to a whole: 'a perspective of history'; 'a need to view
    the problem in the proper perspective'.

    This is a Perspective Broker-specific wrapper for an avatar. That
    is to say, a PB-published view on to the business logic for the
    system's concept of a 'user'.

    The concept of attached/detached is no longer implemented by the
    framework. The realm is expected to implement such semantics if
    needed.
    """

    def perspectiveMessageReceived(self, broker, message, args, kwargs):
        """
        This method is called when a network message is received.

        @arg broker: The Perspective Broker.

        @type message: str
        @arg message: The name of the method called by the other end.

        @type args: list in jelly format
        @arg args: The arguments that were passed by the other end. It
                   is recommend that you use the `unserialize' method of the
                   broker to decode this.

        @type kwargs: dict in jelly format
        @arg kwargs: The keyword arguments that were passed by the
                     other end.  It is recommended that you use the
                     `unserialize' method of the broker to decode this.

        @rtype: A jelly list.
        @return: It is recommended that you use the `serialize' method
                 of the broker on whatever object you need to return to
                 generate the return value.
        """



class Avatar:
    """A default IPerspective implementor.

    This class is intended to be subclassed, and a realm should return
    an instance of such a subclass when IPerspective is requested of
    it.

    A peer requesting a perspective will receive only a
    L{RemoteReference} to a pb.Avatar.  When a method is called on
    that L{RemoteReference}, it will translate to a method on the
    remote perspective named 'perspective_methodname'.  (For more
    information on invoking methods on other objects, see
    L{flavors.ViewPoint}.)
    """

    implements(IPerspective)

    def perspectiveMessageReceived(self, broker, message, args, kw):
        """This method is called when a network message is received.

        I will call::

          |  self.perspective_%(message)s(*broker.unserialize(args),
          |                               **broker.unserialize(kw))

        to handle the method; subclasses of Avatar are expected to
        implement methods of this naming convention.
        """

        args = broker.unserialize(args, self)
        kw = broker.unserialize(kw, self)
        method = getattr(self, "perspective_%s" % message)
        try:
            state = method(*args, **kw)
        except TypeError:
            log.msg("%s didn't accept %s and %s" % (method, args, kw))
            raise
        return broker.serialize(state, self, method, args, kw)

components.backwardsCompatImplements(Avatar)

class Perspective(perspective.Perspective, Avatar):
    """
    This class is DEPRECATED, because it relies on old cred
    APIs. Please use L{Avatar}.
    """

    def brokerAttached(self, reference, identity, broker):
        """An intermediary method to override.

        Normally you will want to use 'attached', as described in
        L{twisted.cred.perspective.Perspective}.attached; however, this method
        serves the same purpose, and in some circumstances, you are sure that
        the protocol that objects will be attaching to your Perspective with is
        Perspective Broker, and in that case you may wish to get the Broker
        object they are connecting with, for example, to determine what host
        they are connecting from.  Bear in mind that when overriding this
        method, other, non-PB protocols will not notify you of being attached
        or detached.
        """
        warnings.warn("pb.Perspective is deprecated, please use pb.Avatar.", DeprecationWarning, 2)
        return self.attached(reference, identity)

    def brokerDetached(self, reference, identity, broker):
        """See L{brokerAttached}.
        """
        return self.detached(reference, identity)


class Service(service.Service):
    """A service for Perspective Broker.

    This class is DEPRECATED, because it relies on old cred APIs.

    On this Service, the result of a perspective request must be a
    L{pb.Perspective} rather than a L{twisted.cred.perspective.Perspective}.
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

    I may be a reference to a L{flavors.ViewPoint}, a
    L{flavors.Referenceable}, or an L{IPerspective} implementor (e.g.,
    pb.Avatar).  From the client's perspective, it is not possible to
    tell which except by convention.

    I am a \"translucent\" reference because although no additional
    bookkeeping overhead is given to the application programmer for
    manipulating a reference, return values are asynchronous.

    See also L{twisted.internet.defer}.

    @ivar broker: The broker I am obtained through.
    @type broker: L{Broker}
    """

    implements(IUnjellyable)

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

        This callback will be called with one argument, this instance.
        """
        assert callable(callback)
        self.disconnectCallbacks.append(callback)
        if len(self.disconnectCallbacks) == 1:
            self.broker.notifyOnDisconnect(self._disconnected)

    def dontNotifyOnDisconnect(self, callback):
        """Remove a callback that was registered with notifyOnDisconnect."""
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

    def callRemote(self, _name, *args, **kw):
        """Asynchronously invoke a remote method.

        @type _name:   C{string}
        @param _name:  the name of the remote method to invoke
        @param args: arguments to serialize for the remote function
        @param kw:  keyword arguments to serialize for the remote function.
        @rtype:   L{twisted.internet.defer.Deferred}
        @returns: a Deferred which will be fired when the result of
                  this remote call is received.
        """
        # note that we use '_name' instead of 'name' so the user can call
        # remote methods with 'name' as a keyword parameter, like this:
        #  ref.callRemote("getPeopleNamed", count=12, name="Bob")

        return self.broker._sendMessage('',self.perspective, self.luid,
                                        _name, args, kw)

    def remoteMethod(self, key):
        """Get a L{RemoteMethod} for this key.
        """
        return RemoteMethod(self, key)

    def __cmp__(self,other):
        """Compare me [to another L{RemoteReference}].
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
components.backwardsCompatImplements(RemoteReference)

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

##
# Failure
##

class CopyableFailure(failure.Failure, Copyable):
    """
    A L{flavors.RemoteCopy} and L{flavors.Copyable} version of
    L{twisted.python.failure.Failure} for serialization.
    """

    unsafeTracebacks = 0

    def getStateToCopy(self):
        #state = self.__getstate__()
        state = self.__dict__.copy()
        state['tb'] = None
        state['frames'] = []
        state['stack'] = []
        if isinstance(self.value, failure.Failure):
            state['value'] = failure2Copyable(self.value, self.unsafeTracebacks)
        else:
            state['value'] = str(self.value) # Exception instance
        state['type'] = str(self.type) # Exception class
        if self.unsafeTracebacks:
            io = StringIO.StringIO()
            self.printTraceback(io)
            state['traceback'] = io.getvalue()
        else:
            state['traceback'] = 'Traceback unavailable\n'
        return state

class CopiedFailure(RemoteCopy, failure.Failure):
    def printTraceback(self, file=None, elideFrameworkCode=0, detail='default'):
        if file is None:
            file = log.logfile
        file.write("Traceback from remote host -- ")
        file.write(self.traceback)

    printBriefTraceback = printTraceback
    printDetailedTraceback = printTraceback

setUnjellyableForClass(CopyableFailure, CopiedFailure)

def failure2Copyable(fail, unsafeTracebacks=0):
    f = CopyableFailure()
    f.__dict__ = fail.__dict__
    f.unsafeTracebacks = unsafeTracebacks
    return f

class Broker(banana.Banana):
    """I am a broker for objects.
    """

    version = 6
    username = None
    factory = None

    def __init__(self, isClient=1, security=globalSecurity):
        banana.Banana.__init__(self, isClient)
        self.disconnected = 0
        self.disconnects = []
        self.failures = []
        self.connects = []
        self.localObjects = {}
        self.security = security
        self.pageProducers = []
        self.currentRequestID = 0
        self.currentLocalID = 0
        # Some terms:
        #  PUID: process unique ID; return value of id() function.  type "int".
        #  LUID: locally unique ID; an ID unique to an object mapped over this
        #        connection. type "int"
        #  GUID: (not used yet) globally unique ID; an ID for an object which
        #        may be on a redirected or meta server.  Type as yet undecided.
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

    def resumeProducing(self):
        """Called when the consumer attached to me runs out of buffer.
        """
        # Go backwards over the list so we can remove indexes from it as we go
        for pageridx in xrange(len(self.pageProducers)-1, -1, -1):
            pager = self.pageProducers[pageridx]
            pager.sendNextPage()
            if not pager.stillPaging():
                del self.pageProducers[pageridx]
        if not self.pageProducers:
            self.transport.unregisterProducer()

    # Streaming producer methods; not necessary to implement.
    def pauseProducing(self):
        pass

    def stopProducing(self):
        pass

    def registerPageProducer(self, pager):
        self.pageProducers.append(pager)
        if len(self.pageProducers) == 1:
            self.transport.registerProducer(self, 0)

    def expressionReceived(self, sexp):
        """Evaluate an expression as it's received.
        """
        if isinstance(sexp, types.ListType):
            command = sexp[0]
            methodName = "proto_%s" % command
            method = getattr(self, methodName, None)
            if method:
                method(*sexp[1:])
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
        """Respond to stock 'C{didNotUnderstand}' message.

        Log the command that was not understood and continue. (Note:
        this will probably be changed to close the connection or raise
        an exception in the future.)
        """
        log.msg("Didn't understand command: %r" % command)

    def connectionReady(self):
        """Initialize. Called after Banana negotiation is done.
        """
        self.sendCall("version", self.version)
        for notifier in self.connects:
            try:
                notifier()
            except:
                log.deferr()
        self.connects = None
        if self.factory: # in tests we won't have factory
            self.factory.clientConnectionMade(self)

    def connectionFailed(self):
        # XXX should never get called anymore? check!
        for notifier in self.failures:
            try:
                notifier()
            except:
                log.deferr()
        self.failures = None

    waitingForAnswers = None

    def connectionLost(self, reason):
        """The connection was lost.
        """
        self.disconnected = 1
        # nuke potential circular references.
        self.luids = None
        if self.waitingForAnswers:
            for d in self.waitingForAnswers.values():
                try:
                    d.errback(failure.Failure(PBConnectionLost(reason)))
                except:
                    log.deferr()
        # Assure all Cacheable.stoppedObserving are called
        for lobj in self.remotelyCachedObjects.values():
            cacheable = lobj.object
            perspective = lobj.perspective
            try:
                cacheable.stoppedObserving(perspective, RemoteCacheObserver(self, cacheable, perspective))
            except:
                log.deferr()
        # Loop on a copy to prevent notifiers to mixup
        # the list by calling dontNotifyOnDisconnect
        for notifier in self.disconnects[:]:
            try:
                notifier()
            except:
                log.deferr()
        self.disconnects = None
        self.waitingForAnswers = None
        self.localSecurity = None
        self.remoteSecurity = None
        self.remotelyCachedObjects = None
        self.remotelyCachedLUIDs = None
        self.locallyCachedObjects = None
        self.localObjects = None

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
        if self.connects is None:
            try:
                notifier()
            except:
                log.err()
        else:
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
        self.L{registerReference}, or C{None} if XXX:Unfinished thought:XXX
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
            if len(self.localObjects) > MAX_BROKER_REFS:
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
        """Returns an ID that says what this instance is cached as remotely, or C{None} if it's not.
        """

        puid = instance.processUniqueID()
        luid = self.remotelyCachedLUIDs.get(puid)
        if (luid is not None) and (incref):
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
            raise DeadReferenceError("Calling Stale Broker")
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
                # If the error is Jellyable or explicitly allowed via our
                # security options, send it back and let the code on the
                # other end deal with unjellying.  If it isn't Jellyable,
                # wrap it in a CopyableFailure, which ensures it can be
                # unjellied on the other end.  We have to do this because
                # all errors must be sent back.
                if isinstance(e, Jellyable) or self.security.isClassAllowed(e.__class__):
                    self._sendError(e, requestID)
                else:
                    self._sendError(CopyableFailure(e), requestID)
        except:
            if answerRequired:
                log.msg("Peer will receive following PB traceback:", isError=True)
                f = CopyableFailure()
                self._sendError(f, requestID)
            log.deferr()
        else:
            if answerRequired:
                if isinstance(netResult, defer.Deferred):
                    args = (requestID,)
                    netResult.addCallbacks(self._sendAnswer, self._sendFailure,
                                           callbackArgs=args, errbackArgs=args)
                    # XXX Should this be done somewhere else?
                else:
                    self._sendAnswer(netResult, requestID)
    ##
    # success
    ##

    def _sendAnswer(self, netResult, requestID):
        """(internal) Send an answer to a previously sent message.
        """
        self.sendCall("answer", requestID, netResult)

    def proto_answer(self, requestID, netResult):
        """(internal) Got an answer to a previously sent message.

        Look up the appropriate callback and call it.
        """
        d = self.waitingForAnswers[requestID]
        del self.waitingForAnswers[requestID]
        d.callback(self.unserialize(netResult))

    ##
    # failure
    ##

    def _sendFailure(self, fail, requestID):
        """Log error and then send it."""
        log.msg("Peer will receive following PB traceback:")
        log.err(fail)
        self._sendError(fail, requestID)

    def _sendError(self, fail, requestID):
        """(internal) Send an error for a previously sent message.
        """
        if isinstance(fail, failure.Failure):
            # If the failures value is jellyable or allowed through security,
            # send the value
            if (isinstance(fail.value, Jellyable) or
                self.security.isClassAllowed(fail.value.__class__)):
                fail = fail.value
            elif not isinstance(fail, CopyableFailure):
                fail = failure2Copyable(fail, self.factory.unsafeTracebacks)
        if isinstance(fail, CopyableFailure):
            fail.unsafeTracebacks = self.factory.unsafeTracebacks
        self.sendCall("error", requestID, self.serialize(fail))

    def proto_error(self, requestID, fail):
        """(internal) Deal with an error.
        """
        d = self.waitingForAnswers[requestID]
        del self.waitingForAnswers[requestID]
        d.errback(self.unserialize(fail))

    ##
    # refcounts
    ##

    def sendDecRef(self, objectID):
        """(internal) Send a DECREF directive.
        """
        self.sendCall("decref", objectID)

    def proto_decref(self, objectID):
        """(internal) Decrement the reference count of an object.

        If the reference count is zero, it will free the reference to this
        object.
        """
        refs = self.localObjects[objectID].decref()
        if refs == 0:
            puid = self.localObjects[objectID].object.processUniqueID()
            del self.luids[puid]
            del self.localObjects[objectID]

    ##
    # caching
    ##

    def decCacheRef(self, objectID):
        """(internal) Send a DECACHE directive.
        """
        self.sendCall("decache", objectID)

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
        obj.broker = None
##         def reallyDel(obj=obj):
##             obj.__really_del__()
##         obj.__del__ = reallyDel
        del self.locallyCachedObjects[objectID]


class BrokerFactory(protocol.Factory, styles.Versioned):
    """DEPRECATED, use PBServerFactory instead.

    I am a server for object brokerage.
    """

    unsafeTracebacks = 0
    persistenceVersion = 3

    def __init__(self, objectToBroker):
        warnings.warn("This is deprecated. Use PBServerFactory.", DeprecationWarning, 2)
        self.objectToBroker = objectToBroker

    def config_objectToBroker(self, newObject):
        self.objectToBroker = newObject

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

    def clientConnectionMade(self, protocol):
        pass


### DEPRECATED AUTH STUFF

class AuthRoot(Root):
    """DEPRECATED.

    I provide AuthServs as root objects to Brokers for a BrokerFactory.
    """

    def __init__(self, auth):
        from twisted.internet.app import Application
        if isinstance(auth, Application):
            auth = auth.authorizer
        self.auth = auth

    def rootObject(self, broker):
        return AuthServ(self.auth, broker)

class _Detacher:
    """DEPRECATED."""

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
    """DEPRECATED.

    I delegate most functionality to a L{twisted.cred.identity.Identity}.
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
    """DEPRECATED.

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
            return d

    def _authOk(self, result, d):
        d.callback(IdentityWrapper(self.serv.broker, self.ident))

    def _authFail(self, result, d):
        d.callback(None)

class AuthServ(Referenceable):
    """DEPRECATED.

    See also: L{AuthRoot}
    """

    def __init__(self, auth, broker):
        self.auth = auth
        self.broker = broker

    def remote_username(self, username):
        defr = self.auth.getIdentityRequest(username)
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
    """DEPRECATED.

    (Internal) Does callbacks for L{getObjectAt}.
    """

    def __init__(self, broker, d):
        warnings.warn("This is deprecated. Use PBClientFactory.", DeprecationWarning, 2)
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
            self.deferred.errback(error.ConnectionLost())
            del self.deferred


    def connectionMade(self):
        assert not self.term, "How did this get called?"
        x = self.broker.remoteForName("root")
        del self.broker
        self.term = 1
        self.deferred.callback(x)
        del self.deferred

    def connectionFailed(self):
        if not self.term:
            self.term = 1
            del self.broker
            self.deferred.errback(error.ConnectError(string="Connection failed"))
            del self.deferred


class BrokerClientFactory(protocol.ClientFactory):
    noisy = 0
    unsafeTracebacks = 0

    def __init__(self, protocol):
        warnings.warn("This is deprecated. Use PBClientFactory.", DeprecationWarning, 2)
        if not isinstance(protocol,Broker): raise TypeError, "protocol is not an instance of Broker"
        self.protocol = protocol

    def buildProtocol(self, addr):
        return self.protocol

    def clientConnectionFailed(self, connector, reason):
        self.protocol.connectionFailed()

    def clientConnectionMade(self, protocol):
        pass


def getObjectRetriever():
    """DEPRECATED.

    Get a factory which retreives a root object from its client

    @returns: A pair: A ClientFactory and a Deferred which will be passed a
              remote reference to the root object of a PB server.x
    """
    warnings.warn("This is deprecated. Use PBClientFactory.", DeprecationWarning, 2)
    d = defer.Deferred()
    b = Broker(1)
    bf = BrokerClientFactory(b)
    _ObjectRetrieval(b, d)
    return bf, d


def getObjectAt(host, port, timeout=None):
    """DEPRECATED. Establishes a PB connection and returns with a L{RemoteReference}.

    @param host: the host to connect to

    @param port: the port number to connect to

    @param timeout: a value in milliseconds to wait before failing by
      default. (OPTIONAL)

    @returns: A Deferred which will be passed a remote reference to the
      root object of a PB server.x
    """
    warnings.warn("This is deprecated. Use PBClientFactory.", DeprecationWarning, 2)
    bf = PBClientFactory()
    if host == "unix":
        # every time you use this, God kills a kitten
        reactor.connectUNIX(port, bf, timeout)
    else:
        reactor.connectTCP(host, port, bf, timeout)
    return bf.getRootObject()

def getObjectAtSSL(host, port, timeout=None, contextFactory=None):
    """DEPRECATED. Establishes a PB connection over SSL and returns with a RemoteReference.

    @param host: the host to connect to

    @param port: the port number to connect to

    @param timeout: a value in milliseconds to wait before failing by
      default. (OPTIONAL)

    @param contextFactory: A factory object for producing SSL.Context
      objects.  (OPTIONAL)

    @returns: A Deferred which will be passed a remote reference to the
      root object of a PB server.
    """
    warnings.warn("This is deprecated. Use PBClientFactory.", DeprecationWarning, 2)
    bf = PBClientFactory()
    if contextFactory is None:
        from twisted.internet import ssl
        contextFactory = ssl.ClientContextFactory()
    reactor.connectSSL(host, port, bf, contextFactory, timeout)
    return bf.getRootObject()

def connect(host, port, username, password, serviceName,
            perspectiveName=None, client=None, timeout=None):
    """DEPRECATED. Connects and authenticates, then retrieves a PB service.

    Required arguments:
       - host -- the host the service is running on
       - port -- the port on the host to connect to
       - username -- the name you will be identified as to the authorizer
       - password -- the password for this username
       - serviceName -- name of the service to request

    Optional (keyword) arguments:
       - perspectiveName -- the name of the perspective to request, if
            different than the username
       - client -- XXX the \"reference\" argument to
                  perspective.Perspective.attached
       - timeout -- see twisted.internet.tcp.Client

    @returns: A Deferred instance that gets a callback when the final
              Perspective is connected, and an errback when an error
              occurs at any stage of connecting.
    """
    warnings.warn("This is deprecated. Use PBClientFactory.", DeprecationWarning, 2)
    if timeout == None:
        timeout = 30
    bf = PBClientFactory()
    if host == "unix":
        # every time you use this, God kills a kitten
        reactor.connectUNIX(port, bf, timeout)
    else:
        reactor.connectTCP(host, port, bf, timeout)
    return bf.getPerspective(username, password, serviceName, perspectiveName, client)

def _connGotRoot(root, d, client, serviceName,
                 username, password, perspectiveName):
    warnings.warn("This is deprecated. Use PBClientFactory.", DeprecationWarning, 2)
    logIn(root, client, serviceName, username, password, perspectiveName).chainDeferred(d)

def authIdentity(authServRef, username, password):
    """DEPRECATED. Return a Deferred which will do the challenge-response dance and
    return a remote Identity reference.
    """
    warnings.warn("This is deprecated. Use PBClientFactory.", DeprecationWarning, 2)
    d = defer.Deferred()
    authServRef.callRemote('username', username).addCallbacks(
        _cbRespondToChallenge, d.errback,
        callbackArgs=(password,d))
    return d

def _cbRespondToChallenge((challenge, challenger), password, d):
    warnings.warn("This is deprecated. Use PBClientFactory.", DeprecationWarning, 2)
    challenger.callRemote("respond", identity.respond(challenge, password)).addCallbacks(
        d.callback, d.errback)

def logIn(authServRef, client, service, username, password, perspectiveName=None):
    """DEPRECATED. I return a Deferred which will be called back with a Perspective.
    """
    warnings.warn("This is deprecated. Use PBClientFactory.", DeprecationWarning, 2)
    d = defer.Deferred()
    authServRef.callRemote('username', username).addCallbacks(
        _cbLogInRespond, d.errback,
        callbackArgs=(d, client, service, password,
                      perspectiveName or username))
    return d

def _cbLogInRespond((challenge, challenger), d, client, service, password, perspectiveName):
    warnings.warn("This is deprecated. Use PBClientFactory.", DeprecationWarning, 2)
    challenger.callRemote('respond',
        identity.respond(challenge, password)).addCallbacks(
        _cbLogInResponded, d.errback,
        callbackArgs=(d, client, service, perspectiveName))

def _cbLogInResponded(identity, d, client, serviceName, perspectiveName):
    warnings.warn("This is deprecated. Use PBClientFactory.", DeprecationWarning, 2)
    if identity:
        identity.callRemote("attach", serviceName, perspectiveName, client).chainDeferred(d)
    else:
        from twisted import cred
        d.errback(cred.error.Unauthorized("invalid username or password"))

class IdentityConnector:
     """DEPRECATED.

     I support connecting to multiple Perspective Broker services that are
     in a service tree.
     """
     def __init__(self, host, port, identityName, password):
         """
         @type host:               C{string}
         @param host:              The host to connect to or the PB server.
                                   If this is C{"unix"}, then a UNIX socket
                                   will be used rather than a TCP socket.
         @type port:               C{integer}
         @param port:              The port to connect to for the PB server.
         @type identityName:       C{string}
         @param identityName:      The name of the identity to use to
                                   autheticate with the PB server.
         @type password:           C{string}
         @param password:          The password to use to autheticate with
                                   the PB server.
         """
         warnings.warn("This is deprecated. Use PBClientFactory.", DeprecationWarning, 2)
         self.host = host
         self.port = port
         self.identityName = identityName
         self.password = password
         self._identityWrapper = None
         self._connectDeferreds = []
         self._requested = 0

     def _cbGotAuthRoot(self, authroot):
         authIdentity(authroot, self.identityName,
                      self.password).addCallbacks(
             self._cbGotIdentity, self._ebGotIdentity)

     def _cbGotIdentity(self, i):
         self._identityWrapper = i
         if i:
             for d in self._connectDeferreds:
                 d.callback(i)
             self._connectDeferreds[:] = []
         else:
             from twisted import cred
             e = cred.error.Unauthorized("invalid username or password")
             self._ebGotIdentity(e)

     def _ebGotIdentity(self, e):
         self._requested = 0
         for d in self._connectDeferreds:
             d.errback(e)
         self._connectDeferreds[:] = []

     def requestLogin(self):
         """
         Attempt to authenticate about the PB server, but don't
         request any services, yet.

         @returns:                  L{IdentityWrapper}
         @rtype:                    L{twisted.internet.defer.Deferred}
         """
         if not self._identityWrapper:
             d = defer.Deferred()
             self._connectDeferreds.append(d)
             if not self._requested:
                 self._requested = 1
                 getObjectAt(self.host, self.port).addCallbacks(
                     self._cbGotAuthRoot, self._ebGotIdentity)
             return d
         else:
             return defer.succeed(self._identityWrapper)

     def requestService(self, serviceName, perspectiveName=None,
                        client=None):
         """
         Request a perspective on the specified service.  This will
         authenticate against the server as well if L{requestLogin}
         hasn't already been called.

         @type serviceName:         C{string}
         @param serviceName:        The name of the service to obtain
                                    a perspective for.
         @type perspectiveName:     C{string}
         @param perspectiveName:    If specified, the name of the
                                    perspective to obtain.  Otherwise,
                                    default to the name of the identity.
         @param client:             The client object to attach to
                                    the perspective.

         @rtype:                    L{twisted.internet.defer.Deferred}
         @return:                   A deferred which will receive a callback
                                    with the perspective.
         """
         return self.requestLogin().addCallback(
             lambda i, self=self: i.callRemote("attach",
                                               serviceName,
                                               perspectiveName,
                                               client))

     def disconnect(self):
         """Lose my connection to the server.

         Useful to free up resources if you've completed requestLogin but
         then change your mind.
         """
         if not self._identityWrapper:
             return
         else:
             self._identityWrapper.broker.transport.loseConnection()


# this is the new shiny API you should be using:

import md5
import random
from twisted.cred.credentials import ICredentials, IUsernameHashedPassword

def respond(challenge, password):
    """Respond to a challenge.

    This is useful for challenge/response authentication.
    """
    m = md5.new()
    m.update(password)
    hashedPassword = m.digest()
    m = md5.new()
    m.update(hashedPassword)
    m.update(challenge)
    doubleHashedPassword = m.digest()
    return doubleHashedPassword

def challenge():
    """I return some random data."""
    crap = ''
    for x in range(random.randrange(15,25)):
        crap = crap + chr(random.randint(65,90))
    crap = md5.new(crap).digest()
    return crap


class PBClientFactory(protocol.ClientFactory):
    """Client factory for PB brokers.

    As with all client factories, use with reactor.connectTCP/SSL/etc..
    getPerspective and getRootObject can be called either before or
    after the connect.
    """

    protocol = Broker
    unsafeTracebacks = 0

    def __init__(self):
        self._reset()

    def _reset(self):
        self.rootObjectRequests = [] # list of deferred
        self._broker = None
        self._root = None

    def _failAll(self, reason):
        deferreds = self.rootObjectRequests
        self._reset()
        for d in deferreds:
            d.errback(reason)

    def clientConnectionFailed(self, connector, reason):
        self._failAll(reason)

    def clientConnectionLost(self, connector, reason, reconnecting=0):
        """Reconnecting subclasses should call with reconnecting=1."""
        if reconnecting:
            # any pending requests will go to next connection attempt
            # so we don't fail them.
            self._broker = None
            self._root = None
        else:
            self._failAll(reason)

    def clientConnectionMade(self, broker):
        self._broker = broker
        self._root = broker.remoteForName("root")
        ds = self.rootObjectRequests
        self.rootObjectRequests = []
        for d in ds:
            d.callback(self._root)

    def getRootObject(self):
        """Get root object of remote PB server.

        @return Deferred of the root object.
        """
        if self._broker and not self._broker.disconnected:
           return defer.succeed(self._root)
        d = defer.Deferred()
        self.rootObjectRequests.append(d)
        return d

    def getPerspective(self, username, password, serviceName,
                       perspectiveName=None, client=None):
        """Get perspective from remote PB server.

        New systems should use login() instead.

        @return Deferred of RemoteReference to the perspective.
        """
        warnings.warn("Update your backend to use PBServerFactory, and then use login().",
                      DeprecationWarning, 2)
        if perspectiveName == None:
            perspectiveName = username
        d = self.getRootObject()
        d.addCallback(self._cbAuthIdentity, username, password)
        d.addCallback(self._cbGetPerspective, serviceName, perspectiveName, client)
        return d

    def _cbAuthIdentity(self, authServRef, username, password):
        return authServRef.callRemote('username', username).addCallback(
            self._cbRespondToChallenge, password)

    def _cbRespondToChallenge(self, (challenge, challenger), password):
        return challenger.callRemote("respond", respond(challenge, password))

    def _cbGetPerspective(self, identityWrapper, serviceName, perspectiveName, client):
        return identityWrapper.callRemote(
            "attach", serviceName, perspectiveName, client)

    def disconnect(self):
        """If the factory is connected, close the connection.

        Note that if you set up the factory to reconnect, you will need to
        implement extra logic to prevent automatic reconnection after this
        is called.
        """
        if self._broker:
            self._broker.transport.loseConnection()

    def _cbSendUsername(self, root, username, password, client):
        return root.callRemote("login", username).addCallback(
            self._cbResponse, password, client)

    def _cbResponse(self, (challenge, challenger), password, client):
        return challenger.callRemote("respond", respond(challenge, password), client)

    def login(self, credentials, client=None):
        """Login and get perspective from remote PB server.

        Currently only credentials implementing IUsernamePassword are
        supported.

        @return Deferred of RemoteReference to the perspective.
        """
        d = self.getRootObject()
        d.addCallback(self._cbSendUsername, credentials.username, credentials.password, client)
        return d


class PBServerFactory(protocol.ServerFactory):
    """Server factory for perspective broker.

    Login is done using a Portal object, whose realm is expected to return
    avatars implementing IPerspective. The credential checkers in the portal
    should accept IUsernameHashedPassword or IUsernameMD5Password.

    Alternatively, any object implementing or adaptable to IPBRoot can
    be used instead of a portal to provide the root object of the PB
    server.
    """

    unsafeTracebacks = 0

    # object broker factory
    protocol = Broker

    def __init__(self, root, unsafeTracebacks=False):
        self.root = IPBRoot(root)
        self.unsafeTracebacks = unsafeTracebacks

    def buildProtocol(self, addr):
        """Return a Broker attached to me (as the service provider).
        """
        proto = self.protocol(0)
        proto.factory = self
        proto.setNameForLocal("root", self.root.rootObject(proto))
        return proto

    def clientConnectionMade(self, protocol):
        pass


class IUsernameMD5Password(ICredentials):
    """I encapsulate a username and a hashed password.

    This credential is used for username/password over
    PB. CredentialCheckers which check this kind of credential must
    store the passwords in plaintext form or as a MD5 digest.

    @type username: C{str} or C{Deferred}
    @ivar username: The username associated with these credentials.
    """

    def checkPassword(self, password):
        """Validate these credentials against the correct password.

        @param password: The correct, plaintext password against which to
        @check.

        @return: a deferred which becomes, or a boolean indicating if the
        password matches.
        """

    def checkMD5Password(self, password):
        """Validate these credentials against the correct MD5 digest of password.

        @param password: The correct, plaintext password against which to
        @check.

        @return: a deferred which becomes, or a boolean indicating if the
        password matches.
        """




class _PortalRoot:
    """Root object, used to login to portal."""

    implements(IPBRoot)

    def __init__(self, portal):
        self.portal = portal

    def rootObject(self, broker):
        return _PortalWrapper(self.portal, broker)

components.backwardsCompatImplements(_PortalRoot)
registerAdapter(_PortalRoot, Portal, IPBRoot)


class _PortalWrapper(Referenceable):
    """Root Referenceable object, used to login to portal."""

    def __init__(self, portal, broker):
        self.portal = portal
        self.broker = broker

    def remote_login(self, username):
        """Start of username/password login."""
        c = challenge()
        return c, _PortalAuthChallenger(self, username, c)


class _PortalAuthChallenger(Referenceable):
    """Called with response to password challenge."""

    implements(IUsernameHashedPassword, IUsernameMD5Password)

    def __init__(self, portalWrapper, username, challenge):
        self.portalWrapper = portalWrapper
        self.username = username
        self.challenge = challenge

    def remote_respond(self, response, mind):
        self.response = response
        d = self.portalWrapper.portal.login(self, mind, IPerspective)
        d.addCallback(self._loggedIn)
        return d

    def _loggedIn(self, (interface, perspective, logout)):
        if not IJellyable.providedBy(perspective):
            perspective = AsReferenceable(perspective, "perspective")
        self.portalWrapper.broker.notifyOnDisconnect(logout)
        return perspective

    # IUsernameHashedPassword:
    def checkPassword(self, password):
        return self.checkMD5Password(md5.md5(password).digest())

    # IUsernameMD5Password
    def checkMD5Password(self, md5Password):
        md = md5.new()
        md.update(md5Password)
        md.update(self.challenge)
        correct = md.digest()
        return self.response == correct

backwardsCompatImplements(_PortalAuthChallenger)
