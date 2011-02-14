# -*- test-case-name: twisted.test.test_explorer -*-
# $Id: explorer.py,v 1.6 2003/02/18 21:15:30 acapnotic Exp $
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.


"""Support for python object introspection and exploration.

Note that Explorers, what with their list of attributes, are much like
manhole.coil.Configurables.  Someone should investigate this further. (TODO)

Also TODO: Determine how much code in here (particularly the function
signature stuff) can be replaced with functions available in the
L{inspect} module available in Python 2.1.
"""

# System Imports
import inspect, new, string, sys, types
import UserDict

# Twisted Imports
from twisted.spread import pb
from twisted.python import reflect


True=(1==1)
False=not True

class Pool(UserDict.UserDict):
    def getExplorer(self, object, identifier):
        oid = id(object)
        if self.data.has_key(oid):
            # XXX: This potentially returns something with
            # 'identifier' set to a different value.
            return self.data[oid]
        else:
            klass = typeTable.get(type(object), ExplorerGeneric)
            e = new.instance(klass, {})
            self.data[oid] = e
            klass.__init__(e, object, identifier)
            return e

explorerPool = Pool()

class Explorer(pb.Cacheable):
    properties = ["id", "identifier"]
    attributeGroups = []
    accessors = ["get_refcount"]

    id = None
    identifier = None

    def __init__(self, object, identifier):
        self.object = object
        self.identifier = identifier
        self.id = id(object)

        self.properties = []
        reflect.accumulateClassList(self.__class__, 'properties',
                                    self.properties)

        self.attributeGroups = []
        reflect.accumulateClassList(self.__class__, 'attributeGroups',
                                    self.attributeGroups)

        self.accessors = []
        reflect.accumulateClassList(self.__class__, 'accessors',
                                    self.accessors)

    def getStateToCopyFor(self, perspective):
        all = ["properties", "attributeGroups", "accessors"]
        all.extend(self.properties)
        all.extend(self.attributeGroups)

        state = {}
        for key in all:
            state[key] = getattr(self, key)

        state['view'] = pb.ViewPoint(perspective, self)
        state['explorerClass'] = self.__class__.__name__
        return state

    def view_get_refcount(self, perspective):
        return sys.getrefcount(self)

class ExplorerGeneric(Explorer):
    properties = ["str", "repr", "typename"]

    def __init__(self, object, identifier):
        Explorer.__init__(self, object, identifier)
        self.str = str(object)
        self.repr = repr(object)
        self.typename = type(object).__name__


class ExplorerImmutable(Explorer):
    properties = ["value"]

    def __init__(self, object, identifier):
        Explorer.__init__(self, object, identifier)
        self.value = object


class ExplorerSequence(Explorer):
    properties = ["len"]
    attributeGroups = ["elements"]
    accessors = ["get_elements"]

    def __init__(self, seq, identifier):
        Explorer.__init__(self, seq, identifier)
        self.seq = seq
        self.len = len(seq)

        # Use accessor method to fill me in.
        self.elements = []

    def get_elements(self):
        self.len = len(self.seq)
        l = []
        for i in xrange(self.len):
            identifier = "%s[%s]" % (self.identifier, i)

            # GLOBAL: using global explorerPool
            l.append(explorerPool.getExplorer(self.seq[i], identifier))

        return l

    def view_get_elements(self, perspective):
        # XXX: set the .elements member of all my remoteCaches
        return self.get_elements()


class ExplorerMapping(Explorer):
    properties = ["len"]
    attributeGroups = ["keys"]
    accessors = ["get_keys", "get_item"]

    def __init__(self, dct, identifier):
        Explorer.__init__(self, dct, identifier)

        self.dct = dct
        self.len = len(dct)

        # Use accessor method to fill me in.
        self.keys = []

    def get_keys(self):
        keys = self.dct.keys()
        self.len = len(keys)
        l = []
        for i in xrange(self.len):
            identifier = "%s.keys()[%s]" % (self.identifier, i)

            # GLOBAL: using global explorerPool
            l.append(explorerPool.getExplorer(keys[i], identifier))

        return l

    def view_get_keys(self, perspective):
        # XXX: set the .keys member of all my remoteCaches
        return self.get_keys()

    def view_get_item(self, perspective, key):
        if type(key) is types.InstanceType:
            key = key.object

        item = self.dct[key]

        identifier = "%s[%s]" % (self.identifier, repr(key))
        # GLOBAL: using global explorerPool
        item = explorerPool.getExplorer(item, identifier)
        return item


