
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
import new

# Twisted Imports
from twisted.python import log, defer, failure
from twisted.protocols import protocol
from twisted.internet import passport, tcp
from twisted.persisted import styles
from twisted.manhole import coil

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


class Serializable:
    """(internal) An object that can be passed remotely.

    This is a style of object which can be serialized by Perspective
    Broker.  Objects which wish to be referenceable or copied remotely
    have to subclass Serializable.  However, clients of Perspective
    Broker will probably not want to directly subclass Serializable; the
    Flavors of transferable objects are listed below.

    What it means to be \"Serializable\" is that an object can be
    passed to or returned from a remote method.  Certain basic types
    (dictionaries, lists, tuples, numbers, strings) are serializable by
    default; however, classes need to choose a specific serialization
    style: Referenceable, Viewable, Copyable or Cacheable.

    You may also pass [lists, dictionaries, tuples] of Serializable
    instances to or return them from remote methods, as many levels deep
    as you like.
    """

    def remoteSerialize(self, broker):
        """Return a list of strings & numbers which represents this object remotely.
        """

        raise NotImplementedError()

    def processUniqueID(self):
        """Return an ID which uniquely represents this object for this process.

        By default, this uses the 'id' builtin, but can be overridden to
        indicate that two values are identity-equivalent (such as proxies
        for the same object).
        """

        return id(self)

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

class Perspective(passport.Perspective):
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
            print ("%s didn't accept %s and %s" % (method, args, kw))
            raise
        return broker.serialize(state, self, method, args, kw)


class Service(passport.Service):
    """A service for Perspective Broker.

    On this Service, the result of a perspective request must be a
    pb.Perspective rather than a passport.Perspective.
    """

class Referenceable(Serializable):
    perspective = None
    """I am an object sent remotely as a direct reference.

    When one of my subclasses is sent as an argument to or returned
    from a remote method call, I will be serialized by default as a
    direct reference.

    This means that the peer will be able to call methods on me;
    a method call xxx() from my peer will be resolved to methods
    of the name remote_xxx.
    """

    def remoteMessageReceived(self, broker, message, args, kw):
        """A remote message has been received.  Dispatch it appropriately.

        The default implementation is to dispatch to a method called
        'remote_messagename' and call it with the same arguments.
        """
        args = broker.unserialize(args)
        kw = broker.unserialize(kw)
        method = getattr(self, "remote_%s" % message)
        try:
            state = apply(method, args, kw)
        except TypeError:
            print ("%s didn't accept %s and %s" % (method, args, kw))
            raise
        return broker.serialize(state, self.perspective)

    def remoteSerialize(self, broker):
        """(internal)

        Return a tuple which will be used as the s-expression to
        serialize this to a peer.
        """

        return remote_atom, broker.registerReference(self)


class Root(Referenceable):
    """I provide a root object to Brokers for a BrokerFactory.

    When a BrokerFactory produces a Broker, it supplies that Broker
    with an object named "root".  That object is obtained by calling
    my rootObject method.

    See also: getObjectAt
    """

    def rootObject(self, broker):
        """A BrokerFactory is requesting to publish me as a root object.

        When a BrokerFactory is sending me as the root object, this
        method will be invoked to allow per-broker versions of an
        object.  By default I return myself.
        """
        return self


class AsReferenceable(Referenceable):
    """AsReferenceable: a reference directed towards another object.
    """

    def __init__(self, object, messageType="remote"):
        """Initialize me with an object.
        """
        self.remoteMessageReceived = getattr(object, messageType + "MessageReceived")

