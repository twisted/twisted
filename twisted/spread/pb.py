"""

Perspective Broker

    "This isn't a professional opinion, but it's probably got enough internet
    to kill you." --glyph
    
 Introduction

  This is a broker for proxies for and copies of objects.  It provides a
  translucent interface layer to those proxies.

  The protocol is not opaque, because it provides objects which represent the
  remote proxies and req uire no context (server references, IDs) to operate on.

  It is not transparent because it does *not* attempt to make remote objects
  behave identically, or even similiarly, to local objects.  Method calls are
  invoked asynchronously, and specific rules are applied when serializing
  arguments.

"""#'

# System Imports
import traceback
import cStringIO
import copy
import sys
import types
import new

# Twisted Imports
from twisted.python import authenticator, log
from twisted.protocols import protocol

# Sibling Imports
import jelly
import banana

portno = 8787

from twisted.protocols import protocol

class ProtocolError(Exception):
    """
    This error is raised when an invalid protocol statement is received.
    """

class Error(Exception):
    """
    This error can be raised to generate known error conditions.

    When a PB callable method (perspective_, remote_, proxy_) raises this
    error, it indicates that a traceback should not be printed, but instead,
    the string representation of the exception should be sent.
    """

class Serializable:
    """(internal) An object that can be passed remotely.
    
    This is a style of object which can be serialized by Perspective Broker.
    Objects which wish to be referenced or copied remotely have to subclass
    Serializable.  However, clients of Perspective Broker will probably not
    want to directly subclass Serializable; the Flavors of transferable objects
    are listed below.

    What it means to be "serializable" is that an object can be passed to or
    returned from a remote method.  Certain basic types (dictionaries, lists,
    tuples, numbers, strings) are serializable by default; however, classes
    need to choose a specific serialization style: Referenced, Proxied, Copied
    or Cached.

    You may also pass [lists, dictionaries, tuples] of Serializable instances
    to or return them from remote methods, as many levels deep as you like.
    """

    def remoteSerialize(self, broker):
        raise NotImplementedError()

    def processUniqueID(self):
        return id(self)
    
class Message:
    """This is a translucent reference to a remote message.
    """
    def __init__(self, obj, name):
        """Initialize with a Reference and the name of this message.
        """
        self.obj = obj
        self.name = name

    def send(self, *args, **kw):
        """Asynchronously invoke a remote method.
        """
        self.obj.remoteInstanceDo(self.name, args, kw)


def noOperation(*args, **kw):
    """Do nothing.

    Neque porro quisquam est qui dolorem ipsum quia dolor sit amet,
    consectetur, adipisci velit...
    """

PB_CONNECTION_LOST = 'Connection Lost'

def printTraceback(tb):
    log.msg('Perspective Broker Traceback:' )
    log.msg(tb)

class Perspective:
    """A perspective on a service.
    
    per*spec*tive, n. : The relationship of aspects of a subject to each other
    and to a whole: 'a perspective of history'; 'a need to view the problem in
    the proper perspective'.
    
    A service represents a collection of state, plus a collection of
    perspectives.  Perspectives are the way that networked clients have a
    'view' onto an object, or collection of objects on the server.
    
    Although you may have a service onto which there is only one perspective,
    the common case is that a Perspective will be analagous to (or the same as)
    a "user"; if you are creating a PB-enabled service, your User (or
    equivalent) class should subclass Perspective.

    Initially, a peer requesting a perspective will receive only a reference to
    a Perspective.  When a method is called on that reference, it will
    translate to a method on the remote perspective named
    'perspective_methodname'.  (For more information on invoking methods on
    other objects, see Proxy.)
    """

    def remoteMessageReceived(self, broker, message, args, kw):
        """This method is called when a network message is received.

        I will call
        self.perspective_%(message)s(*broker.unserialize(args),
                                     **broker.unserialize(kw))

        to handle the method; subclasses of Perspective are expected to
        implement methods of this naming convention.
        """
        
        args = broker.unserialize(args, self)
        kw = broker.unserialize(kw, self)
        method = getattr(self, "perspective_%s" % message)
        state = apply(method, args, kw)
        return broker.serialize(state, self, method, args, kw)

    def attached(self, broker):
        """Called when a broker is 'attached' to me.

        After being authenticated and sent to the peer who requested me, I will
        receive this message, telling me that this broker is now attached to
        me.
        """

    def detached(self, broker):
        """Called when a broker is 'detached' from me.

        When a peer disconnects, this is called in order to indicate that the
        broker associated with that peer is no longer attached to this
        perspective.
        """




class Service(authenticator.Authenticator):
    """A service for Perspective Broker.
    """

    def getPerspectiveNamed(self, name):
        """Return a perspective that represents a user for this service.

        Raises a KeyError if no such user exists.

        You must implement this method.
        """
        raise NotImplementedError("%s.getPerspectiveNamed" % str(self.__class__))


