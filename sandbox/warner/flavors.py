#! /usr/bin/python

import types

from zope.interface import interface
from zope.interface import implements, providedBy
from twisted.python import reflect
from twisted.python.components import registerAdapter
Interface = interface.Interface
from twisted.internet.defer import Deferred

import schema, slicer, tokens
from tokens import ISlicer, BananaError, Violation


class RemoteInterfaceClass(interface.InterfaceClass):
    """This metaclass lets RemoteInterfaces be a lot like Interfaces. The
    methods are parsed differently (PB needs more information from them than
    z.i extracts, and the methods can be specified with a RemoteMethodSchema
    directly).

    RemoteInterfaces can accept the following additional attribute:

     __remote_name__: can be set to a string to specify the globally-unique
                      name for this interface. If not set, defaults to the
                      fully qualified classname.

    RIFoo.names() returns the list of remote method names.

    RIFoo['bar'] is still used to get information about method 'bar', however
    it returns a RemoteMethodSchema instead of a z.i Method instance.
    
    """

    def __init__(self, iname, bases=(), attrs=None, __module__=None):
        if attrs is None:
            interface.InterfaceClass.__init__(self, iname, bases, attrs,
                                              __module__)
            return

        # parse (and remove) the attributes that make this a RemoteInterface
        try:
            rname, remote_attrs = self._parseRemoteInterface(iname, attrs)
        except:
            print "error parsing remote-interface attributes"
            raise

        # now let the normal InterfaceClass do its thing
        interface.InterfaceClass.__init__(self, iname, bases, attrs,
                                          __module__)

        # now add all the remote methods that InterfaceClass would have
        # complained about. This is really gross, and it really makes me
        # question why we're bothing to inherit from z.i.Interface at all. I
        # will probably stop doing that soon, and just have our own
        # meta-class, but I want to make sure you can still do
        # 'implements(RIFoo)' from within a class definition.

        a = getattr(self, "_InterfaceClass__attrs") # the ickiest part
        a.update(remote_attrs)
        self.__remote_name__ = rname

        # finally, auto-register the interface
        try:
            registerRemoteInterface(self, rname)
        except:
            print "error registering RemoteInterface '%s'" % rname
            raise

    def _parseRemoteInterface(self, iname, attrs):
        remote_attrs = {}

        remote_name = attrs.get("__remote_name__", iname)

        # and see if there is a __remote_name__ . We delete it because
        # InterfaceClass doesn't like arbitrary attributes
        if attrs.has_key("__remote_name__"):
            del attrs["__remote_name__"]

        # determine all remotely-callable methods
        names = [name for name in attrs.keys()
                 if ((type(attrs[name]) == types.FunctionType and
                      not name.startswith("_")) or
                     schema.IConstraint.providedBy(attrs[name]))]

        # turn them into constraints. Tag each of them with their name and
        # the RemoteInterface they came from.
        for name in names:
            m = attrs[name]
            if not schema.IConstraint.providedBy(m):
                m = schema.RemoteMethodSchema(method=m)
            m.name = name
            m.interface = self
            remote_attrs[name] = m
            # delete the methods, so zope's InterfaceClass doesn't see them.
            # Particularly necessary for things defined with IConstraints.
            del attrs[name]

        return remote_name, remote_attrs

RemoteInterface = RemoteInterfaceClass("RemoteInterface",
                                       __module__="pb.flavors")



def getRemoteInterfaces(obj):
    """Get a list of all RemoteInterfaces supported by the object."""
    interfaces = list(providedBy(obj))
    # TODO: versioned Interfaces!
    ilist = []
    for i in interfaces:
        if isinstance(i, RemoteInterfaceClass):
            if i not in ilist:
                ilist.append(i)
    ilist.sort(lambda x,y: cmp(x.__remote_name__, y.__remote_name__))
    # TODO: really? both sides must match
    return ilist

class DuplicateRemoteInterfaceError(Exception):
    pass