class ViewPoint(Referenceable):
    """I act as an indirect reference to an object accessed through a Perspective.

    Simply put, I combine an object with a perspective so that when a
    peer calls methods on the object I refer to, the method will be
    invoked with that perspective as a first argument, so that it can
    know who is calling it.

    While Viewable objects will be converted to ViewPoints by default
    when they are returned from or sent as arguments to a remote
    method, any object may be manually proxied as well. (XXX: Now that
    this class is no longer named Proxy, this is the only occourance
    of the term 'proxied' in this docstring, and may be unclear.)

    This can be useful when dealing with Perspectives, Copyables,
    and Cacheables.  It is legal to implement a method as such on
    a perspective::

     | def perspective_getViewPointForOther(self, name):
     |     defr = self.service.getPerspectiveRequest(name)
     |     defr.addCallbacks(lambda x, self=self: ViewPoint(self, x), log.msg)
     |     return defr

    This will allow you to have references to Perspective objects in two
    different ways.  One is through the initial 'attach' call -- each
    peer will have a RemoteReference to their perspective directly.  The
    other is through this method; each peer can get a RemoteReference to
    all other perspectives in the service; but that RemoteReference will
    be to a ViewPoint, not directly to the object.

    The practical offshoot of this is that you can implement 2 varieties
    of remotely callable methods on this Perspective; view_xxx and
    perspective_xxx. view_xxx methods will follow the rules for
    ViewPoint methods (see ViewPoint.remoteMessageReceived), and
    perspective_xxx methods will follow the rules for Perspective
    methods.
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
        'view_messagename' to my Object and call it on my object with
        the same arguments, modified by inserting my Perspective as
        the first argument.
        """
        args = broker.unserialize(args, self.perspective)
        kw = broker.unserialize(kw, self.perspective)
        method = getattr(self.object, "view_%s" % message)
        try:
            state = apply(method, (self.perspective,)+args, kw)
        except TypeError:
            print ("%s didn't accept %s and %s" % (method, args, kw))
            raise
        rv = broker.serialize(state, self.perspective, method, args, kw)
        return rv


class Viewable(Serializable):
    """I will be converted to a ViewPoint when passed to or returned from a remote method.

    The beginning of a peer's interaction with a PB Service is always
    through a perspective.  However, if a perspective_xxx method returns
    a Viewable, it will be serialized to the peer as a response to that
    method.
    """

    def remoteSerialize(self, broker):
        """Serialize a ViewPoint for me and the perspective of the given broker.
        """
        return ViewPoint(broker.getPerspective(), self).remoteSerialize(broker)



class Copyable(Serializable):
    """Subclass me to get copied each time you are returned from or passed to a remote method.

    When I am returned from or passed to a remote method call, I will be
    converted into data via a set of callbacks (see my methods for more
    info).  That data will then be serialized using Jelly, and sent to
    the peer.

    The peer will then look up the type to represent this with; see
    RemoteCopy for details.
    """

    def getStateToCopy(self):
        """Gather state to send when I am serialized for a peer.

        I will default to returning self.__dict__.  Override this to
        customize this behavior.
        """

        return self.__dict__

    def getStateToCopyFor(self, perspective):
        """Gather state to send when I am serialized for a particular perspective.

        I will default to calling getStateToCopy.  Override this to
        customize this behavior.
        """

        return self.getStateToCopy()

    def getTypeToCopy(self):
        """Determine what type tag to send for me.

        By default, send the string representation of my class
        (package.module.Class); normally this is adequate, but
        you may override this to change it.
        """

        return str(self.__class__)

    def getTypeToCopyFor(self, perspective):
        """Determine what type tag to send for me.

        By default, defer to self.getTypeToCopy() normally this is
        adequate, but you may override this to change it.
        """

        return self.getTypeToCopy()

    def remoteSerialize(self, broker):
        """Assemble type tag and state to copy for this broker.

        This will call getTypeToCopyFor and getStateToCopy, and
        return an appropriate s-expression to represent me.  Do
        not override this method.
        """

        p = broker.getPerspective()
        return (copy_atom, self.getTypeToCopyFor(p),
                broker.jelly(self.getStateToCopyFor(p)))


class RemoteCopy:
    """I am a remote copy of a Copyable object.

    When the state from a Copyable object is received, an instance will
    be created based on the copy tags table (see setCopierForClass) and
    sent the setCopyableState message.  I provide a reasonable default
    implementation of that message; subclass me if you wish to serve as
    a copier for remote data.

    NOTE: copiers are invoked with no arguments.  Do not implement a
    constructor which requires args in a subclass of RemoteCopy!
    """

    def postUnjelly(self):
        """I will be invoked after the data I was sent with has been fully unjellied.
        """

    def setCopyableState(self, state):
        """I will be invoked with the state to copy locally.

        'state' is the data returned from the remote object's
        'getStateToCopyFor' method, which will often be the remote
        object's dictionary (or a filtered approximation of it depending
        on my peer's perspective).
        """

        self.__dict__ = state

