
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

from twisted.spread import pb, jelly
import new, string, sys, types

# sibling
import reflect, text

def typeString(type):
    return jelly.typeNames.get(type, type.__name__)

class ObjectLink(pb.Copyable):
    """A representation of object with a particular identifier.

    This object:

        * has an 'identifier' member.  Feeding this identifier to
          ObjectBrowser.browseIdentifier should return information
          on the object I represent.

        * Has a 'value' member.  For simple objects, this contains
          the value of the object, where applicable.  For more complex
          objects, this is a sequence containing documentation and
          ObjectLinks of the object's properties.  See the documentation
          for ObjectBrowser.browse_* methods for details.

        * Has a 'type' member, with a string describing the type of
          object I represent.  If this type differs from the type of
          my 'value' attribute, that's an indication that the value
          attribute carries information *about* the object I represent,
          rather than being a direct representation.  Convert a TypeType
          to this string with the explorer.typeString function.

        * represents an object from *my* view.  That is, if
          it's a Perspective object with the methods bar() and
          perspective_foo(), I want to see that it has the methods bar()
          and perspective_foo(); not foo(), as it would appear remotely.

        * is jelly safe and pb.Copyable.
    """
    value = None
    type = None
    identifier = None

    def __init__(self, value, identifier=None, type=None, id_=None):
        """See ObjectLink class documentation for details on attributes.
        """
        self.value = value
        self.identifier = identifier
        self.id = id_

        # Shucks, TypeType isn't jelliable yet.
        if type:
            self.setType(type)

    def getStateToCopy(self):
        return {'value': self.value,
                'identifier': self.identifier,
                'type': self.type}

    def setType(self, type):
        """Given a TypeType, sets my 'type' attribute.
        """
        self._type = type
        self.type = typeString(type)

    def __repr__(self):
        ofString = typeString = ''
        if self.identifier:
            ofString = " of %s" % (self.identifier,)
        if self.type:
            typeString = " type %s" % (self.type,)

        s = "<%s at %x%s%s>" % (self.__class__, id(self),
                                ofString, typeString)
        return s

    def __str__(self):
        """Provides a readable, if not beautiful, view of my object tree.
        """
        if type(self.value) in (types.StringType, types.NoneType,
                                types.IntType, types.LongType,
                                types.FloatType, types.ComplexType):
            s = repr(self.value)
        else:
            if self.identifier:
                ofString = " of %s" % (self.identifier,)
            if self.type:
                typeString = " type %s" % (self.type,)

            r = "<%s%s%s>" % (self.__class__.__name__,
                               ofString, typeString)

            valueString = text.stringyString(self.value, '  ')
            if text.isMultiline(valueString):
                s = "%s:\n%s" % (r, valueString)
            else:
                s = "%s: %s" % (r, valueString)
        return s