class Referenced(Serializable):
    perspective = None
    """I am an object sent remotely as a direct reference.

    When one of my subclasses is sent as an argument to or returned from a
    remote method call, I will be serialized by default as a direct reference.

    This means that the peer will be able to call methods on me; a method call
    xxx() from my peer will be resolved to methods of the name remote_xxx.
    """
    def remoteMessageReceived(self, broker, message, args, kw):
        """A remote message has been received.  Dispatch it appropriately.

        The default implementation is to dispatch to a method called
        'remote_messagename' and call it with the same arguments.
        """
        args = broker.unserialize(args)
        kw = broker.unserialize(kw)
        method = getattr(self, "remote_%s" % message)
        state = apply(method, args, kw)
        return broker.serialize(state, self.perspective)

    def remoteSerialize(self, broker):
        """(internal)

        Return a tuple which will be used as the s-expression to serialize this
        to a peer.
        """
        return remote_atom, broker.registerReference(self)

class Proxy(Referenced):
    """I act as an indirect reference to an object accessed through a Perspective.

    Simply put, I combine an object with a perspective so that when a peer
    calls methods on the object I refer to, the method will be invoked with
    that perspective as a first argument, so that it can know who is calling
    it.

    While Proxied objects will be converted to Proxies by default when they are
    returned from or sent as arguments to a remote method, any object may be
    manually proxied as well.

    This can be useful when dealing with Perspectives, Copieds, and Cacheds.
    It is legal to implement a method as such on a perspective::

      def perspective_getProxyForOther(self, name):
          return Proxy(self, self.service.getPerspectiveNamed(name))

    This will allow you to have references to Perspective objects in two
    different ways.  One is through the initial requestPerspective call -- each
    peer will have a reference to their perspective directly.  The other is
    through this method; each peer can get a reference to all other
    perspectives in the service; but that reference will be to a Proxy, not
    directly to the object.

    The practical offshoot of this is that you can implement 2 varieties of
    remotely callable methods on this Perspective; proxy_xxx and
    perspective_xxx.  proxy_xxx methods will follow the rules for Proxy methods
    (see Proxy.remoteMessageReceived), and perspective_xxx methods will follow
    the rules for Perspective methods.
    """

    def __init__(self, perspective, object):
        """Initialize me with a Perspective and an Object.
        """
        self.perspective = perspective
        self.object = object

    def processUniqueID(self):
        """Return an ID unique to a proxy for this perspective+object combination.
        """
        return (id(self.perspective), id(self.object))

    def remoteSerialize(self, broker):
        """(internal) Serialize remotely.
        """
        # waste not, want not
        return remote_atom, broker.registerReference(self)

    def remoteMessageReceived(self, broker, message, args, kw):
        """A remote message has been received.  Dispatch it appropriately.

        The default implementation is to dispatch to a method called
        'proxy_messagename' to my Object and call it on my object with the same
        arguments, modified by inserting my Perspective as the first argument.
        """
        args = broker.unserialize(args, self.perspective)
        kw = broker.unserialize(kw, self.perspective)
        method = getattr(self.object, "proxy_%s" % message)
        state = apply(method, (self.perspective,)+args, kw)
        rv = broker.serialize(state, self.perspective, method, args, kw)
        return rv


class Proxied(Serializable):
    """I will be converted to a Proxy when passed to or returned from a remote method.

    The beginning of a peer's interaction with a PB Service is always through a
    perspective.  However, if a perspective_xxx method returns a Proxied, it will
    be serialized to the peer as a response to that method.

    """
    proxy = Proxy

    def remoteSerialize(self, broker):
        # getPerspective will have to return different values from different
        # threads, if this is ever to be made thread safe!
        return self.proxy(broker.getPerspective(), self).remoteSerialize(broker)



class Copied(Serializable):
    """Subclass me to get copied each time you are returned from or passed to a remote method.

    When I am returned from or passed to a remote method call, I will be
    converted into data via a set of callbacks (see my methods for more info).
    That data will then be serialized using Jelly, and sent to the peer.

    The peer will then look up the type to represent this with; see Copy for
    details.
    """
    def getStateToCopy(self):
        """Gather state to send when I am serialized for a peer.

        I will default to returning self.__dict__.  Override this to customize
        this behavior.
        """
        return self.__dict__

    def getStateToCopyFor(self, perspective):
        """Gather state to send when I am serialized for a particular perspective.

        I will default to calling getStateToCopy.  Override this to customize
        this behavior.
        """
        return self.getStateToCopy()

    def getTypeToCopy(self):
        """Determine what type tag to send for me.

        By default, send the string representation of my class
        (package.module.Class); normally this is adequate, but you may override
        this to change it.
        """
        return str(self.__class__)

    def getTypeToCopyFor(self, perspective):
        """Determine what type tag to send for me.

        By default, defer to self.getTypeToCopy() normally this is adequate,
        but you may override this to change it.
        """
        return self.getTypeToCopy()

    def remoteSerialize(self, broker):
        """Assemble type tag and state to copy for this broker.

        This will call getTypeToCopyFor and getStateToCopy, and return an
        appropriate s-expression to represent me.  Do not override this method.
        """
        p = broker.getPerspective()
        return (copy_atom, self.getTypeToCopyFor(p),
                broker.jelly(self.getStateToCopyFor(p)))