class RemoteCache(RemoteCopy, Serializable):
    """A cache is a local representation of a remote Cacheable object.

    This represents the last known state of this object.  It may
    also have methods invoked on it -- in order to update caches,
    the cached class generates a RemoteReference to this object as
    it is originally sent.

    Much like copy, I will be invoked with no arguments.  Do not
    implement a constructor that requires arguments in one of my
    subclasses.
    """

    def remoteMessageReceived(self, broker, message, args, kw):
        """A remote message has been received.  Dispatch it appropriately.

        The default implementation is to dispatch to a method called
        'observe_messagename' and call it on my  with the same arguments.
        """

        args = broker.unserialize(args)
        kw = broker.unserialize(kw)
        method = getattr(self, "observe_%s" % message)
        try:
            state = apply(method, args, kw)
        except TypeError:
            print ("%s didn't accept %s and %s" % (method, args, kw))
            raise
        return broker.serialize(state, None, method, args, kw)

    def remoteSerialize(self, broker):
        """serialize me (only for the broker I'm for) as the original cached reference
        """

        assert broker is self.broker, "You cannot exchange cached proxies between brokers."
        print 'local cache',self.luid
        return 'lcache', self.luid

    def __really_del__(self):
        """Final finalization call, made after all remote references have been lost.
        """

    def __cmp__(self, other):
        """Compare me [to another RemoteCacheProxy.
        """
        if isinstance(other, self.__class__):
            return cmp(id(self.__dict__), id(other.__dict__))
        else:
            return cmp(id(self.__dict__), other)

    def __hash__(self):
        """Hash me.
        """
        return id(self.__dict__)

    def __del__(self):
        """Do distributed reference counting on finalize.
        """
        try:
            # print 'decache: %s %d' % (self, self.luid)
            self.broker.decCacheRef(self.luid)
        except:
            traceback.print_exc(file=log.logfile)



copyTags = {}

def setCopierForClass(classname, copier):
    """Set which local class will represent a remote type.

    If you have written a Copyable class that you expect your client to be
    receiving, write a local "copy" class to represent it, then call::

      pb.setCopierForClass('module.package.Class', MyCopier).

    Call this at the module level immediately after its class
    definition. MyCopier should be a subclass of RemoteCopy.

    The classname may be a special tag returned by
    'Copyable.getTypeToCopyFor' rather than an actual classname.

    This call is also for cached classes, since there will be no
    overlap.  The rules are the same.
    """

    global copyTags
    copyTags[classname] = copier

def setCopierForClassTree(module, baseClass, prefix=None):
    """Set all classes in a module derived from base_class as copiers for a corresponding remote class.

    When you have a heirarchy of Copyable (or Cacheable) classes on
    one side, and a mirror structure of Copied (or RemoteCache)
    classes on the other, use this to setCopierForClass all your
    Copieds for the Copyables.

    Each copyTag (the \"classname\" argument to getTypeToCopyFor, and
    what the Copyable's getTypeToCopyFor returns) is formed from
    adding a prefix to the Copied's class name.  The prefix defaults
    to module.__name__.  If you wish the copy tag to consist of solely
    the classname, pass the empty string \'\'.

    module -- a module object from which to pull the Copied classes.
              (passing sys.modules[__name__] might be useful)

    baseClass -- the base class from which all your Copied classes derive.

    prefix -- the string prefixed to classnames to form the copyTags.
    """
    if prefix is None:
        prefix = module.__name__

    if prefix:
        prefix = "%s." % prefix

    for i in dir(module):
        i_ = getattr(module, i)
        if type(i_) == types.ClassType:
            if issubclass(i_, baseClass):
                setCopierForClass('%s%s' % (prefix, i), i_)


class RemoteCacheMethod:
    """A method on a reference to a RemoteCache.
    """

    def __init__(self, name, broker, cached, perspective):
        """(internal) initialize.
        """
        self.name = name
        self.broker = broker
        self.perspective = perspective
        self.cached = cached

    def __cmp__(self, other):
        return cmp((self.name, self.broker, self.perspective, self.cached), other)
    
    def __hash__(self):
        return hash((self.name, self.broker, self.perspective, self.cached))
    
    def __call__(self, *args, **kw):
        """(internal) action method.
        """
        cacheID = self.broker.cachedRemotelyAs(self.cached)
        if cacheID is None:
            raise ProtocolError("You can't call a cached method when the object hasn't been given to the peer yet.")
        return self.broker._sendMessage('cache', self.perspective, cacheID, self.name, args, kw)

