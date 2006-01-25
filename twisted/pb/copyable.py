# -*- test-case-name: twisted.pb.test.test_copyable -*-

# this module is responsible for all copy-by-value objects

from zope.interface import interface, implements
from twisted.python import reflect
from twisted.python.components import registerAdapter
from twisted.internet import defer

import slicer, tokens
from tokens import BananaError

Interface = interface.Interface

############################################################
# the first half of this file is sending/serialization

class ICopyable(Interface):
    """I represent an object which is passed-by-value across PB connections.
    """

    def getTypeToCopy():
        """Return a string which names the class. This string must match
        the one that gets registered at the receiving end."""
    def getStateToCopy():
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
registerAdapter(CopyableSlicer, ICopyable, tokens.ISlicer)


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

def registerCopier(klass, copier):
    """This is a shortcut for arranging to serialize third-party clases.
    'copier' must be a callable which accepts an instance of the class you
    want to serialize, and returns a tuple of (typename, state_dictionary).
    If it returns a typename of None, the original class's fully-qualified
    classname is used.
    """
    klassname = reflect.qual(klass)
    class _CopierAdapter:
        implements(ICopyable)
        def __init__(self, original):
            self.nameToCopy, self.state = copier(original)
            if self.nameToCopy is None:
                self.nameToCopy = klassname
        def getTypeToCopy(self):
            return self.nameToCopy
        def getStateToCopy(self):
            return self.state
    registerAdapter(_CopierAdapter, klass, ICopyable)

############################################################
# beyond here is the receiving/deserialization side

class RemoteCopyUnslicer(slicer.BaseUnslicer):
    attrname = None
    attrConstraint = None

    def __init__(self, factory, stateSchema):
        self.factory = factory
        self.schema = stateSchema

    def start(self, count):
        self.d = {}
        self.count = count
        self.deferred = defer.Deferred()
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

    def receiveChild(self, obj, ready_deferred=None):
        assert not isinstance(obj, defer.Deferred)
        assert ready_deferred is None
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
            if isinstance(obj, defer.Deferred):
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
        try:
            obj = self.factory(self.d)
        except:
            log.msg("%s.receiveClose: problem in factory %s" %
                    (self.__class__.__name__, self.factory))
            log.err()
            raise
        self.protocol.setObject(self.count, obj)
        self.deferred.callback(obj)
        return obj, None

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
        obj = self.factory(self.d)
        return obj, None


class IRemoteCopy(Interface):
    """This interface defines what a RemoteCopy class must do. RemoteCopy
    subclasses are used as factories to create objects that correspond to
    Copyables sent over the wire.

    Note that the constructor of an IRemoteCopy class will be called without
    any arguments.
    """

    def setCopyableState(statedict):
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


# This maps typename to an Unslicer factory
CopyableRegistry = {}
def registerRemoteCopyUnslicerFactory(typename, unslicerfactory,
                                      registry=None):
    """Tell PB that unslicerfactory can be used to handle Copyable objects
    that provide a getTypeToCopy name of 'typename'. 'unslicerfactory' must
    be a callable which takes no arguments and returns an object which
    provides IUnslicer.
    """
    assert callable(unslicerfactory)
    # in addition, it must produce a tokens.IUnslicer . This is safe to do
    # because Unslicers don't do anything significant when they are created.
    test_unslicer = unslicerfactory()
    assert tokens.IUnslicer.providedBy(test_unslicer)
    assert type(typename) is str

    if registry == None:
        registry = CopyableRegistry
    assert not registry.has_key(typename)
    registry[typename] = unslicerfactory

# this keeps track of everything submitted to registerRemoteCopyFactory
debug_CopyableFactories = {}
def registerRemoteCopyFactory(typename, factory, stateSchema=None,
                              cyclic=True, registry=None):
    """Tell PB that 'factory' can be used to handle Copyable objects that
    provide a getTypeToCopy name of 'typename'. 'factory' must be a callable
    which accepts a state dictionary and returns a fully-formed instance.

    'cyclic' is a boolean, which should be set to False to avoid using a
    Deferred to provide the resulting RemoteCopy instance. This is needed to
    deserialize Failures (or instances which inherit from one, like
    CopiedFailure). In exchange for this, it cannot handle reference cycles.
    """
    assert callable(factory)
    debug_CopyableFactories[typename] = (factory, stateSchema, cyclic)
    if cyclic:
        def _RemoteCopyUnslicerFactory():
            return RemoteCopyUnslicer(factory, stateSchema)
        registerRemoteCopyUnslicerFactory(typename,
                                          _RemoteCopyUnslicerFactory,
                                          registry)
    else:
        def _RemoteCopyUnslicerFactoryNonCyclic():
            return NonCyclicRemoteCopyUnslicer(factory, stateSchema)
        registerRemoteCopyUnslicerFactory(typename,
                                          _RemoteCopyUnslicerFactoryNonCyclic,
                                          registry)

# this keeps track of everything submitted to registerRemoteCopy, which may
# be useful when you're wondering what's been auto-registered by the
# RemoteCopy metaclass magic
debug_RemoteCopyClasses = {}
def registerRemoteCopy(typename, remote_copy_class, registry=None):
    """Tell PB that remote_copy_class is the appropriate RemoteCopy class to
    use when deserializing a Copyable sequence that is tagged with
    'typename'. 'remote_copy_class' should be a RemoteCopy subclass or
    implement the same interface, which means its constructor takes no
    arguments and it has a setCopyableState(state) method to actually set the
    instance's state after initialization. It must also have a nonCyclic
    attribute.
    """
    assert IRemoteCopy.implementedBy(remote_copy_class)
    assert type(typename) is str

    debug_RemoteCopyClasses[typename] = remote_copy_class
    def _RemoteCopyFactory(state):
        obj = remote_copy_class()
        obj.setCopyableState(state)
        return obj

    registerRemoteCopyFactory(typename, _RemoteCopyFactory,
                              remote_copy_class.stateSchema, 
                              not remote_copy_class.nonCyclic,
                              registry)


class _AutoRegister:
    pass

class RemoteCopyClass(type):
    # auto-register RemoteCopy classes
    def __init__(self, name, bases, dict):
        type.__init__(self, name, bases, dict)
        copytype = dict.get('copytype', _AutoRegister)
        if copytype is _AutoRegister:
            copytype = dict['__module__'] + "." + name
        reg = dict.get('copyableRegistry')
        if copytype:
            registerRemoteCopy(copytype, self, reg)

class _RemoteCopyBase:

    implements(IRemoteCopy)

    stateSchema = None # always a class attribute
    nonCyclic = False

    def __init__(self):
        # the constructor will always be called without arguments
        pass

    def setCopyableState(self, state):
        self.__dict__ = state

class RemoteCopyOldStyle(_RemoteCopyBase):
    # note that these will not auto-register for you, because old-style
    # classes do not do metaclass magic
    copytype = None

class RemoteCopy(_RemoteCopyBase, object):
    # leave copytype at the default to auto-register with the fully-qualified
    # class name, which is the same behavior as Copyable. Set copytype to a
    # string to override this name. Set it to None to disable
    # auto-registration.

    # TODO: N.B. auto-registration with the default name is only actually
    # useful if you use the same class for both ends (i.e. your class
    # inherits from both pb.Copyable and pb.RemoteCopy). Otherwise the
    # default name for the receiver's pb.RemoteCopy class will be different
    # than the sender's pb.Copyable class.
    __metaclass__ = RemoteCopyClass
    pass
