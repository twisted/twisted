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
    def __init__(self, iname, bases=(), attrs=None, __module__=None):
        if attrs is not None:
            try:
                remote_name = self._parseRemoteInterface(iname, attrs)
            except:
                print "error parsing remote-interface attributes"
                raise

        # now let the normal InterfaceClass take over
        interface.InterfaceClass.__init__(self, iname, bases, attrs,
                                          __module__)

        # auto-register the interface
        if attrs is not None:
            try:
                registerRemoteInterface(self, remote_name)
            except:
                print "error registering RemoteInterface '%s'" % remote_name
                raise

    def _parseRemoteInterface(self, iname, attrs):
        # determine all remotely-callable methods
        methods = [name for name in attrs.keys()
                   if ((type(attrs[name]) == types.FunctionType and
                        not name.startswith("_")) or
                       schema.IConstraint.providedBy(attrs[name]))]

        # turn them into constraints
        constraints = {}
        for name in methods:
            m = attrs[name]
            if not schema.IConstraint.providedBy(m):
                m = schema.RemoteMethodSchema(method=m)
            constraints[name] = m
            # delete the methods, so zope's InterfaceClass doesn't see them
            del attrs[name]

        # and see if there is a __remote_name__ . We delete it because
        # InterfaceClass doesn't like arbitrary attributes
        remote_name = attrs.get("__remote_name__", iname)
        if attrs.has_key("__remote_name__"):
            del attrs["__remote_name__"]

        self.__remote_stuff__ = (methods, constraints, remote_name)
        return remote_name

    def remoteGetMethodNames(self):
        return self.__remote_stuff__[0]
    def remoteGetMethodConstraint(self, name):
        return self.__remote_stuff__[1][name]
    def remoteGetRemoteName(self):
        return self.__remote_stuff__[2]

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
    def getname(i):
        return i.remoteGetRemoteName()
    ilist.sort(lambda x,y: cmp(x.remoteGetRemoteName(),
                               y.remoteGetRemoteName()))
    # TODO: really? both sides must match
    return ilist

def getRemoteInterfaceNames(obj):
    """Get the names of all RemoteInterfaces supported by the object."""
    return [i.remoteGetRemoteName() for i in getRemoteInterfaces(obj)]

class DuplicateRemoteInterfaceError(Exception):
    pass

RemoteInterfaceRegistry = {}
def registerRemoteInterface(iface, name=None):
    if not name:
        name = iface.remoteGetRemoteName()
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
        Deferreds in them (e.g. containers which reference recursive
        tuples). Therefore you must be careful about how much state
        inspection you perform within this method."""
        
    def getStateSchema(self):
        """I return an AttributeDictConstraint object which places
        restrictions on incoming attribute values. These restrictions are
        enforced as the tokens are received, before the state is passed to
        setCopyableState."""

class RemoteCopy(object):
    implements(IRemoteCopy)

    stateSchema = None
    nonCyclic = False

    def __init__(self):
        # the constructor will not be called with any args
        pass

    def setCopyableState(self, state):
        self.__dict__ = state
    def getStateSchema(self):
        return self.stateSchema

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

    def doOpen(self, opentype):
        if self.attrConstraint:
            self.attrConstraint.checkOpentype(opentype)
        unslicer = self.open(opentype)
        if unslicer:
            if self.attrConstraint:
                unslicer.setConstraint(self.attrConstraint)
        return unslicer

    def receiveChild(self, obj):
        self.propagateUnbananaFailures(obj)
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

    def setAttribute(self, name, value):
        self.d[name] = value

    def receiveClose(self):
        obj = self.factory()
        obj.setCopyableState(self.d)
        self.protocol.setObject(self.count, obj)
        self.deferred.callback(obj)
        return obj

    def describeSelf(self):
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
    refschema = None
    # TODO: this wants to be in an adapter, not a base class

    def getSchema(self):
        # create and return a RemoteReferenceSchema for us
        if not self.refschema:
            interfaces = dict([
                (iface.remoteGetRemoteName(), iface)
                for iface in getRemoteInterfaces(self)])
            self.refschema = schema.RemoteReferenceSchema(interfaces)
        return self.refschema
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
            yield getRemoteInterfaceNames(self.obj)
            # TODO: maybe create the RemoteReferenceSchema now
            # obj.getSchema()
registerAdapter(ReferenceableSlicer, Referenceable, ISlicer)

class ReferenceUnslicer(slicer.BaseUnslicer):
    clid = None
    interfaces = []
    ilistConstraint = schema.ListOf(str)

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
        self.propagateUnbananaFailures(token)

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
# the registerAdapter() is performed in pb.py, since RemoteReference lives
# there

class YourReferenceUnslicer(slicer.LeafUnslicer):
    clid = None

    def checkToken(self, typebyte, size):
        if typebyte not in (tokens.INT, tokens.STRING, tokens.VOCAB):
            raise BananaError("your-reference ID must be an INT or STRING")

    def receiveChild(self, token):
        self.propagateUnbananaFailures(token)
        self.clid = token

    def receiveClose(self):
        if self.clid is None:
            raise BananaError("sequence ended too early")
        obj = self.broker.getReferenceable(self.clid)
        if not obj:
            raise Violation("unknown clid '%s'" % self.clid)
        return obj