class RemoteCacheObserver:
    """I am a reverse-reference to the peer's RemoteCache.

    I am generated automatically when a cache is serialized.  I
    represent a reference to the client's RemoteCache object that
    will represent a particular Cacheable; I am the additional
    object passed to getStateToCacheAndObserveFor.
    """

    def __init__(self, broker, cached, perspective):
        """Initialize me pointing at a client side cache for a particular broker/perspective.
        """

        self.broker = broker
        self.cached = cached
        self.perspective = perspective

    def __repr__(self):
        return "<RemoteCacheObserver(%s, %s, %s) at %s>" % (
            self.broker, self.cached, self.perspective, id(self))

    def __hash__(self):
        """generate a hash unique to all RemoteCacheObservers for this broker/perspective/cached triplet
        """

        return (  (hash(self.broker) % 2**10)
                + (hash(self.perspective) % 2**10)
                + (hash(self.cached) % 2**10))

    def __cmp__(self, other):
        """compare me to another RemoteCacheObserver
        """

        return cmp((self.broker, self.perspective, self.cached), other)

    def __getattr__(self, key):
        """Create a RemoteCacheMethod.
        """

        if key[:2]=='__' and key[-2:]=='__':
            raise AttributeError(key)
        return RemoteCacheMethod(key, self.broker, self.cached, self.perspective)


class Cacheable(Copyable):
    """A cached instance.

    This means that it's copied; but there is some logic to make sure
    that it's only copied once.  Additionally, when state is retrieved,
    it is passed a "proto-reference" to the state as it will exist on
    the client.

    XXX: The documentation for this class needs work, but it's the most
    complex part of PB and it is inherently difficult to explain.
    """

    def getStateToCacheAndObserveFor(self, perspective, observer):
        """Get state to cache on the client and client-cache reference to observe locally.

        This is similiar to getStateToCopyFor, but it additionally
        passes in a reference to the client-side RemoteCache instance
        that will be created when it is unserialized.  This allows
        Cacheable instances to keep their RemoteCaches up to date when
        they change, such that no changes can occurr between the point
        at which the state is initially copied and the client receives
        it that are not propogated.
        """

        return self.getStateToCopyFor(perspective)

    def remoteSerialize(self, broker):
        """Return an appropriate tuple to serialize me.

        Depending on whether this broker has cached me or not, this may
        return either a full state or a reference to an existing cache.
        """

        luid = broker.cachedRemotelyAs(self)
        if luid is None:
            luid = broker.cacheRemotely(self)
            p = broker.getPerspective()
            type_ = self.getTypeToCopyFor(p)
            observer = RemoteCacheObserver(broker, self, p)
            state = self.getStateToCacheAndObserveFor(p, observer)
            jstate = broker.jelly(state)
            return cache_atom, luid, type_, jstate
        else:
            return cached_atom, luid