class Copy:
    """I am a remote copy of a Copied object.

    When the state from a Copied object is received, an instance will be
    created based on the copy tags table (see setCopierForClass) and sent the
    setCopiedState message.  I provide a reasonable default implementation of
    that message; subclass me if you wish to serve as a copier for remote data.

    NOTE: copiers are invoked with no arguments.  Do not implement a
    constructor which requires args in a subclass of Copy!
    """
    def setCopiedState(self, state):
        """I will be invoked with the state to copy locally.

        'state' is the data returned from the remote object's
        'getStateToCopyFor' method, which will often be the remote object's
        dictionary (or a filtered approximation of it depending on my peer's
        perspective).
        """
        self.__dict__ = state

class Cache(Copy):
    """A cache is a local representation of a remote Cached object.

    This represents the last known state of this object.  It may also have
    methods invoked on it -- in order to update caches, the cached class
    generates a reference to this object as it is originally sent.

    Much like copy, I will be invoked with no arguments.  Do not implement a
    constructor that requires arguments in one of my subclasses.
    """
    def remoteMessageReceived(self, broker, message, args, kw):
        """A remote message has been received.  Dispatch it appropriately.

        The default implementation is to dispatch to a method called
        'observe_messagename' and call it on my  with the same arguments.
        """
        args = broker.unserialize(args)
        kw = broker.unserialize(kw)
        method = getattr(self, "observe_%s" % message)
        state = apply(method, args, kw)
        return broker.serialize(state, None, method, args, kw)

copyTags = {}

def setCopierForClass(classname, copier):
    """Set which local class will represent a remote type.
    
    If you have written a Copied class that you expect your client to be
    receiving, write a local "copy" class to represent it, then call::
    
      pb.setCopierForClass('module.package.Class', MyCopier).

    Call this at the module level immediately after its class definition.
    MyCopier should be a subclass of Copy.

    The classname may be a special tag returned by 'Copied.getTypeToCopyFor'
    rather than an actual classname.

    This call is also for cached classes, since there will be no overlap.  The
    rules are the same.
    """
    global copyTags
    copyTags[classname] = copier


class CacheMethod:
    """A method on a reference to a Cache.
    """
    def __init__(self, name, broker, cached, perspective):
        """(internal) initialize.
        """
        self.name = name
        self.broker = broker
        self.perspective = perspective
        self.cached = cached

    def do(self, *args, **kw):
        """(internal) action method.
        """
        self.cached.remoteCacheDo(self.broker, self.name, self.perspective, args, kw)
        

class CacheObserver:
    """I am a reverse-reference to the peer's Cache.

    I am generated automatically when a cache is serialized.  I represent a
    reference to the client's Cache object that will represent a particular
    Cache; I am the additional object passed to getStateToCacheAndObserveFor.
    """
    def __init__(self, broker, cached, perspective):
        """Initialize me pointing at a client side cache for a particular broker/perspective.
        """
        self.broker = broker
        self.cached = cached
        self.perspective = perspective

    def __repr__(self):
        return "<CacheObserver(%s, %s, %s) at %s>" % (
            self.broker, self.cached, self.perspective, id(self))
    
    def __hash__(self):
        """generate a hash unique to all CacheObservers for this broker/perspective/cached triplet
        """
        return (  (hash(self.broker) % 2**10)
                + (hash(self.perspective) % 2**10)
                + (hash(self.cached) % 2**10))
    
    def __cmp__(self, other):
        """compare me to another CacheObserver
        """
        return cmp((self.broker, self.perspective, self.cached), other)
    
    def __getattr__(self, key):
        """Create a CacheMethod.
        """
        if key[:2]=='__' and key[-2:]=='__':
            raise AttributeError(key)
        return CacheMethod(key, self.broker, self.cached, self.perspective).do