class ObjectBrowser:
    """Return ObjectLinks for an identifier.

    There are three methods for browsing:

        * browseIdentifier takes an expression and browses the object
          obtained by evaluating it.

        * browseObject takes an object (and an identifier) and works from
          that.

        * browseStrictlyIdentifier takes an object name.  This object
          must be directly in the local or global namespace; no
          evaluating, getattr, or getitem of the identifier will be done.
    """
    globalNamespace = sys.modules['__main__'].__dict__
    localNamespace = None

    def __init__(self, globalNamespace=None, localNamespace=None):
        if globalNamespace is not None:
            self.globalNamespace = globalNamespace

        if localNamespace is not None:
            self.localNamespace = localNamespace
        else:
            self.localNamespace = {}

        self.watchUninstallers = {}

    def browseStrictlyIdentifier(self, identifier):
        """
        This checks for the identifier in the local and global
        namespaces.  If it's not there, raise a NameError.  Doesn't
        do any getattr for dots or getitem for brackets or evaluate
        nothin.
        """
        if self.localNamespace.has_key(identifier):
            object = self.localNamespace[identifier]
        elif self.globalNamespace.has_key(identifier):
            object = self.globalNamespace[identifier]
        else:
            raise NameError(identifier)

        return self.browseObject(object, identifier)

    def browseIdentifier(self, identifier):
        """WARNING: This calls eval() on its argument!

        This browses the object returned by evaluating
        the given expression.
        """
        object = eval(identifier,
                      self.globalNamespace,
                      self.localNamespace)
        return self.browseObject(object, identifier)

    def browseObject(self, object, identifier=None):
        """Browse the given object.
        """
        method = self.typeTable.get(type(object),
                                    self.__class__.browse_other)

        return method(self, object, identifier)

    def watchIdentifier(self, identifier, callback):
        object = eval(identifier,
                      self.globalNamespace,
                      self.localNamespace)
        return self.watchObject(object, identifier, callback)

    def watchObject(self, object, identifier, callback):
        if type(object) is not types.InstanceType:
            raise TypeError, "Sorry, can only place a watch on Instances."

        dct = {}
        reflect.addMethodNamesToDict(object.__class__, dct, '')
        for k in object.__dict__.keys():
            dct[k] = 1

        members = dct.keys()

        uninstallers = []

        clazzNS = {}
        clazz = new.classobj('Watching%s%X' %
                             (object.__class__.__name__, id(object)),
                             (_MonkeysSetattrMixin, object.__class__,),
                             clazzNS)

        clazzNS['_watchEmitChanged'] = new.instancemethod(
            lambda slf, i=identifier, b=self, cb=callback:
            cb(b.browseObject(slf, i)),
            None, clazz)

        orig_class = object.__class__
        object.__class__ = clazz

        for name in members:
            m = getattr(object, name)
            # Only hook bound methods.
            if ((type(m) is types.MethodType)
                and (m.im_self is not None)):

                monkey = _WatchMonkey(object)
                monkey.install(name)
                uninstallers.append(monkey.uninstall)

        # XXX: This probably prevents these objects from ever having a
        # zero refcount.  Leak, Leak!
        ## self.watchUninstallers[object] = uninstallers

    def browse_other(self, thing, identifier, seenThings=None):
        """
        returns an ObjectLink with no special properties.
        """
        if seenThings is None:
            seenThings = {}

        thingId = id(thing)
        seenThings[thingId] = 'Set'

        thingType = type(thing)
        if thingType in (types.StringType, types.NoneType,
                         types.IntType, types.LongType,
                         types.FloatType, types.ComplexType,
                         types.CodeType):
            # XXX: types.XRangeType needs to be made jelly-safe!
            thing = thing

        elif thingType in (types.ListType, types.TupleType):
            lst = [None] * len(thing)
            for i in xrange(len(thing)):
                iIdentifier = "%s[%d]" % (identifier, i)

                if seenThings.has_key(id(thing[i])):
                    lst[i] = ObjectLink(str(thing[i]), iIdentifier,
                                        type(thing[i]), id(thing[i]))
                else:
                    seenThings[id(thing[i])] = 'Set'
                    lst[i] = self.browse_other(thing[i], iIdentifier,
                                               seenThings)

            if thingType is types.TupleType:
                thing = tuple(lst)
            else:
                thing = lst

        elif thingType is types.DictType:
            dct = {}
            keys = thing.keys()
            for i in xrange(len(keys)):
                key = keys[i]
                value = thing[key]
                keyIdentifier = "%s.keys()[%d]" % (identifier, i)

                valueIdentifier = "%s[%s]" % (identifier, key)

                if seenThings.has_key(id(key)):
                    key = ObjectLink(str(key), keyIdentifier, type(key),
                                     id(key))
                else:
                    seenThings[id(key)] = 'Set'
                    key = self.browse_other(key, keyIdentifier,
                                            seenThings)
                if seenThings.has_key(id(value)):
                    value = ObjectLink(str(value), valueIdentifier,
                                       type(value), id(value))
                else:
                    seenThings[id(value)] = 'Set'
                    value = self.browse_other(value, valueIdentifier,
                                              seenThings)

                dct[key] = value

            thing = dct
        else:
            thing = str(thing)

        return ObjectLink(thing, identifier, thingType, thingId)

    def browse_builtin(self, function, identifier):
        """
        Returns a dictionary in an ObjectLink with type BulitinFunctionType.
        The dictionary contains the members:
            name -- the name the function was defined as
            doc -- function's docstring, or None if unavailable
            self -- if not None, the function is a method of this object.
        """
        rval = {'doc': function.__doc__,
                'name': function.__name__,
                'self': function.__self__}

        return ObjectLink(rval, identifier, types.BuiltinFunctionType,
                          id(function))

    def browse_instance(self, instance, identifier):
        """
        Returns a dictionary in an ObjectLink with type InstanceType.

        The dictionary contains the members:
            class -- an ObjectLink to the class this is an instance of
            methods -- a list of ObjectLinks of methods
            members -- a list of ObjectLinks of data members

        Note these are only the *instance* methods and members --
        if you want the class methods, you'll have to look up the class.
        """
        members = {}
        methods = {}
        for i in dir(instance):
            if i[0] == '_':
                continue
            mIdentifier = string.join([identifier, i], ".")
            member = getattr(instance, i)
            mType = type(member)

            if mType is types.MethodType:
                methods[i] = self.browse_method(member, mIdentifier)
            else:
                members[i] = self.browse_other(member, mIdentifier)

        rval = {"class": ObjectLink(str(instance.__class__),
                                    str(instance.__class__),
                                    type(instance.__class__),
                                    id(instance.__class__)),
                "members": members,
                "methods": methods,
                }

        return ObjectLink(rval, identifier, types.InstanceType,
                          id(instance))

    def browse_class(self, theClass, identifier):
        """
        Returns a dictionary in an ObjectLink with type ClassType.

        The dictionary contains the members:
            name -- the name the class was defined with
            doc -- the class's docstring
            methods -- class methods
            members -- other members of the class
            module -- the module the class is defined in
        """
        if not identifier:
            identifier = theClass.__name__
        members = {}
        methods = {}
        for i in dir(theClass):
            if (i[0] == '_') and (i != '__init__'):
                continue
            #if i in ('__module__', '__doc__'):
            #    continue

            mIdentifier = string.join([identifier, i], ".")
            member = getattr(theClass, i)
            mType = type(member)

            if mType is types.MethodType:
                methods[i] = self.browse_method(member, mIdentifier)
            else:
                members[i] = self.browse_other(member, mIdentifier)

        rval = {"name": theClass.__name__,
                "doc": text.docstringLStrip(theClass.__doc__),
                "members": members,
                "methods": methods,
                "bases": self.browse_other(theClass.__bases__,
                                        identifier + ".__bases__"),
                "module": getattr(theClass, '__module__', None),
                }

        return ObjectLink(rval, identifier, types.ClassType)

    def browse_method(self, method, identifier):
        """
        Returns a dictionary in an ObjectLink with type MethodType.

        In addition to the elements in the browse_function dictionary,
        this also includes 'self' and 'class' elements.
        """

        function = method.im_func
        if type(function) is types.InstanceType:
            function = function.__call__.im_func
        link = self.browse_function(function, identifier)
        link.id = id(method)
        link.value['class'] = self.browse_other(method.im_class,
                                             identifier + '.im_class')
        link.value['self'] = self.browse_other(method.im_self,
                                            identifier + '.im_self')
        link.setType(types.MethodType)
        if method.im_self:
            # I'm a bound method -- eat the 'self' arg.
            del link.value['signature'][0]
        return link

    def browse_function(self, function, identifier):
        """
        Returns a dictionary in an ObjectLink with type FunctionType.

        The dictionary contains the elements:
            name -- the name the function was defined as
            signature -- the function's calling signature
            doc -- the function's docstring
            file -- the file the function is defined in
            line -- the line in the file the function begins on

        The signature element is a list of dictionaries, each of which
        includes a 'name' element.  If that argument has a default, it
        is provided in the 'default' element.  If the argument is a
        variable argument list, its dictionary will have a 'list' key
        set.  If the argument accepts arbitrary keyword arguments, its
        dictionary will have a 'keywords' element set.
        """
        code = function.func_code
        argcount = code.co_argcount
        takesList = (code.co_flags & 0x04) and 1
        takesKeywords = (code.co_flags & 0x08) and 1

        args = [None] * (argcount + takesList + takesKeywords)
        for i in xrange(len(args)):
            args[i] = {'name': code.co_varnames[i]}

        if function.func_defaults:
            i_d = 0
            for i in xrange(argcount - len(function.func_defaults),
                            argcount):
                args[i]['default'] = self.browse_other(
                    function.func_defaults[i_d],
                    '%s.func_defaults[%d]' % (identifier, i_d))

                i_d = i_d + 1

        if takesKeywords:
            args[-1]['keywords'] = 1

        if takesList:
            args[-(1 + takesKeywords)]['list'] = 1

        # maybe also: function.func_globals

        rval = {'name': function.__name__,
                'signature': args,
                'doc': text.docstringLStrip(function.__doc__),
                'file': code.co_filename,
                'line': code.co_firstlineno,
                }

        return ObjectLink(rval, identifier, types.FunctionType,
                          id(function))

    def browse_module(self, module, identifier):
        """
        Returns a dictionary in an ObjectLink with type ModuleType.

        The dictionary contains the elements:
            name -- the name the module was defined as
            doc -- documentation string for the module
            file -- the file the module is defined in
            classes -- the public classes provided by the module
            functions -- the public functions provided by the module
            data -- the public data members provided by the module

        (\"Public\" is taken to be \"anything that doesn't start with _\")
        """
        functions = []
        classes = []
        data = []
        for key, value in module.__dict__.items():
            if key[0] == '_':
                continue

            mIdentifier = "%s.%s" % (identifier, key)

            if type(value) is types.ClassType:
                classes.append(self.browse_class(value, mIdentifier))
            elif type(value) is types.FunctionType:
                functions.append(self.browse_function(value, mIdentifier))
            elif type(value) is types.ModuleType:
                pass # pass on imported modules
            else:
                data.append(self.browse_other(value, mIdentifier))

        rval = {'name': module.__name__,
                'doc': text.docstringLStrip(module.__doc__),
                'file': getattr(module, '__file__', None),
                'classes': classes,
                'functions': functions,
                'data': data,
                }

        return ObjectLink(rval, identifier, types.ModuleType, id(module))

    typeTable = {types.InstanceType: browse_instance,
                 types.ClassType: browse_class,
                 types.MethodType: browse_method,
                 types.FunctionType: browse_function,
                 types.ModuleType: browse_module,
                 types.BuiltinFunctionType: browse_builtin,
                 }