class ExplorerBuiltin(Explorer):
    """
    @ivar name: the name the function was defined as
    @ivar doc: function's docstring, or C{None} if unavailable
    @ivar self: if not C{None}, the function is a method of this object.
    """
    properties = ["doc", "name", "self"]
    def __init__(self, function, identifier):
        Explorer.__init__(self, function, identifier)
        self.doc = function.__doc__
        self.name = function.__name__
        self.self = function.__self__


class ExplorerInstance(Explorer):
    """
    Attribute groups:
        - B{methods} -- dictionary of methods
        - B{data} -- dictionary of data members

    Note these are only the *instance* methods and members --
    if you want the class methods, you'll have to look up the class.

    TODO: Detail levels (me, me & class, me & class ancestory)

    @ivar klass: the class this is an instance of.
    """
    properties = ["klass"]
    attributeGroups = ["methods", "data"]

    def __init__(self, instance, identifier):
        Explorer.__init__(self, instance, identifier)
        members = {}
        methods = {}
        for i in dir(instance):
            # TODO: Make screening of private attributes configurable.
            if i[0] == '_':
                continue
            mIdentifier = string.join([identifier, i], ".")
            member = getattr(instance, i)
            mType = type(member)

            if mType is types.MethodType:
                methods[i] = explorerPool.getExplorer(member, mIdentifier)
            else:
                members[i] = explorerPool.getExplorer(member, mIdentifier)

        self.klass = explorerPool.getExplorer(instance.__class__,
                                              self.identifier +
                                              '.__class__')
        self.data = members
        self.methods = methods


class ExplorerClass(Explorer):
    """
    @ivar name: the name the class was defined with
    @ivar doc: the class's docstring
    @ivar bases: a list of this class's base classes.
    @ivar module: the module the class is defined in

    Attribute groups:
        - B{methods} -- class methods
        - B{data} -- other members of the class
    """
    properties = ["name", "doc", "bases", "module"]
    attributeGroups = ["methods", "data"]
    def __init__(self, theClass, identifier):
        Explorer.__init__(self, theClass, identifier)
        if not identifier:
            identifier = theClass.__name__
        members = {}
        methods = {}
        for i in dir(theClass):
            if (i[0] == '_') and (i != '__init__'):
                continue

            mIdentifier = string.join([identifier, i], ".")
            member = getattr(theClass, i)
            mType = type(member)

            if mType is types.MethodType:
                methods[i] = explorerPool.getExplorer(member, mIdentifier)
            else:
                members[i] = explorerPool.getExplorer(member, mIdentifier)

        self.name = theClass.__name__
        self.doc = inspect.getdoc(theClass)
        self.data = members
        self.methods = methods
        self.bases = explorerPool.getExplorer(theClass.__bases__,
                                              identifier + ".__bases__")
        self.module = getattr(theClass, '__module__', None)


class ExplorerFunction(Explorer):
    properties = ["name", "doc", "file", "line","signature"]
    """
        name -- the name the function was defined as
        signature -- the function's calling signature (Signature instance)
        doc -- the function's docstring
        file -- the file the function is defined in
        line -- the line in the file the function begins on
    """
    def __init__(self, function, identifier):
        Explorer.__init__(self, function, identifier)
        code = function.func_code
        argcount = code.co_argcount
        takesList = (code.co_flags & 0x04) and 1
        takesKeywords = (code.co_flags & 0x08) and 1

        n = (argcount + takesList + takesKeywords)
        signature = Signature(code.co_varnames[:n])

        if function.func_defaults:
            i_d = 0
            for i in xrange(argcount - len(function.func_defaults),
                            argcount):
                default = function.func_defaults[i_d]
                default = explorerPool.getExplorer(
                    default, '%s.func_defaults[%d]' % (identifier, i_d))
                signature.set_default(i, default)

                i_d = i_d + 1

        if takesKeywords:
            signature.set_keyword(n - 1)

        if takesList:
            signature.set_varlist(n - 1 - takesKeywords)

        # maybe also: function.func_globals,
        # or at least func_globals.__name__?
        # maybe the bytecode, for disassembly-view?

        self.name = function.__name__
        self.signature = signature
        self.doc = inspect.getdoc(function)
        self.file = code.co_filename
        self.line = code.co_firstlineno


class ExplorerMethod(ExplorerFunction):
    properties = ["self", "klass"]
    """
    In addition to ExplorerFunction properties:
        self -- the object I am bound to, or None if unbound
        klass -- the class I am a method of
    """
    def __init__(self, method, identifier):

        function = method.im_func
        if type(function) is types.InstanceType:
            function = function.__call__.im_func

        ExplorerFunction.__init__(self, function, identifier)
        self.id = id(method)
        self.klass = explorerPool.getExplorer(method.im_class,
                                              identifier + '.im_class')
        self.self = explorerPool.getExplorer(method.im_self,
                                             identifier + '.im_self')

        if method.im_self:
            # I'm a bound method -- eat the 'self' arg.
            self.signature.discardSelf()