class Cached(Copied):
    """A cached instance.

    This means that it's copied; but there is some logic to make sure that it's
    only copied once.  Additionally, when state is retrieved, it is passed a
    "proto-reference" to the state as it will exist on the client.

    XXX: The documentation for this class needs work, but it's the most complex
    part of PB and it is inherently difficult to explain.
    """

    def getStateToCacheAndObserveFor(self, perspective, observer):
        """Get state to cache on the client and client-cache reference to observe locally.

        This is similiar to getStateToCopyFor, but it additionally passes in a
        reference to the client-side Cache instance that will be created when
        it is unserialized.  This allows Cached instances to keep their Caches
        up to date when they change, such that no changes can occurr between
        the point at which the state is initially copied and the client
        receives it that are not propogated.
        """
        return self.getStateToCopyFor(perspective)
    
    def remoteSerialize(self, broker):
        """Return an appropriate tuple to serialize me.

        Depending on whether this broker has cached me or not, this may return
        either a full state or a reference to an existing cache.
        """
        luid = broker.cachedRemotelyAs(self)
        if luid is None:
            luid = broker.cacheRemotely(self)
            p = broker.getPerspective()
            type_ = self.getTypeToCopyFor(p)
            observer = CacheObserver(broker, self, p)
            state = self.getStateToCacheAndObserveFor(p, observer)
            jstate = broker.jelly(state)
            return cache_atom, luid, type_, jstate
        else:
            return cached_atom, luid

    def remoteCacheDo(self, broker, methodName, perspective, args, kw):
        """Call this method on the remotely cached version of this object. (For a given broker.)
        """
        cacheID = broker.cachedRemotelyAs(self)
        assert cacheID is not None, "You can't call a cached method when the object hasn't been given to the other side yet."
        callback = kw.get("pbcallback")
        errback = kw.get("pberrback")
        if kw.has_key('pbcallback'):
            del kw['pbcallback']
        if kw.has_key('pberrback'):
            del kw['pberrback']
        broker.sendCacheMessage(cacheID, methodName, perspective, args, kw, callback, errback)

class Reference(Serializable):
    """This is a translucent reference to a remote object.

    I may be a reference to a Proxy, a Referenced, or a Perspective.  From the
    client's perspective, it is not possible to tell which except by convention.

    I am a "translucent" reference because although no additional bookkeeping
    overhead is given to the application programmer for manipulating a
    reference, return values are asynchronous.

    In order to get a return value from a Referenced method, you must pass a
    callback in as a 'pbcallback'.  Errors can be detected with a 'pberrback'.
    For example::

      def doIt(reference):
          reference.doIt("hello","world", frequency=2,
                         pbcallback=didIt,
                         pberrback=couldntDoIt)
      def didIt(result):
          print 'I did it and the answer was: %s'% result
      def couldntDoIt(traceback):
          print 'I couldn't do it and the traceback was: %s' % traceback

    This snippet of code will execute a method and report feedback.
    """

    def __init__(self, perspective, broker, luid, doRefCount):
        """(internal) Initialize me with a broker and a locally-unique ID.

        The ID is unique only to the particular Perspective Broker instance.
        """
        self.luid = luid
        self.broker = broker
        self.doRefCount = doRefCount
        self.perspective = perspective

    def remoteSerialize(self, broker):
        """If I am being sent back to where I came from, serialize as a local backreference.
        """
        assert self.broker == broker, "Can't send references to brokers other than their own."
        return local_atom, self.luid

    def __getattr__(self, key):
        """Get a Message for this key.

        This makes attributes translucent, so that the method call syntax
        foo.bar(baz) will still work.  However, please note that method calls
        are asynchronous, so return values and exceptions will not be
        propogated.  (Message calls always return None.)
        """
        if key[:2]=='__' and key[-2:]=='__':
            raise AttributeError(key)
        return Message(self, key).send


    def remoteInstanceDo(self, key, args, kw):
        """Asynchronously send a named message to the object which I proxy for.
        """
        callback = kw.get("pbcallback")
        errback = kw.get("pberrback")
        if kw.has_key('pbcallback'):
            del kw['pbcallback']
        if kw.has_key('pberrback'):
            del kw['pberrback']
        self.broker.sendMessage(self.perspective, self.luid,
                                key, args, kw,
                                callback, errback)

    def __cmp__(self,other):
        """Compare me [to another Reference].
        """
        if isinstance(other, Reference):
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

class CacheProxy(Serializable):
    """I am an ugly implementation detail.
    
    Cached objects have to be manually reference counted in order to properly
    do handshaking on removing references to them.  I aid in that; when you
    *think* you have a reference to a Cache, you actually have a reference to
    me.
    """
    __inited = 0
    def __init__(self, broker, instance, luid):
        self.__broker = broker
        self.__instance = instance
        self.__luid = luid
        self.__inited = 1

    def remoteSerialize(self, broker):
        """serialize me (only for the broker I'm for) as the original cached reference
        """
        assert broker is self.__broker, "You cannot exchange cached proxies between brokers."
        return 'lcache', self.__luid

    def __getattr__(self, name):
        """Get a method or attribute from my cache.
        """
        assert name != '_CacheProxy__instance', "Infinite recursion."
        inst = self.__instance
        maybeMethod = getattr(inst, name)
        if isinstance(maybeMethod, types.MethodType):
            if maybeMethod.im_self is inst:
                psuedoMethod = new.instancemethod(maybeMethod.im_func,
                                                  self,
                                                  CacheProxy)
                return psuedoMethod
        if maybeMethod is inst:
            return self
        return maybeMethod

    def __repr__(self):
        """String representation.
        """
        return "CacheProxy(%s)" % repr(self.__instance)
    def __str__(self):
        """Printable representation.
        """
        return "CacheProxy(%s)" % str(self.__instance)

    def __setattr__(self, name, value):
        """Set an attribute of my cache.
        """
        if self.__inited:
            setattr(self.__instance, name, value)
        else:
            self.__dict__[name] = value

    def __cmp__(self, other):
        """Compare me [to another CacheProxy.
        """
        if isinstance(other, CacheProxy):
            return cmp(self.__instance, other.__instance)
        else:
            return cmp(self.__instance, other)

    def __hash__(self):
        """Hash me.
        """
        return hash(self.__instance)

    def __del__(self):
        """Do distributed reference counting on finalize.
        """
        try:
            self.__broker.decCacheRef(self.__luid)
        except:
            traceback.print_exc(file=log.logfile)


