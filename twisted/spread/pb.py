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


from twisted.protocols import protocol

class ProtocolError(Exception):
    """
    This error is raised when an invalid protocol statement is received.
    """

class Serializable:
    """
    This is a style of object which can be serialized by Perspective Broker.
    Objects which wish to be referenced or copied remotely have to subclass
    Serializable.  However, clients of Perspective Broker will probably not
    want to directly subclass Serializable; the Flavors of transferable objects
    are listed below.
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

    I want to it to be *possible* to be able to call remote methods on this.  I
    also want it to *normally* be serialized as a Proxy, becuase if users want
    references to each other they've got to be able to see each others'
    perspective.  (I can *see* your perspective, but I can't see *from* your
    perspective.)

    So why does it have to be referenced?  It just has to implement
    remoteMessageReceived.  In fact, it should not implement remote_; it should
    implement perspective_ or somesuch.  Normally, they're not serializable
    anwyay!
    """

    def remoteMessageReceived(self, broker, message, args, kw):
        args = broker.unserialize(args, self)
        kw = broker.unserialize(kw, self)
        method = getattr(self, "perspective_%s" % message)
        state = apply(method, args, kw)
        return broker.serialize(state, self, method, args, kw)

    def attached(self, broker):
        """Called when a broker is attached to this perspective.
        """

    def detached(self, broker):
        """Called when a broker is detached from this perspective.
        """




class Service(authenticator.Authenticator):
    """A service for Perspective Broker.
    """

    def getPerspectiveNamed(self, name):
        """Return a perspective that represents a user for this service.

        Other services should really, really subclass this method.
        """
        return Perspective()


class Referenced(Serializable):
    perspective = None
    """Referenced objects are sent remotely as direct references.
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
        return remote_atom, broker.registerReference(self)

class Proxy(Referenced):
    """A class which operates as the remote arbiter.

    Subclass this to implement a remote access interface for objects which
    shouldn't be accessed directly, but instead should be accessed through a
    'user'.
    """
    
    def __init__(self, perspective, object):
        self.perspective = perspective
        self.object = object

    def processUniqueID(self):
        return (id(self.perspective), id(self.object))

    def remoteSerialize(self, broker):
        """(internal) Serialize remotely.
        """
        # waste not, want not
        return remote_atom, broker.registerReference(self)

    def remoteMessageReceived(self, broker, message, args, kw):
        """A remote message has been received.  Dispatch it appropriately.

        The default implementation is to dispatch to a method called
        'proxy_messagename' and call it on my  with the same arguments.
        """
        args = broker.unserialize(args, self.perspective)
        kw = broker.unserialize(kw, self.perspective)
        method = getattr(self.object, "proxy_%s" % message)
        state = apply(method, (self.perspective,)+args, kw)
        rv = broker.serialize(state, self.perspective, method, args, kw)
        return rv


class Proxied(Serializable):
    proxy = Proxy

    def remoteSerialize(self, broker):
        # getPerspective will have to return different values from different
        # threads, if this is ever to be made thread safe!
        return self.proxy(broker.getPerspective(), self).remoteSerialize(broker)



class Copied(Serializable):
    """A class which is serialized when seen remotely.
    """
    def getStateToCopy(self):
        return self.__dict__

    def getStateToCopyFor(self, perspective):
        return self.getStateToCopy()

    def getTypeToCopy(self):
        return str(self.__class__)

    def getTypeToCopyFor(self, perspective):
        return self.getTypeToCopy()

    def remoteSerialize(self, broker):
        p = broker.getPerspective()
        return (copy_atom, self.getTypeToCopyFor(p),
                broker.jelly(self.getStateToCopyFor(p)))


class Copy:
    def setCopiedState(self, state):
        self.__dict__ = state

class Cache(Copy):
    """It's like a copy, but way, *WAY* worse!
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
    global copyTags
    copyTags[classname] = copier


class CacheMethod:
    def __init__(self, name, broker, cached, perspective):
        self.name = name
        self.broker = broker
        self.perspective = perspective
        self.cached = cached

    def do(self, *args, **kw):
        self.cached.remoteCacheDo(self.broker, self.name, self.perspective, args, kw)
        