class ExplorerModule(Explorer):
    """
    @ivar name: the name the module was defined as
    @ivar doc: documentation string for the module
    @ivar file: the file the module is defined in

    Attribute groups:
        - B{classes} -- the public classes provided by the module
        - B{functions} -- the public functions provided by the module
        - B{data} -- the public data members provided by the module

    (\"Public\" is taken to be \"anything that doesn't start with _\")
    """
    properties = ["name","doc","file"]
    attributeGroups = ["classes", "functions", "data"]

    def __init__(self, module, identifier):
        Explorer.__init__(self, module, identifier)
        functions = {}
        classes = {}
        data = {}
        for key, value in module.__dict__.items():
            if key[0] == '_':
                continue

            mIdentifier = "%s.%s" % (identifier, key)

            if type(value) is types.ClassType:
                classes[key] = explorerPool.getExplorer(value,
                                                        mIdentifier)
            elif type(value) is types.FunctionType:
                functions[key] = explorerPool.getExplorer(value,
                                                          mIdentifier)
            elif type(value) is types.ModuleType:
                pass # pass on imported modules
            else:
                data[key] = explorerPool.getExplorer(value, mIdentifier)

        self.name = module.__name__
        self.doc = inspect.getdoc(module)
        self.file = getattr(module, '__file__', None)
        self.classes = classes
        self.functions = functions
        self.data = data

typeTable = {types.InstanceType: ExplorerInstance,
             types.ClassType: ExplorerClass,
             types.MethodType: ExplorerMethod,
             types.FunctionType: ExplorerFunction,
             types.ModuleType: ExplorerModule,
             types.BuiltinFunctionType: ExplorerBuiltin,
             types.ListType: ExplorerSequence,
             types.TupleType: ExplorerSequence,
             types.DictType: ExplorerMapping,
             types.StringType: ExplorerImmutable,
             types.NoneType: ExplorerImmutable,
             types.IntType: ExplorerImmutable,
             types.FloatType: ExplorerImmutable,
             types.LongType: ExplorerImmutable,
             types.ComplexType: ExplorerImmutable,
             }

class Signature(pb.Copyable):
    """I represent the signature of a callable.

    Signatures are immutable, so don't expect my contents to change once
    they've been set.
    """
    _FLAVOURLESS = None
    _HAS_DEFAULT = 2
    _VAR_LIST = 4
    _KEYWORD_DICT = 8

    def __init__(self, argNames):
        self.name = argNames
        self.default = [None] * len(argNames)
        self.flavour = [None] * len(argNames)

    def get_name(self, arg):
        return self.name[arg]

    def get_default(self, arg):
        if arg is types.StringType:
            arg = self.name.index(arg)

        # Wouldn't it be nice if we just returned "None" when there
        # wasn't a default?  Well, yes, but often times "None" *is*
        # the default, so return a tuple instead.
        if self.flavour[arg] == self._HAS_DEFAULT:
            return (True, self.default[arg])
        else:
            return (False, None)

    def set_default(self, arg, value):
        if arg is types.StringType:
            arg = self.name.index(arg)

        self.flavour[arg] = self._HAS_DEFAULT
        self.default[arg] = value

    def set_varlist(self, arg):
        if arg is types.StringType:
            arg = self.name.index(arg)

        self.flavour[arg] = self._VAR_LIST

    def set_keyword(self, arg):
        if arg is types.StringType:
            arg = self.name.index(arg)

        self.flavour[arg] = self._KEYWORD_DICT

    def is_varlist(self, arg):
        if arg is types.StringType:
            arg = self.name.index(arg)

        return (self.flavour[arg] == self._VAR_LIST)

    def is_keyword(self, arg):
        if arg is types.StringType:
            arg = self.name.index(arg)

        return (self.flavour[arg] == self._KEYWORD_DICT)

    def discardSelf(self):
        """Invoke me to discard the first argument if this is a bound method.
        """
        ## if self.name[0] != 'self':
        ##    log.msg("Warning: Told to discard self, but name is %s" %
        ##            self.name[0])
        self.name = self.name[1:]
        self.default.pop(0)
        self.flavour.pop(0)

    def getStateToCopy(self):
        return {'name': tuple(self.name),
                'flavour': tuple(self.flavour),
                'default': tuple(self.default)}

    def __len__(self):
        return len(self.name)

    def __str__(self):
        arglist = []
        for arg in xrange(len(self)):
            name = self.get_name(arg)
            hasDefault, default = self.get_default(arg)
            if hasDefault:
                a = "%s=%s" % (name, default)
            elif self.is_varlist(arg):
                a = "*%s" % (name,)
            elif self.is_keyword(arg):
                a = "**%s" % (name,)
            else:
                a = name
            arglist.append(a)

        return string.join(arglist,", ")





