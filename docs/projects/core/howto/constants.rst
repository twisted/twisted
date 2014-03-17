
:LastChangedDate: $LastChangedDate$
:LastChangedRevision: $LastChangedRevision$
:LastChangedBy: $LastChangedBy$


Symbolic Constants
==================


Overview
--------

It is often useful to define names which will be treated as constants.
:api:`twisted.python.constants <twisted.python.constants>` provides APIs for defining such symbolic constants with minimal overhead and some useful features beyond those afforded by the common Python idioms for this task.

This document will explain how to use these APIs and what circumstances they might be helpful in.


Constant Names
--------------

Constants which have no value apart from their name and identity can be defined by subclassing :api:`twisted.python.constants.Names <Names>` .
Consider this example, in which some HTTP request method constants are defined.

.. code-block:: python

    from twisted.python.constants import NamedConstant, Names
    class METHOD(Names):
        """
        Constants representing various HTTP request methods.
        """
        GET = NamedConstant()
        PUT = NamedConstant()
        POST = NamedConstant()
        DELETE = NamedConstant()

Only direct subclasses of ``Names`` are supported (i.e., you cannot subclass ``METHOD`` to add new constants the collection).

Given this definition, constants can be looked up by name using attribute access on the ``METHOD`` object:

.. code-block:: console

    >>> METHOD.GET
    <METHOD=GET>
    >>> METHOD.PUT
    <METHOD=PUT>
    >>>

If it's necessary to look up constants from a string (e.g. based on user input of some sort), a safe way to do it is using ``lookupByName`` :

.. code-block:: console

    >>> METHOD.lookupByName('GET')
    <METHOD=GET>
    >>> METHOD.lookupByName('__doc__')
    Traceback (most recent call last):
      File "<stdin>", line 1, in <module>
      File "twisted/python/constants.py", line 145, in lookupByName
        raise ValueError(name)
    ValueError: __doc__
    >>>

As demonstrated, it is safe because any name not associated with a constant (even those special names initialized by Python itself) will result in ``ValueError`` being raised, not some other object not intended to be used the way the constants are used.

The constants can also be enumerated using the ``iterconstants`` method:

.. code-block:: console

    >>> list(METHOD.iterconstants())
    [<METHOD=GET>, <METHOD=PUT>, <METHOD=POST>, <METHOD=DELETE>]
    >>>

Constants can be compared for equality or identity:

.. code-block:: console

    >>> METHOD.GET is METHOD.GET
    True
    >>> METHOD.GET == METHOD.GET
    True
    >>> METHOD.GET is METHOD.PUT
    False
    >>> METHOD.GET == METHOD.PUT
    False
    >>>

Ordered comparisons (and therefore sorting) also work.
The order is defined to be the same as the instantiation order of the constants:

.. code-block:: python

    >>> from twisted.python.constants import NamedConstant, Names
    >>> class Letters(Names):
    ...   a = NamedConstant()
    ...   b = NamedConstant()
    ...   c = NamedConstant()
    ... 
    >>> Letters.a < Letters.b < Letters.c
    True
    >>> Letters.a > Letters.b 
    False
    >>> sorted([Letters.b, Letters.a, Letters.c])
    [<Letters=a>, <Letters=b>, <Letters=c>]
    >>> 

A subclass of ``Names`` may define class methods to implement custom functionality.
Consider this definition of ``METHOD`` :

.. code-block:: python

    from twisted.python.constants import NamedConstant, Names
    class METHOD(Names):
        """
        Constants representing various HTTP request methods.
        """
        GET = NamedConstant()
        PUT = NamedConstant()
        POST = NamedConstant()
        DELETE = NamedConstant()
    
        @classmethod
        def isIdempotent(cls, method):
            """
            Return True if the given method is side-effect free, False otherwise.
            """
            return method is cls.GET

This functionality can be used as any class methods are used:

.. code-block:: console

    >>> METHOD.isIdempotent(METHOD.GET)
    True
    >>> METHOD.isIdempotent(METHOD.POST)
    False
    >>>


Constants With Values
---------------------

Constants with a particular associated value are supported by the :api:`twisted.python.constants.Values <Values>` base class.
Consider this example, in which some HTTP status code constants are defined.

.. code-block:: python

    from twisted.python.constants import ValueConstant, Values
    class STATUS(Values):
        """
        Constants representing various HTTP status codes.
        """
        OK = ValueConstant("200")
        FOUND = ValueConstant("302")
        NOT_FOUND = ValueConstant("404")

As with ``Names`` , constants are accessed as attributes of the class object:

.. code-block:: console

    >>> STATUS.OK
    <STATUS=OK>
    >>> STATUS.FOUND
    <STATUS=FOUND>
    >>>

Additionally, the values of the constants can be accessed using the ``value`` attribute of one these objects:

.. code-block:: console

    >>> STATUS.OK.value
    '200'
    >>>

As with ``Names`` , constants can be looked up by name:

.. code-block:: console

    >>> STATUS.lookupByName('NOT_FOUND')
    <STATUS=NOT_FOUND>
    >>>

Constants on a ``Values`` subclass can also be looked up by value:

.. code-block:: console

    >>> STATUS.lookupByValue('404')
    <STATUS=NOT_FOUND>
    >>> STATUS.lookupByValue('500')
    Traceback (most recent call last):
      File "<stdin>", line 1, in <module>
      File "twisted/python/constants.py", line 244, in lookupByValue
          raise ValueError(value)
    ValueError: 500
    >>>

Multiple constants may have the same value.
If they do, ``lookupByValue`` will find the one which is defined first.

Iteration is also supported:

.. code-block:: console

    >>> list(STATUS.iterconstants())
    [<STATUS=OK>, <STATUS=FOUND>, <STATUS=NOT_FOUND>]
    >>>

Constants can be compared for equality, identity and ordering:

.. code-block:: console

    >>> STATUS.OK == STATUS.OK
    True
    >>> STATUS.OK is STATUS.OK
    True
    >>> STATUS.OK is STATUS.NOT_FOUND
    False
    >>> STATUS.OK == STATUS.NOT_FOUND
    False
    >>> STATUS.NOT_FOUND > STATUS.OK
    True
    >>> STATUS.FOUND < STATUS.OK
    False
    >>>

Note that like ``Names`` , ``Values`` are ordered by instantiation order, not by value, though either order is the same in the above example.

As with ``Names`` , a subclass of ``Values`` can define custom methods:

.. code-block:: python

    from twisted.python.constants import ValueConstant, Values
    class STATUS(Values):
        """
        Constants representing various HTTP status codes.
        """
        OK = ValueConstant("200")
        NO_CONTENT = ValueConstant("204")
        NOT_MODIFIED = ValueConstant("304")
        NOT_FOUND = ValueConstant("404")
    
        @classmethod
        def hasBody(cls, status):
            """
            Return True if the given status is associated with a response body,
            False otherwise.
            """
            return status not in (cls.NO_CONTENT, cls.NOT_MODIFIED)

This functionality can be used as any class methods are used:

.. code-block:: console

    >>> STATUS.hasBody(STATUS.OK)
    True
    >>> STATUS.hasBody(STATUS.NO_CONTENT)
    False
    >>>


Constants As Flags
------------------
  
Integers are often used as a simple set for constants.
The values for these constants are assigned as powers of two so that bits in the integer can be set to represent them.
Individual bits are often called *flags* .
:api:`twisted.python.constants.Flags <Flags>` supports this use-case, including allowing constants with particular bits to be set, for interoperability with other tools.

POSIX filesystem access control is traditionally done using a bitvector defining which users and groups may perform which operations on a file.
This state might be represented using ``Flags`` as follows:

.. code-block:: python

    from twisted.python.constants import FlagConstant, Flags
    class Permission(Flags):
        """
        Constants representing user, group, and other access bits for reading,
        writing, and execution.
        """
        OTHER_EXECUTE = FlagConstant()
        OTHER_WRITE = FlagConstant()
        OTHER_READ = FlagConstant()
        GROUP_EXECUTE = FlagConstant()
        GROUP_WRITE = FlagConstant()
        GROUP_READ = FlagConstant()
        USER_EXECUTE = FlagConstant()
        USER_WRITE = FlagConstant()
        USER_READ = FlagConstant()

As for the previous types of constants, these can be accessed as attributes of the class object:

.. code-block:: console

    >>> Permission.USER_READ
    <Permission=USER_READ>
    >>> Permission.USER_WRITE
    <Permission=USER_WRITE>
    >>> Permission.USER_EXECUTE
    <Permission=USER_EXECUTE>
    >>>

These constant objects also have a ``value`` attribute giving their integer value:

.. code-block:: console

    >>> Permission.USER_READ.value
    256
    >>>

These constants can be looked up by name or value:

.. code-block:: console

    >>> Permission.lookupByName('USER_READ') is Permission.USER_READ
    True
    >>> Permission.lookupByValue(256) is Permission.USER_READ
    True
    >>>

Constants can also be combined using the logical operators ``&`` (*and* ), ``|`` (*or* ), and ``^`` (*exclusive or* ).

.. code-block:: console

    >>> Permission.USER_READ | Permission.USER_WRITE
    <Permission={USER_READ,USER_WRITE}>
    >>> (Permission.USER_READ | Permission.USER_WRITE) & Permission.USER_WRITE
    <Permission=USER_WRITE>
    >>> (Permission.USER_READ | Permission.USER_WRITE) ^ Permission.USER_WRITE
    <Permission=USER_READ>
    >>>

These combined constants can be deconstructed via iteration:

.. code-block:: console

    >>> mode = Permission.USER_READ | Permission.USER_WRITE
    >>> list(mode)
    [<Permission=USER_READ>, <Permission=USER_WRITE>]
    >>> Permission.USER_READ in mode
    True
    >>> Permission.USER_EXECUTE in mode
    False
    >>>

They can also be inspected via boolean operations:

.. code-block:: console

    >>> Permission.USER_READ & mode
    <Permission=USER_READ>
    >>> bool(Permission.USER_READ & mode)
    True
    >>> Permission.USER_EXECUTE & mode
    <Permission={}>
    >>> bool(Permission.USER_EXECUTE & mode)
    False
    >>>

The unary operator ``~`` (*not* ) is also defined:

.. code-block:: console

    >>> ~Permission.USER_READ
    <Permission={GROUP_EXECUTE,GROUP_READ,GROUP_WRITE,OTHER_EXECUTE,OTHER_READ,OTHER_WRITE,USER_EXECUTE,USER_WRITE}>
    >>>

Constants created using these operators also have a ``value`` attribute.

.. code-block:: console

    >>> (~Permission.USER_WRITE).value
    383
    >>>

Note the care taken to ensure the ``~`` operator is applied first and the ``value`` attribute is looked up second.

A ``Flags`` subclass can also define methods, just as a ``Names`` or ``Values`` subclass may.
For example, ``Permission`` might benefit from a method to format a flag as a string in the traditional style.
Consider this addition to that class:

.. code-block:: python

    from twisted.python import filepath
    from twisted.python.constants import FlagConstant, Flags
    class Permission(Flags):
        ...
    
        @classmethod
        def format(cls, permissions):
            """
            Format permissions flags in the traditional 'rwxr-xr-x' style.
            """
            return filepath.Permissions(permissions.value).shorthand()

Use this like any other class method:

.. code-block:: console

    >>> Permission.format(Permission.USER_READ | Permission.USER_WRITE | Permission.GROUP_READ | Permission.OTHER_READ)
    'rw-r--r--'
    >>>