RemoteInterfaceRegistry = {}
def registerRemoteInterface(iface, name=None):
    if not name:
        name = iface.__remote_name__
    assert isinstance(iface, RemoteInterfaceClass)
    if RemoteInterfaceRegistry.has_key(name):
        old = RemoteInterfaceRegistry[name]
        msg = "remote interface %s was registered with the same name (%s) as %s, please use __remote_name__ to provide a unique name" % (old, name, iface)
        raise DuplicateRemoteInterfaceError(msg)
    RemoteInterfaceRegistry[name] = iface



class ICopyable(Interface):
    """I represent an object which is passed-by-value across PB connections.
    """

    def getTypeToCopy(self):
        """Return a string which names the class. This string must match
        the one that gets registered at the receiving end."""
    def getStateToCopy(self):
        """Return a state dictionary (with plain-string keys) which will be
        serialized and sent to the remote end. This state object will be
        given to the receiving object's setCopyableState method."""

class Copyable(object):
    implements(ICopyable)

    def getTypeToCopy(self):
        return reflect.qual(self.__class__)
    def getStateToCopy(self):
        return self.__dict__

class CopyableSlicer(slicer.BaseSlicer):
    """I handle ICopyable objects (things which are copied by value)."""
    def slice(self, streamable, banana):
        yield 'copyable'
        yield self.obj.getTypeToCopy()
        state = self.obj.getStateToCopy()
        for k,v in state.iteritems():
            yield k
            yield v
    def describe(self):
        return "<%s>" % self.obj.getTypeToCopy()
registerAdapter(CopyableSlicer, ICopyable, ISlicer)


class Copyable2(slicer.BaseSlicer):
    # I am my own Slicer. This has more methods than you'd usually want in a
    # base class, but if you can't register an Adapter for a whole class
    # hierarchy then you may have to use it.
    def getTypeToCopy(self):
        return reflect.qual(self.__class__)
    def getStateToCopy(self):
        return self.__dict__
    def slice(self, streamable, banana):
        yield 'instance'
        yield self.getTypeToCopy()
        yield self.getStateToCopy()
    def describe(self):
        return "<%s>" % self.getTypeToCopy()

#registerRemoteCopy(typename, factory)
#registerUnslicer(typename, factory)

class IRemoteCopy(Interface):
    """This interface defines what a RemoteCopy class must do. RemoteCopy
    subclasses are used as factories to create objects that correspond to
    Copyables sent over the wire.

    Note that the constructor of an IRemoteCopy class will be called without
    any arguments.
    
    """

    def setCopyableState(self, statedict):
        """I accept an attribute dictionary name/value pairs and use it to
        set my internal state.

        Some of the values may be Deferreds, which are placeholders for the
        as-yet-unreferenceable object which will eventually go there. If you
        receive a Deferred, you are responsible for adding a callback to
        update the attribute when it fires. [note:
        RemoteCopyUnslicer.receiveChild currently has a restriction which
        prevents this from happening, but that may go away in the future]

        Some of the objects referenced by the attribute values may have
        Deferreds in them (e.g. containers which reference recursive tuples).
        Such containers are responsible for updating their own state when
        those Deferreds fire, but until that point their state is still
        subject to change. Therefore you must be careful about how much state
        inspection you perform within this method."""
        
    stateSchema = interface.Attribute("""I return an AttributeDictConstraint
    object which places restrictions on incoming attribute values. These
    restrictions are enforced as the tokens are received, before the state is
    passed to setCopyableState.""")


class RemoteCopy(object):
    implements(IRemoteCopy)

    stateSchema = None # always a class attribute
    nonCyclic = False

    def __init__(self):
        # the constructor will always be called without arguments
        pass

    def setCopyableState(self, state):
        self.__dict__ = state