class RemoteReference(Serializable, styles.Ephemeral):
    """This is a translucent reference to a remote object.

    I may be a reference to a ViewPoint, a Referenceable, or
    a Perspective.  From the client's perspective, it is not
    possible to tell which except by convention.

    I am a "translucent" reference because although no additional
    bookkeeping overhead is given to the application programmer for
    manipulating a reference, return values are asynchronous.

    All attributes besides '__double_underscored__' attributes are RemoteMethod
    instances; these act like methods which return Deferreds.
    
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

    def remoteSerialize(self, broker):
        """If I am being sent back to where I came from, serialize as a local backreference.
        """

        assert self.broker == broker, "Can't send references to brokers other than their own."
        return local_atom, self.luid

    def __getattr__(self, key):
        """Get a RemoteMethod for this key.
        """

        if key[:2]=='__' and key[-2:]=='__':
            raise AttributeError(key)
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

class _RemoteCacheDummy:
    """Ignore.
    """

class _NetUnjellier(jelly._Unjellier):
    """An unjellier for PB.

    This unserializes the various Serializable flavours in PB.
    """

    def __init__(self, broker):
        jelly._Unjellier.__init__(self, broker.localSecurity, None)
        self.broker = broker

    def _unjelly_copy(self, rest):
        """Unserialize a Copyable.
        """
        global copyTags
        inst = copyTags[rest[0]]()
        inst.setCopyableState(self._unjelly(rest[1]))
        self.postCallbacks.append(inst.postUnjelly)
        return inst

    def _unjelly_cache(self, rest):
        global copyTags
        luid = rest[0]
        cNotProxy = _RemoteCacheDummy() #copyTags[rest[1]]()
        cNotProxy.broker = self.broker
        cNotProxy.luid = luid
        cNotProxy.__class__ = copyTags[rest[1]]
        cProxy = _RemoteCacheDummy() # (self.broker, cNotProxy, luid)
        cProxy.__class__ = cNotProxy.__class__
        cProxy.__dict__ = cNotProxy.__dict__
        init = getattr(cProxy, "__init__", None)
        if init:
            init()
        cProxy.setCopyableState(self._unjelly(rest[2]))
        # Might have changed due to setCopyableState method; we'll assume that
        # it's bad form to do so afterwards.
        cNotProxy.__dict__ = cProxy.__dict__
        # chomp, chomp -- some existing code uses "self.__dict__ =", some uses
        # "__dict__.update".  This is here in order to handle both cases.
        cNotProxy.broker = self.broker
        cNotProxy.luid = luid
        # Must be done in this order otherwise __hash__ isn't right!
        self.broker.cacheLocally(luid, cNotProxy)
        self.postCallbacks.append(cProxy.postUnjelly)
        return cProxy

    def _unjelly_cached(self, rest):
        luid = rest[0]
        cNotProxy = self.broker.cachedLocallyAs(luid)
        cProxy = _RemoteCacheDummy()
        cProxy.__class__ = cNotProxy.__class__
        cProxy.__dict__ = cNotProxy.__dict__
        return cProxy

    def _unjelly_lcache(self, rest):
        luid = rest[0]
        obj = self.broker.remotelyCachedForLUID(luid)
        return obj

    def _unjelly_remote(self, rest):
        obj = RemoteReference(self.broker.getPerspective(), self.broker, rest[0], 1)
        return obj

    def _unjelly_local(self, rest):
        obj = self.broker.localObjectForID(rest[0])
        return obj


class Broker(banana.Banana):
    """I am a broker for objects.
    """

    version = 4
    username = None

    def __init__(self):
        banana.Banana.__init__(self)
        self.disconnected = 0
        self.disconnects = []
        self.failures = []
        self.connects = []
        self.localObjects = {}

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
        log.msg("Didn't understand command:", repr(command))

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
        security = jelly.SecurityOptions()
        self.remoteSecurity = self.localSecurity = security
        security.allowBasicTypes()
        security.allowTypes("copy", "cache", "cached", "local", "remote", "lcache")
        self.jellier = None
        self.unjellier = None
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

    def connectionLost(self):
        """The connection was lost.
        """

        self.disconnected = 1
        # nuke potential circular references.
        self.luids = None
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

    def registerReference(self, object):
        """Get an ID for a local object.

        Store a persistent reference to a local object and map its id()
        to a generated, session-unique ID and return that ID.
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

        Note that this does not check the validity of the name, only
        creates a translucent reference for it.  In order to check
        the validity of an object, you can use the special message
        '__ping__'.

        object.__ping__() will always be answered with a 1 or 0 (never
        an error) depending on whether the peer knows about the object
        or not.
        """
        return RemoteReference(None, self, name, 0)

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
        XXX"""
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

        if isinstance(object, defer.Deferred):
            object.addCallbacks(self.serialize, lambda x: x,
                                callbackKeywords={
                'perspective': perspective,
                'method': method,
                'args': args,
                'kw': kw
                })
            return object
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
        netArgs = self.serialize(args, perspective=perspective, method=message)
        netKw = self.serialize(kw, perspective=perspective, method=message)
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
            # Special message to check for validity of object-ID.
            if message == '__ping__':
                result = (object is not None)
            else:
                netResult = object.remoteMessageReceived(self, message, netArgs, netKw)
        except Error, e:
            if answerRequired:
                self._sendError(str(e), requestID)
        except:
            if answerRequired:
                io = cStringIO.StringIO()
                failure.Failure().printBriefTraceback(file=io)
                self._sendError(io.getvalue(), requestID)
                log.msg("Client Received PB Traceback:")
            else:
                log.msg("Client Ignored PB Traceback:")
            log.deferr()
        else:
            if answerRequired:
                if isinstance(netResult, defer.Deferred):
                    args = (requestID,)
                    netResult.addCallbacks(self._sendAnswer, self._sendError,
                                           callbackArgs=args, errbackArgs=args)
                    # XXX Should this be done somewhere else?
                    netResult.arm()
                else:
                    self._sendAnswer(netResult, requestID)


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
        d.arm()
        d.errback(descriptiveString)

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
        # print 'decaching: %s #refs: %s' % (objectID, refs)
        if refs == 0:
            puid = self.remotelyCachedObjects[objectID].object.processUniqueID()
            del self.remotelyCachedLUIDs[puid]
            del self.remotelyCachedObjects[objectID]
            self.sendCall("uncache", objectID)

    def proto_uncache(self, objectID):
        """(internal) Tell the client it is now OK to uncache an object.
        """
        # print "uncaching %d" % objectID
        obj = self.locallyCachedObjects[objectID]
        def reallyDel(obj=obj):
            obj.__really_del__()
        obj.__del__ = reallyDel
        del self.locallyCachedObjects[objectID]