class CRUFT_WatchyThingie:
    # TODO:
    #
    #  * an exclude mechanism for the watcher's browser, to avoid
    #    sending back large and uninteresting data structures.
    #
    #  * an exclude mechanism for the watcher's trigger, to avoid
    #    triggering on some frequently-called-method-that-doesn't-
    #    actually-change-anything.
    #
    #  * XXX! need removeWatch()

    def watchIdentifier(self, identifier, callback):
        """Watch the object returned by evaluating the identifier.

        Whenever I think the object might have changed, I'll send an
        ObjectLink of it to the callback.

        WARNING: This calls eval() on its argument!
        """
        object = eval(identifier,
                      self.globalNamespace,
                      self.localNamespace)
        return self.watchObject(object, identifier, callback)

    def watchObject(self, object, identifier, callback):
        """Watch the given object.

        Whenever I think the object might have changed, I'll send an
        ObjectLink of it to the callback.

        The identifier argument is used to generate identifiers for
        objects which are members of this one.
        """
        if type(object) is not types.InstanceType:
            raise TypeError, "Sorry, can only place a watch on Instances."

        # uninstallers = []

        dct = {}
        reflect.addMethodNamesToDict(object.__class__, dct, '')
        for k in object.__dict__.keys():
            dct[k] = 1

        members = dct.keys()

        clazzNS = {}
        clazz = new.classobj('Watching%s%X' %
                             (object.__class__.__name__, id(object)),
                             (_MonkeysSetattrMixin, object.__class__,),
                             clazzNS)

        clazzNS['_watchEmitChanged'] = new.instancemethod(
            lambda slf, i=identifier, b=self, cb=callback:
            cb(b.browseObject(slf, i)),
            None, clazz)

        # orig_class = object.__class__
        object.__class__ = clazz

        for name in members:
            m = getattr(object, name)
            # Only hook bound methods.
            if ((type(m) is types.MethodType)
                and (m.im_self is not None)):
                # What's the use of putting watch monkeys on methods
                # in addition to __setattr__?  Well, um, uh, if the
                # methods modify their attributes (i.e. add a key to
                # a dictionary) instead of [re]setting them, then
                # we wouldn't know about it unless we did this.
                # (Is that convincing?)

                monkey = _WatchMonkey(object)
                monkey.install(name)
                # uninstallers.append(monkey.uninstall)

        # XXX: This probably prevents these objects from ever having a
        # zero refcount.  Leak, Leak!
        ## self.watchUninstallers[object] = uninstallers


class _WatchMonkey:
    """I hang on a method and tell you what I see.

    TODO: Aya!  Now I just do browseObject all the time, but I could
    tell you what got called with what when and returning what.
    """
    oldMethod = None

    def __init__(self, instance):
        """Make a monkey to hang on this instance object.
        """
        self.instance = instance

    def install(self, methodIdentifier):
        """Install myself on my instance in place of this method.
        """
        oldMethod = getattr(self.instance, methodIdentifier, None)

        # XXX: this conditional probably isn't effective.
        if oldMethod is not self:
            # avoid triggering __setattr__
            self.instance.__dict__[methodIdentifier] = (
                new.instancemethod(self, self.instance,
                                   self.instance.__class__))
            self.oldMethod = (methodIdentifier, oldMethod)

    def uninstall(self):
        """Remove myself from this instance and restore the original method.

        (I hope.)
        """
        if self.oldMethod is None:
            return

        # XXX: This probably doesn't work if multiple monkies are hanging
        # on a method and they're not removed in order.
        if self.oldMethod[1] is None:
            delattr(self.instance, self.oldMethod[0])
        else:
            setattr(self.instance, self.oldMethod[0], self.oldMethod[1])

    def __call__(self, instance, *a, **kw):
        """Pretend to be the method I replaced, and ring the bell.
        """
        if self.oldMethod[1]:
            rval = apply(self.oldMethod[1], a, kw)
        else:
            rval = None

        instance._watchEmitChanged()
        return rval


class _MonkeysSetattrMixin:
    """A mix-in class providing __setattr__ for objects being watched.
    """
    def __setattr__(self, k, v):
        """Set the attribute and ring the bell.
        """
        if hasattr(self.__class__.__bases__[1], '__setattr__'):
            # Hack!  Using __bases__[1] is Bad, but since we created
            # this class, we can be reasonably sure it'll work.
            self.__class__.__bases__[1].__setattr__(self, k, v)
        else:
            self.__dict__[k] = v

        # XXX: Hey, waitasec, did someone just hang a new method on me?
        #  Do I need to put a monkey on it?

        self._watchEmitChanged()