class Local:
    """(internal) A reference to a local object.
    """
    def __init__(self, object):
        """Initialize.
        """
        self.object = object
        self.refcount = 1

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


copy_atom = "copy"
cache_atom = "cache"
cached_atom = "cached"
remote_atom = "remote"
local_atom = "local"


class _NetJellier(jelly._Jellier):
    """A Jellier for pb, serializing all serializable flavors.
    """
    def __init__(self, broker):
        """initialize me for a single request.
        """
        jelly._Jellier.__init__(self, broker.localSecurity, None)
        self.broker = broker
        
    def _jelly_instance(self, instance):
        """(internal) replacement method
        """
        assert isinstance(instance, Serializable),\
               'non-serializable %s (%s) for: %s %s %s' % (
            str(instance.__class__),
            str(instance),
            str(self.broker.jellyMethod),
            str(self.broker.jellyArgs),
            str(self.broker.jellyKw))
            
        sxp = self._prepare(instance)
        tup = instance.remoteSerialize(self.broker)
        map(sxp.append, tup)
        return self._preserve(instance, sxp)

class _NetUnjellier(jelly._Unjellier):
    """An unjellier for PB.

    This unserializes the various Serializable flavours in PB.
    """
    def __init__(self, broker):
        jelly._Unjellier.__init__(self, broker.localSecurity, None)
        self.broker = broker

    def _unjelly_copy(self, rest):
        """Unserialize a Copied.
        """
        global copyTags
        inst = copyTags[rest[0]]()
        self._reference(inst)
        return jelly._Promise(self, inst, "copy", rest), inst

    def _postunjelly_copy(self, rest, inst):
        state = self.unjelly(rest[1])
        inst.setCopiedState(state)

    def _unjelly_cache(self, rest):
        global copyTags
        luid = rest[0]
        cNotProxy = copyTags[rest[1]]()
        cProxy = CacheProxy(self.broker, cNotProxy, luid)
        self._reference(cProxy)
        self.broker.cacheLocally(luid, cNotProxy)
        return jelly._Promise(self, cNotProxy, "cache", rest), cProxy

    def _postunjelly_cache(self, rest, inst):
        state = self.unjelly(rest[2])
        inst.setCopiedState(state)

    def _unjelly_cached(self, rest):
        luid = rest[0]
        cNotProxy = self.broker.cachedLocallyAs(luid)
        cProxy = CacheProxy(self.broker, cNotProxy, luid)
        self._reference(cProxy)
        return jelly._FalsePromise(), cProxy

    def _unjelly_lcache(self, rest):
        luid = rest[0]
        obj = self.broker.remotelyCachedForLUID(luid)
        self._reference(obj)
        return jelly._FalsePromise(), obj

    def _unjelly_remote(self, rest):
        obj = Reference(self.broker.getPerspective(), self.broker, rest[0], 1)
        self._reference(obj)
        return jelly._FalsePromise(), obj

    def _unjelly_local(self, rest):
        obj = self.broker.localObjectForID(rest[0])
        self._reference(obj)
        return jelly._FalsePromise(), obj