class BrokerFactory(protocol.Factory, styles.Versioned, coil.Configurable):
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
        proto = Broker()
        proto.factory = self
        proto.setNameForLocal("root",
                              self.objectToBroker.rootObject(proto))
        return proto

coil.registerClass(BrokerFactory)

### AUTH STUFF

class AuthRoot(Root):
    """I provide AuthServs as root objects to Brokers for a BrokerFactory.
    """

    def __init__(self, app):
        self.app = app

    def rootObject(self, broker):
        return AuthServ(self.app, broker)

class _Detacher:
    def __init__(self, perspective, remoteRef, identity):
        self.perspective = perspective
        self.remoteRef = remoteRef
        self.identity = identity

    def detach(self):
        self.perspective.detached(self.remoteRef, self.identity)

class IdentityWrapper(Referenceable):
    """I delegate most functionality to a passport.Identity.
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
        perspective = perspective.attached(remoteRef, self.identity)
        # Make sure that when connectionLost happens, this perspective
        # will be tracked in order that 'detached' will be called.
        self.broker.notifyOnDisconnect(_Detacher(perspective, remoteRef, self.identity).detach)
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
            if self.ident.verifyPassword(self.challenge, response):
                return IdentityWrapper(self.serv.broker, self.ident)


class AuthServ(Referenceable):
    """XXX

    See also: AuthRoot
    """

    def __init__(self, app, broker):
        self.app = app
        self.broker = broker

    def remote_username(self, username):
        defr = self.app.authorizer.getIdentityRequest(username)
        defr.addCallbacks(self.mkchallenge, self.mkchallenge)
        return defr

    def mkchallenge(self, ident):
        if type(ident) == types.StringType:
            # it's an error, so we must fail.
            challenge = passport.challenge()
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
            self.eb("connection lost")

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
    b = Broker()
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
        client -- XXX the "reference" argument to passport.Perspective.attached
        timeout -- see twisted.internet.tcp.Client
    """
    d = defer.Deferred()
    getObjectAt(host,port,timeout).addCallbacks(
        _connGotRoot, d.armAndErrback,
        callbackArgs=[d, client, serviceName, username, password, perspectiveName])
    return d

def _connGotRoot(root, d, client, serviceName,
                 username, password, perspectiveName):
    logIn(root, client, serviceName, username, password, perspectiveName).armAndChain(d)

def logIn(authServRef, client, service, username, password, perspectiveName=None):
    """I return a Deferred which will be called back with a Perspective.
    """
    d = defer.Deferred()
    authServRef.username(username).addCallbacks(_cbLogInRespond, d.armAndErrback,
                                                callbackArgs=(d, client, service, password, perspectiveName or userName))
    return d

def _cbLogInRespond((challenge, challenger), d, client, service, password, perspectiveName):
    challenger.respond(
        passport.respond(challenge, password)).addCallbacks(
        _cbLogInResponded, d.armAndErrback,
        callbackArgs=(d, client, service, perspectiveName))

def _cbLogInResponded(identity, d, client, serviceName, perspectiveName):
    if identity:
        identity.attach(serviceName, perspectiveName, client).armAndChain(d)
    else:
        d.armAndErrback("invalid username or password")