class CacheObserver:
    def __init__(self, broker, cached, perspective):
        self.broker = broker
        self.cached = cached
        self.perspective = perspective

    def __repr__(self):
        return "<CacheObserver(%s, %s, %s) at %s>" % (
            self.broker, self.cached, self.perspective, id(self))
    
    def __hash__(self):
        return (  (hash(self.broker) % 2**10)
                + (hash(self.perspective) % 2**10)
                + (hash(self.cached) % 2**10))
    
    def __cmp__(self, other):
        return cmp((self.broker, self.perspective, self.cached), other)
    
    def __getattr__(self, key):
        if key[:2]=='__' and key[-2:]=='__':
            raise AttributeError(key)
        return CacheMethod(key, self.broker, self.cached, self.perspective).do


class Cached(Copied):
    """A cached instance.

    This means that it's copied; but there is some logic to make sure that it's
    only copied once.
    """

    def getStateToCacheAndObserveFor(self, perspective, observer):
        """Look.  If you don't know, don't ask, okay?
        """
        return self.getStateToCopyFor(perspective)
    
    def remoteSerialize(self, broker):
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
        callback = noOperation
        errback = printTraceback
        if kw.has_key('pbcallback'):
            callback = kw['pbcallback']
            del kw['pbcallback']
        if kw.has_key('pberrback'):
            errback = kw['pberrback']
            del kw['pberrback']
        broker.sendCacheMessage(cacheID, methodName, perspective, args, kw, callback, errback)

class Reference(Serializable):
    """This is a translucent reference to a remote object.
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
        callback = noOperation
        errback = printTraceback
        if kw.has_key('pbcallback'):
            callback = kw['pbcallback']
            del kw['pbcallback']
        if kw.has_key('pberrback'):
            errback = kw['pberrback']
            del kw['pberrback']
        self.broker.sendMessage(self.perspective, self.luid,
                                key, args, kw,
                                callback, errback)

    def __cmp__(self,other):
        """Compare me.
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
        """Do distributed reference counting.
        """
        if self.doRefCount:
            self.broker.sendDecRef(self.luid)

class CacheProxy(Serializable):
    """A proxy for cached instances.

    This is an as-transparent-as-possible layer, since its really designed
    for reference counting.
    """
    __inited = 0
    def __init__(self, broker, instance, luid):
        self.__broker = broker
        self.__instance = instance
        self.__luid = luid
        self.__inited = 1

    def remoteSerialize(self, broker):
        assert broker is self.__broker, "You cannot exchange cached proxies between brokers."
        return 'lcache', self.__luid

    def __getattr__(self, name):
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
        return "CacheProxy(%s)" % repr(self.__instance)
    def __str__(self):
        return "CacheProxy(%s)" % str(self.__instance)

    def __setattr__(self, name, value):
        if self.__inited:
            setattr(self.__instance, name, value)
        else:
            self.__dict__[name] = value

    def __cmp__(self, other):
        if isinstance(other, CacheProxy):
            return cmp(self.__instance, other.__instance)
        else:
            return cmp(self.__instance, other)

    def __hash__(self):
        return hash(self.__instance)

    def __del__(self):
        try:
            self.__broker.decCacheRef(self.__luid)
        except:
            traceback.print_exc(file=log.logfile)