class _WatchMonkey:
    """I hang on a method and tell you what I see.

    TODO: Aya!  Now I just do browseObject all the time, but I could
        tell you what got called with what when and returning what.
    """
    oldMethod = None

    def __init__(self, instance):
        """

        instance -- to watch
        """
        self.instance = instance

    def install(self, methodIdentifier):
        oldMethod = getattr(self.instance, methodIdentifier, None)

        # XXX: this conditional probably isn't effective.
        if oldMethod is not self:
            self.instance.__dict__[methodIdentifier] = (
                new.instancemethod(self, self.instance,
                                   self.instance.__class__))
            self.oldMethod = (methodIdentifier, oldMethod)

    def uninstall(self):
        if self.oldMethod is None:
            # Not installed.
            return

        # XXX: This probably doesn't work if multiple monkies are hanging
        # on a method and they're not removed in order.
        if self.oldMethod[1] is None:
            delattr(self.instance, self.oldMethod[0])
        else:
            setattr(self.instance, self.oldMethod[0], self.oldMethod[1])

    def __call__(self, instance, *a, **kw):
        if self.oldMethod[1]:
            rval = apply(self.oldMethod[1], a, kw)
        else:
            rval = None

        instance._watchEmitChanged()
        return rval

class _MonkeysSetattrMixin:
    def __setattr__(self, k, v):
        if hasattr(self.__class__.__bases__[1], '__setattr__'):
            # Hack!  Using __bases__[1] is Bad, but since we created
            # this class, we can be reasonably sure it'll work.
            self.__class__.__bases__[1].__setattr__(self, k, v)
        else:
            self.__dict__[k] = v

        self._watchEmitChanged()
