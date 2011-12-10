# -*- test-case-name: twisted.python.test.test_constants -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Symbolic constant support, including collections and constants with text,
numeric, and bit flag values.
"""

__all__ = ['NamedConstant', 'ValueConstant', 'Names', 'Values']

from itertools import count


_unspecified = object()
_constantOrder = count().next


class _Constant(object):
    """
    @ivar _index: A C{int} allocated from a shared counter in order to keep
        track of the order in which L{_Constant}s are instantiated.

    @ivar name: A C{str} giving the name of this constant; only set once the
        constant is initialized by L{_ConstantsContainer}.

    @ivar _container: The L{_ConstantsContainer} subclass this constant belongs
        to; only set once the constant is initialized by that subclass.
    """
    def __init__(self):
        self._index = _constantOrder()


    def __get__(self, oself, cls):
        """
        Ensure this constant has been initialized before returning it.
        """
        cls._initializeEnumerants()
        return self


    def __repr__(self):
        """
        Return text identifying both which constant this is and which collection
        it belongs to.
        """
        return "<%s=%s>" % (self._container.__name__, self.name)


    def _realize(self, container, name, value):
        """
        Complete the initialization of this L{_Constant}.

        @param container: The L{_ConstantsContainer} subclass this constant is
            part of.

        @param name: The name of this constant in its container.

        @param value: The value of this constant; not used, as named constants
            have no value apart from their identity.
        """
        self._container = container
        self.name = name



class _EnumerantsInitializer(object):
    """
    L{_EnumerantsInitializer} is a descriptor used to initialize a cache of
    objects representing named constants for a particular L{_ConstantsContainer}
    subclass.
    """
    def __get__(self, oself, cls):
        """
        Trigger the initialization of the enumerants cache on C{cls} and then
        return it.
        """
        cls._initializeEnumerants()
        return cls._enumerants



class _ConstantsContainer(object):
    """
    L{_ConstantsContainer} is a class with attributes used as symbolic
    constants.  It is up to subclasses to specify what kind of constants are
    allowed.

    @cvar _constantType: Specified by a L{_ConstantsContainer} subclass to
        specify the type of constants allowed by that subclass.

    @cvar _enumerantsInitialized: A C{bool} tracking whether C{_enumerants} has
        been initialized yet or not.

    @cvar _enumerants: A C{dict} mapping the names of constants (eg
        L{NamedConstant} instances) found in the class definition to those
        instances.  This is initialized via the L{_EnumerantsInitializer}
        descriptor the first time it is accessed.
    """
    _constantType = None

    _enumerantsInitialized = False
    _enumerants = _EnumerantsInitializer()

    def __new__(cls):
        """
        Classes representing constants containers are not intended to be
        instantiated.

        The class object itself is used directly.
        """
        raise TypeError("%s may not be instantiated." % (cls.__name__,))


    def _initializeEnumerants(cls):
        """
        Find all of the L{NamedConstant} instances in the definition of C{cls},
        initialize them with constant values, and build a mapping from their
        names to them to attach to C{cls}.
        """
        if not cls._enumerantsInitialized:
            constants = []
            for (name, descriptor) in cls.__dict__.iteritems():
                if isinstance(descriptor, cls._constantType):
                    constants.append((descriptor._index, name, descriptor))
            enumerants = {}
            for (index, enumerant, descriptor) in constants:
                value = cls._constantFactory(enumerant)
                descriptor._realize(cls, enumerant, value)
                enumerants[enumerant] = descriptor
            # Replace the _enumerants descriptor with the result so future
            # access will go directly to the values.  The _enumerantsInitialized
            # flag is still necessary because NamedConstant.__get__ may also
            # call this method.
            cls._enumerants = enumerants
            cls._enumerantsInitialized = True
    _initializeEnumerants = classmethod(_initializeEnumerants)


    def _constantFactory(cls, name):
        """
        Construct the value for a new constant to add to this container.

        @param name: The name of the constant to create.

        @return: L{NamedConstant} instances have no value apart from identity,
            so return a meaningless dummy value.
        """
        return _unspecified
    _constantFactory = classmethod(_constantFactory)


    def lookupByName(cls, name):
        """
        Retrieve a constant by its name or raise a C{ValueError} if there is no
        constant associated with that name.

        @param name: A C{str} giving the name of one of the constants defined by
            C{cls}.

        @raise ValueError: If C{name} is not the name of one of the constants
            defined by C{cls}.

        @return: The L{NamedConstant} associated with C{name}.
        """
        if name in cls._enumerants:
            return getattr(cls, name)
        raise ValueError(name)
    lookupByName = classmethod(lookupByName)


    def iterconstants(cls):
        """
        Iteration over a L{Names} subclass results in all of the constants it
        contains.

        @return: an iterator the elements of which are the L{NamedConstant}
            instances defined in the body of this L{Names} subclass.
        """
        constants = cls._enumerants.values()
        constants.sort(key=lambda descriptor: descriptor._index)
        return iter(constants)
    iterconstants = classmethod(iterconstants)



class NamedConstant(_Constant):
    """
    L{NamedConstant} defines an attribute to be a named constant within a
    collection defined by a L{Names} subclass.

    L{NamedConstant} is only for use in the definition of L{Names}
    subclasses.  Do not instantiate L{NamedConstant} elsewhere and do not
    subclass it.
    """



class Names(_ConstantsContainer):
    """
    A L{Names} subclass contains constants which differ only in their names and
    identities.
    """
    _constantType = NamedConstant



class ValueConstant(_Constant):
    """
    L{ValueConstant} defines an attribute to be a named constant within a
    collection defined by a L{Values} subclass.

    L{ValueConstant} is only for use in the definition of L{Values} subclasses.
    Do not instantiate L{ValueConstant} elsewhere and do not subclass it.
    """
    def __init__(self, value):
        _Constant.__init__(self)
        self.value = value



class Values(_ConstantsContainer):
    """
    A L{Values} subclass contains constants which are associated with arbitrary
    values.
    """
    _constantType = ValueConstant

    def lookupByValue(cls, value):
        """
        Retrieve a constant by its value or raise a C{ValueError} if there is no
        constant associated with that value.

        @param value: The value of one of the constants defined by C{cls}.

        @raise ValueError: If C{value} is not the value of one of the constants
            defined by C{cls}.

        @return: The L{ValueConstant} associated with C{value}.
        """
        for constant in cls.iterconstants():
            if constant.value == value:
                return constant
        raise ValueError(value)
    lookupByValue = classmethod(lookupByValue)