class Local:
    """A reference to a local object.
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
    def __init__(self, broker):
        jelly._Jellier.__init__(self, broker.localSecurity, None)
        self.broker = broker
        
    def _jelly_instance(self, instance):
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
    def __init__(self, broker):
        jelly._Unjellier.__init__(self, broker.localSecurity, None)
        self.broker = broker

    def _unjelly_copy(self, rest):
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
            # print "pb:",sexp
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


    def addPerspective(self, tag, perspective):
        """Add a perspective to this connection.
        """
        perspective.attached(self)
        self.perspectives[tag] = perspective
        self.setNameForLocal(tag, perspective)


    def getPerspective(self, tag):
        """Get a perspective for this tag.
        """
        return self.perspectives[tag]


    def sendCall(self, *exp):
        """Utility method to send an expression to the other side of the connection.
        """
        if self.connected:
            self.sendEncoded(exp)
        else:
            self.expq.append(exp)

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

    def proto_login(self, service, username):
        """Receive a login name, and respond with a challenge.

        This is the second step in the protocol, the first being version number
        checking.

        See the documentation for twisted.python.authenticator for more
        information on the challenge/response system that is used here.
        """
        self.username = username
        self.loginService = self.getService(service)
        self.loginTag = service
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
            self.addPerspective(self.loginTag, perspective)
            self.sendCall("perspective", self.loginTag)
            del self.username
            del self.challenge
            del self.loginTag
            del self.loginService
        except authenticator.Unauthorized:
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
        for xp in self.expq:
            self.sendEncoded(xp)

    def connectionFailed(self):
        """The connection failed; bail on any awaiting perspective requests.
        """
        for callback, errback in self.awaitingPerspectives.values():
            try:
                errback()
            except:
                traceback.print_exc(file=log.logfile)

    def connectionLost(self):
        """The connection was lost.
        """
        # nuke potential circular references.
        for perspective in self.perspectives.values():
            try:
                perspective.detached(self)
            except:
                log.msg( "Exception in perspective detach ignored:")
                traceback.print_exc(file=log.logfile)
        self.perspectives = None
        self.localObjects = None
        self.luids = None
        for callback, errback in self.waitingForAnswers.values():
            try:
                errback(PB_CONNECTION_LOST)
            except:
                traceback.print_exc(file=log.logfile)
        for notifier in self.disconnects:
            try:
                notifier()
            except:
                traceback.print_exc(file=log.logfile)
        self.disconnects = None
        self.waitingForAnswers = None
        self.localSecurity = None
        self.remoteSecurity = None
        self.remotelyCachedObjects = None
        self.remotelyCachedLUIDs = None
        self.locallyCachedObjects = None
        self.waitingForAnswers = None
        self.disconnected = 1

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

    def proto_inperspective(self, name):
        """Received when a perspective authenticates incorrectly.
        """
        self._gotPerspective(perspective, 0)


    def requestPerspective(self, perspective, username, password, callback=noOperation, errback=printTraceback):
        self.sendCall("login", perspective, username)
        self.awaitingPerspectives[perspective] = callback, errback
        self.password = password

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

    def sendMessage(self, perspective, objectID,
                    message, args, kw,
                    callback, errback):
        
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
        netArgs = self.serialize(args, perspective=perspective, method=message)
        netKw = self.serialize(kw, perspective=perspective, method=message)
        requestID = self.newRequestID()
        if self.disconnected:
            try:
                errback(PB_CONNECTION_LOST)
            except:
                traceback.print_exc(file=log.logfile)
        else:
            self.waitingForAnswers[requestID] = callback, errback
            self.sendCall("message", requestID, objectID, message, netArgs, netKw)

    def sendCacheMessage(self, cacheID, message, perspective, args, kw, callback, errback):
        """(internal) Similiar to sendMessage, but for cached.
        """
        netArgs = self.serialize(args, perspective = perspective, method = message)
        netKw = self.serialize(kw, perspective = perspective, method = message)
        requestID = self.newRequestID()
        if self.disconnected:
            try:
                errback(PB_CONNECTION_LOST)
            except:
                traceback.print_exc(file=log.logfile)
        else:
            self.waitingForAnswers[requestID] = callback, errback
            self.sendCall("cachemessage", requestID, cacheID, message, netArgs, netKw)

    def proto_message(self, requestID, objectID, message, netArgs, netKw):
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
        except:
            io = cStringIO.StringIO()
            traceback.print_exc(file=io)
            self.sendError(requestID, io.getvalue())
        else:
            self.sendAnswer(requestID, netResult)


    def proto_cachemessage(self, requestID, cacheID, message, netArgs, netKw):
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
        except:
            io = cStringIO.StringIO()
            traceback.print_exc(file=io)
            self.sendError(requestID, io.getvalue())
        else:
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