class Broker(banana.Banana):
    """I am a broker for objects.
    """
    
    version = 2
    username = None

    def __init__(self):
        banana.Banana.__init__(self)
        self.awaitingPerspectives = {}
        self.serverServices = {}
        self.expq = []
        self.perspectives = {}
        self.disconnected = 0
        self.disconnects = []

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
        Check to make sure that both ends of the protocol are speaking the same
        version dialect.
        """
        assert vnum == self.version, "Version Incompatibility: %s %s" % (self.version, vnum)


    def sendCall(self, *exp):
        """Utility method to send an expression to the other side of the connection.
        """
        self.sendEncoded(exp)

    def proto_didNotUnderstand(self, command):
        """Respond to stock 'didNotUnderstand' message.
        
        Log the command that was not understood and continue. (Note: this will
        probably be changed to close the connection or raise an exception in
        the future.)
        """
        log.msg( "Didn't understand command:", repr(command) )

    def addService(self, name, service):
        self.myServices[name] = service

    def getService(self, name):
        foo = self.myServices.get(name)
        if foo is None:
            return self.serverServices[name]
        return foo

    def proto_login(self, service, username, objid):
        """Receive a service, login name, and object, and respond with a challenge.

        This is the second step in the protocol, the first being version number
        checking.  The peer to this is requestPerspective.

        See the documentation for twisted.python.authenticator for more
        information on the challenge/response system that is used here.
        """
        self.username = username
        self.loginService = self.getService(service)
        self.loginTag = service
        self.loginObjID = objid
        self.challenge = authenticator.challenge()
        self.sendCall("challenge", self.challenge)

    def proto_password(self, password):
        """Receive a password, and authenticate using it.
        
        This will use the provided authenticator to authenticate, using the
        previously-sent challenge and previously-received username.
        """
        assert self.username is not None, "login directive must appear *BEFORE* password directive"
        try:
            self.loginService.authenticate(self.username, self.challenge, password)
            perspective = self.loginService.getPerspectiveNamed(self.username)
            if self.loginObjID == -1:
                loginObj = None
            else:
                loginObj = Reference(perspective, self, self.loginObjID, 1)
            perspective.attached(loginObj)
            self.perspectives[self.loginTag] = (perspective, loginObj)
            self.setNameForLocal(self.loginTag, perspective)
            self.sendCall("perspective", self.loginTag)
            del self.username
            del self.challenge
            del self.loginTag
            del self.loginService
            del self.loginObjID
        except authenticator.Unauthorized:
            log.msg("Unauthorized Login Attempt: %s" % self.username)
            self.sendCall("inperspective", self.loginTag)
            # TODO; this should do some more heuristics rather than just
            # closing the connection immediately.
            self.transport.loseConnection()

    def connectionMade(self):
        """Initialize.
        """
        # Some terms:
        #  PUID: process unique ID; return value of id() function.  type "int".
        #  LUID: locally unique ID; an ID unique to an object mapped over this
        #        connection. type "int"
        #  GUID: (not used yet) globally unique ID; an ID for an object which
        #        may be on a redirected or meta server.  Type as yet undecided.
        banana.Banana.connectionMade(self)
        self.sendCall("version", self.version)
        self.currentRequestID = 0
        self.currentLocalID = 0
        # Dictionary mapping LUIDs to local objects.
        self.localObjects = {}
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
        security = jelly.SecurityOptions()
        self.remoteSecurity = self.localSecurity = security
        security.allowBasicTypes()
        security.allowTypes("copy", "cache", "cached", "local", "remote", "lcache")
        self.jellier = None
        self.unjellier = None
        self.myServices = {}
        for perspective, username, password, referenced, callback, errback in self.expq:
            self.requestPerspective(perspective, username, password, referenced, callback, errback)

    def connectionFailed(self):
        """The connection failed; bail on any awaiting perspective requests.
        """
        for perspective, username, password, referenced, callback, errback in self.expq:
            try:
                errback()
            except:
                traceback.print_exc(file=log.logfile)

    def connectionLost(self):
        """The connection was lost.
        """
        self.disconnected = 1
        # nuke potential circular references.
        for perspective, client in self.perspectives.values():
            try:
                perspective.detached(client)
            except:
                log.msg("Exception in perspective detach ignored:")
                traceback.print_exc(file=log.logfile)
        self.perspectives = None
        self.localObjects = None
        self.luids = None
        for callback, errback in self.waitingForAnswers.values():
            try:
                errback(PB_CONNECTION_LOST)
            except:
                traceback.print_exc(file=log.logfile)
        for callback, errback in self.awaitingPerspectives.items():
            try:
                errback()
            except:
                traceback.print_exc(file=log.logfile)
        for notifier in self.disconnects:
            try:
                notifier()
            except:
                traceback.print_exc(file=log.logfile)
        self.disconnects = None
        self.waitingForAnswers = None
        self.awaitingPerspectives = None
        self.localSecurity = None
        self.remoteSecurity = None
        self.remotelyCachedObjects = None
        self.remotelyCachedLUIDs = None
        self.locallyCachedObjects = None

    def notifyOnDisconnect(self, notifier):
        self.disconnects.append(notifier)
        
    def localObjectForID(self, luid):
        """Get a local object for a locally unique ID.

        I will return an object previously stored with self.registerReference,
        or None if 
        """
        lob = self.localObjects.get(luid)
        if lob is None:
            return
        return lob.object

    def registerReference(self, object):
        """Get an ID for a local object.

        Store a persistent reference to a local object and map its id() to a
        generated, session-unique ID and return that ID.
        """
        assert object is not None
        puid = object.processUniqueID()
        luid = self.luids.get(puid)
        if luid is None:
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

        Note that this does not check the validity of the name, only creates a
        translucent reference for it.  In order to check the validity of an
        object, you can use the special message '__ping__'.
        
        object.__ping__() will always be answered with a 1 or 0 (never an
        error) depending on whether the peer knows about the object or not.
        """
        return Reference(None, self, name, 0)

    def cachedRemotelyAs(self, instance):
        """Returns an ID that says what this instance is cached as remotely, or None if it's not.
        """
        puid = instance.processUniqueID()
        luid = self.remotelyCachedLUIDs.get(puid)
        if luid is not None:
            self.remotelyCachedObjects[luid].incref()
        return luid
    
    def remotelyCachedForLUID(self, luid):
        """Returns an instance which is cached remotely, with this LUID.
        """
        return self.remotelyCachedObjects[luid].object

    def cacheRemotely(self, instance):
        """
        """
        puid = instance.processUniqueID()
        luid = self.newLocalID()
        self.remotelyCachedLUIDs[puid] = luid
        # This table may not be necessary -- for now, it's to make sure that no
        # monkey business happens with id(instance)
        self.remotelyCachedObjects[luid] = Local(instance)
        return luid

    def cacheLocally(self, cid, instance):
        """(internal)
        Store a non-filled-out cached instance locally.
        """
        self.locallyCachedObjects[cid] = instance

    def cachedLocallyAs(self, cid):
        instance = self.locallyCachedObjects[cid]
        return instance

    def getPerspective(self):
        return self.perspective

    def jelly(self, object):
        return self.jellier.jelly(object)

    def serialize(self, object, perspective=None, method=None, args=None, kw=None):
        """Jelly an object according to the remote security rules for this broker.
        """
        self.jellier = _NetJellier(self)
        self.perspective = perspective
        self.jellyMethod = method
        self.jellyArgs = args
        self.jellyKw = kw
        try:
            return self.jellier.jelly(object)
        finally:
            self.jellier = None
            self.perspective = None
            self.jellyMethod = None
            self.jellyArgs = None
            self.jellyKw = None

    def unserialize(self, sexp, perspective = None):
        """Unjelly an sexp according to the local security rules for this broker.
        """
        self.perspective = perspective
        self.unjellier = _NetUnjellier(self)
        try:
            return self.unjellier.unjelly(sexp)
        finally:
            self.perspective = None
            self.unjellier = None

    def _gotPerspective(self, perspective, isPerspective, *args):
        """(internal)
        """
        it = self.awaitingPerspectives[perspective][not isPerspective]
        del self.awaitingPerspectives[perspective]
        apply(it, args)

    def proto_perspective(self, perspective):
        """Received when a perspective authenticates correctly.
        """
        self._gotPerspective(perspective, 1, self.remoteForName(perspective))

    def proto_inperspective(self, perspective):
        """Received when a perspective authenticates incorrectly.
        """
        self._gotPerspective(perspective, 0)


    def requestPerspective(self, perspective, username, password, referenced=None, callback=noOperation, errback=printTraceback):
        """
        Request a perspective from this broker, and give a callback when it is or is not available.

        Arguments:

          * perspective: this is the name of the perspective broker service to
            request.

          * username: this is the username you wish to authenticate with.

          * password: this is the password you wish to authenticate with.  pass
            it in plaintext, it will be hashed using a challenge-response
            authentication handshake automatically.

          * referenced: this is pb.Referenced instance which represents the
            "client" to the remote side.  This argument may not be optional
            depending on the sort of service you are authenticating to.

          * callback: a callback which will be made (with a reference to the
            resulting perspective as the argument) if and when the
            authentication succeeds.

          * errback: a callback which will be made (with an error message as
            the argument) if and when the authentication fails.

        """
        if self.connected:
            if referenced == None:
                num = -1
            else:
                num = self.registerReference(referenced)
            self.sendCall("login", perspective, username, num)
            self.awaitingPerspectives[perspective] = callback, errback
            self.password = password
        else:
            self.expq.append((perspective, username, password, referenced, callback, errback))

    def proto_challenge(self, challenge):
        """Use authenticator.respond to respond to the server's challenge.
        """
        self.sendCall("password", authenticator.respond(challenge, self.password))

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

    def sendMessage(self, perspective, objectID, message, args, kw, callback, errback):
        
        """(internal) Send a message to a remote object.
        
        Arguments:

          * perspective: a perspective to serialize with/for.

          * objectID: an ID which will map to a remote object.

          * message: a string which names the message to be sent.

          * args: a tuple or list of arguments to be applied

          * kw: a dict of keyword arguments

          * callback: a callback to be made when this request is answered with
            a return value.

          * errback: a callback to be made when this request is answered with
            an exception.
        """
        self._sendMessage('',perspective, objectID, message, args, kw, callback, errback)

    def sendCacheMessage(self, cacheID, message, perspective, args, kw, callback, errback):
        """(internal) Similiar to sendMessage, but for cached.
        """
        self._sendMessage('cache',perspective, cacheID, message, args, kw, callback, errback)
    
    def _sendMessage(self, prefix, perspective, objectID, message, args, kw, callback, errback):
        if self.disconnected:
            raise ProtocolError("Calling Stale Broker")
        netArgs = self.serialize(args, perspective=perspective, method=message)
        netKw = self.serialize(kw, perspective=perspective, method=message)
        requestID = self.newRequestID()
        if (callback is None) and (errback is None):
            answerRequired = 0
        else:
            answerRequired = 1
            if callback is None:
                callback = noOperation
            if errback is None:
                errback = printTraceback
            self.waitingForAnswers[requestID] = callback, errback
        self.sendCall(prefix+"message", requestID, objectID, message, answerRequired, netArgs, netKw)

    def proto_message(self, requestID, objectID, message, answerRequired, netArgs, netKw):
        """Received a message-send.

        Look up message based on object, unserialize the arguments, and invoke
        it with args, and send an 'answer' or 'error' response.
        """
        try:
            object = self.localObjectForID(objectID)
            # Special message to check for validity of object-ID.
            if message == '__ping__':
                result = (object is not None)
            else:
                netResult = object.remoteMessageReceived(self, message,
                                                         netArgs, netKw)
        except Error, e:
            if answerRequired:
                self.sendError(requestID, str(e))
        except:
            io = cStringIO.StringIO()
            traceback.print_exc(file=io)
            if answerRequired:
                self.sendError(requestID, io.getvalue())
            else:
                log.msg("Client Ignored PB Traceback:")
                log.msg(io.getvalue())
        else:
            if answerRequired:
                self.sendAnswer(requestID, netResult)


    def proto_cachemessage(self, requestID, cacheID, message, answerRequired, netArgs, netKw):
        """Received a message-send to a Cached instance on the other side -- this needs to go to my Cache.

        Look up message based on a locally cached object, unserialize the
        arguments, and invoke it with args, and send an 'answer' or 'error'
        response.
        """
        try:
            object = self.cachedLocallyAs(cacheID)
            args = self.unserialize(netArgs)
            kw = self.unserialize(netKw)
            netResult = object.remoteMessageReceived(self, message, args, kw)
        except Error, e:
            if answerRequired:
                self.sendError(requestID, str(e))
        except:
            io = cStringIO.StringIO()
            traceback.print_exc(file=io)
            if answerRequired:
                self.sendError(requestID, io.getvalue())
            else:
                log.msg("Client Ignored PB Traceback:")
                log.msg(io.getvalue())
        else:
            if answerRequired:
                self.sendAnswer(requestID, netResult)

    def sendAnswer(self, requestID, netResult):
        """(internal) Send an answer to a previously sent message.
        """
        self.sendCall("answer", requestID, netResult)


    def proto_answer(self, requestID, netResult):
        """(internal) Got an answer to a previously sent message.

        Look up the appropriate callback and call it.
        """
        callback, errback = self.waitingForAnswers[requestID]
        del self.waitingForAnswers[requestID]
        result = self.unserialize(netResult)
        # XXX should this exception be caught?
        callback(result)


    def sendError(self, requestID, descriptiveString):
        """(internal) Send an error for a previously sent message.
        """
        self.sendCall("error", requestID, descriptiveString)


    def proto_error(self, requestID, descriptiveString):
        """(internal) Deal with an error.
        """
        callback, errback = self.waitingForAnswers[requestID]
        del self.waitingForAnswers[requestID]
        errback(descriptiveString)

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
        if self.localObjects[objectID].decref() == 0:
            puid = self.localObjects[objectID].object.processUniqueID()
            del self.luids[puid]
            del self.localObjects[objectID]

    def proto_decache(self, objectID):
        """(internal) Decrement the reference count of a cached object.

        If the reference count is zero, free the reference, then send an
        'uncached' directive.
        """
        if self.remotelyCachedObjects[objectID].decref() == 0:
            puid = self.remotelyCachedObjects[objectID].object.processUniqueID()
            del self.remotelyCachedLUIDs[puid]
            del self.remotelyCachedObjects[objectID]

    def proto_uncache(self, objectID):
        """(internal) Tell the client it is now OK to uncache an object.
        """
        del self.locallyCachedObjects[objectID]

class BrokerFactory(protocol.Factory):
    """I am a server for object brokerage.
    """
    
    def __init__(self):
        """Initialize me.
        """
        self.services = {}

    def addService(self, tag, service):
        """Add a service to me.
        """
        self.services[tag] = service

    def getService(self, tag):
        return self.services[tag]

    def buildProtocol(self, addr):
        """Return a Broker attached to me (as the service provider).
        """
        proto = Broker()
        proto.serverServices = self.services
        return proto