class RemoteCopyUnslicer(slicer.BaseUnslicer):
    attrname = None
    attrConstraint = None

    def __init__(self, factory):
        self.factory = factory
        self.schema = factory.stateSchema

    def start(self, count):
        self.d = {}
        self.count = count
        self.deferred = Deferred()
        self.protocol.setObject(count, self.deferred)

    def checkToken(self, typebyte, size):
        if self.attrname == None:
            if typebyte not in (tokens.STRING, tokens.VOCAB):
                raise BananaError("RemoteCopyUnslicer keys must be STRINGs")
        else:
            if self.attrConstraint:
                self.attrConstraint.checkToken(typebyte, size)

    def doOpen(self, opentype):
        if self.attrConstraint:
            self.attrConstraint.checkOpentype(opentype)
        unslicer = self.open(opentype)
        if unslicer:
            if self.attrConstraint:
                unslicer.setConstraint(self.attrConstraint)
        return unslicer

    def receiveChild(self, obj):
        if self.attrname == None:
            attrname = obj
            if self.d.has_key(attrname):
                raise BananaError("duplicate attribute name '%s'" % attrname)
            s = self.schema
            if s:
                accept, self.attrConstraint = s.getAttrConstraint(attrname)
                assert accept
            self.attrname = attrname
        else:
            if isinstance(obj, Deferred):
                # TODO: this is an artificial restriction, and it might
                # be possible to remove it, but I need to think through
                # it carefully first
                raise BananaError("unreferenceable object in attribute")
            self.setAttribute(self.attrname, obj)
            self.attrname = None
            self.attrConstraint = None

    def setAttribute(self, name, value):
        self.d[name] = value

    def receiveClose(self):
        obj = self.factory()
        obj.setCopyableState(self.d)
        self.protocol.setObject(self.count, obj)
        self.deferred.callback(obj)
        return obj

    def describe(self):
        if self.classname == None:
            return "<??>"
        me = "<%s>" % self.classname
        if self.attrname is None:
            return "%s.attrname??" % me
        else:
            return "%s.%s" % (me, self.attrname)
    

class NonCyclicRemoteCopyUnslicer(RemoteCopyUnslicer):
    # The Deferred used in RemoteCopyUnslicer (used in case the RemoteCopy
    # is participating in a reference cycle, say 'obj.foo = obj') makes it
    # unsuitable for holding Failures (which cannot be passed through
    # Deferred.callback). Use this class for Failures. It cannot handle
    # reference cycles (they will cause a KeyError when the reference is
    # followed).

    def start(self, count):
        self.d = {}
        self.count = count
        self.gettingAttrname = True

    def receiveClose(self):
        obj = self.factory()
        obj.setCopyableState(self.d)
        return obj

CopyableRegistry = {}
def registerRemoteCopy(typename, factory):
    """Tell PB that 'factory' can be used to handle Copyable objects that
    provide a getTypeToCopy name of 'typename'. 'factory' can be a
    RemoteCopy subclass (it implements IRemoteCopy), or they can be an
    Unslicer class (it implements IUnslicer). In addition, IRemoteCopy
    factories with a true .nonCyclic attribute will be created with the
    NonCyclicRemoteCopyUnslicer.
    """
    # to be more clever than this, register an Unslicer instead
    assert (IRemoteCopy.implementedBy(factory) or
            tokens.IUnslicer.implementedBy(factory))
    CopyableRegistry[typename] = factory


class Referenceable(object):
    _interfaceNames = None
    # TODO: this code wants to be in an adapter, not a base class. Also, it
    # would be nice to cache this across the class: if every instance has the
    # same interface list, they will have the same set of _interfaceNames,
    # and it feels silly to store that list separately for each instance.
    # Perhaps we could compare the instance's interface list with that of the
    # class and only recompute the names if they differ.

    def getInterfaceNames(self):
        if not self._interfaceNames:
            self._interfaceNames = [iface.__remote_name__
                                    for iface in getRemoteInterfaces(self)]

            # detect and warn about method name collisions. We do this here
            # because it's pretty much the only place that a set of
            # RemoteInterfaces are brought together into a single place.
            # Really, we only want to do this once per Referenceable
            # subclass, not per-instance. TODO: consider using a
            # Referenceable metaclass to implement such an optimization.
            methods = {}
            for iface in getRemoteInterfaces(self):
                for name in list(iface):
                    if methods.has_key(name):
                        log.msg("WARNING: method '%s' occurs in both %s and %s"
                                % (name, methods[name].__remote_name__,
                                   iface.__remote_name__))
                    else:
                        methods[name] = iface

        return self._interfaceNames

    def processUniqueID(self):
        return id(self)

# TODO: rather than subclassing Referenceable, ReferenceableSlicer should be
# used for anything which provides any RemoteInterface

class ReferenceableSlicer(slicer.BaseSlicer):
    """I handle pb.Referenceable objects (things with remotely invokable
    methods, which are copied by reference).
    """
    opentype = ('my-reference',)

    def sliceBody(self, streamable, broker):
        puid = self.obj.processUniqueID()
        clid, firstTime = broker.getCLID(puid, self.obj)
        yield clid
        if firstTime:
            # this is the first time the Referenceable has crossed this
            # wire. In addition to the luid, send the interface list to the
            # far end.
            yield self.obj.getInterfaceNames()

registerAdapter(ReferenceableSlicer, Referenceable, ISlicer)

class ReferenceUnslicer(slicer.BaseUnslicer):
    """I turn an incoming 'my-reference' sequence into a RemoteReference."""
    clid = None
    interfaces = []
    ilistConstraint = schema.ListOf(str) # TODO: only known RI names?

    def checkToken(self, typebyte, size):
        if self.clid is None:
            if typebyte != tokens.INT:
                raise BananaError("reference ID must be an INT")
        else:
            self.ilistConstraint.checkToken(typebyte, size)

    def doOpen(self, opentype):
        # only for the interface list
        self.ilistConstraint.checkOpentype(opentype)
        unslicer = self.open(opentype)
        if unslicer:
            unslicer.setConstraint(self.ilistConstraint)
        return unslicer

    def receiveChild(self, token):
        if self.clid is None:
            self.clid = token
        else:
            # must be the interface list
            assert type(token) == type([]) # TODO: perhaps a dict instead
            self.interfaces = token

    def receiveClose(self):
        if self.clid is None:
            raise BananaError("sequence ended too early")
        return self.broker.registerRemoteReference(self.clid,
                                                   self.interfaces)

    def describe(self):
        if self.clid is None:
            return "<ref-?>"
        return "<ref-%s>" % self.clid

class YourReferenceSlicer(slicer.BaseSlicer):
    """I handle pb.RemoteReference objects (being sent back home to the
    original pb.Referenceable-holder)
    """
    opentype = ('your-reference',)

    def sliceBody(self, streamable, broker):
        if not self.obj.broker == broker:
            # only send to home broker
            raise Violation("RemoteReferences can only be sent back to their home Broker")
        yield self.obj.refID # either string or int
    def describe(self):
        return "<your-ref-%s>" % self.obj.refID

# the registerAdapter() is performed in pb.py, since RemoteReference lives
# there

class YourReferenceUnslicer(slicer.LeafUnslicer):
    """I accept incoming (integer) your-reference sequences and try to turn
    them back into the original Referenceable. I also accept (string)
    your-reference sequences and try to turn them into a published
    Referenceable that they did not have access to before."""
    clid = None

    def checkToken(self, typebyte, size):
        if typebyte not in (tokens.INT, tokens.STRING, tokens.VOCAB):
            raise BananaError("your-reference ID must be an INT or STRING")

    def receiveChild(self, token):
        self.clid = token

    def receiveClose(self):
        if self.clid is None:
            raise BananaError("sequence ended too early")
        obj = self.broker.getReferenceable(self.clid)
        if not obj:
            raise Violation("unknown clid '%s'" % self.clid)
        return obj

    def describe(self):
        return "<your-ref-%s>" % self.obj.refID
