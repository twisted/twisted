# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Unit tests for L{twisted.python.constants}.
"""

from twisted.trial.unittest import TestCase

from twisted.python.constants import NamedConstant, Names, ValueConstant, Values


class NamedConstantTests(TestCase):
    """
    Tests for the L{twisted.python.constants.NamedConstant} class which is used
    to represent individual values.
    """
    def setUp(self):
        """
        Create a dummy container into which constants can be placed.
        """
        class foo(Names):
            pass
        self.container = foo


    def test_name(self):
        """
        The C{name} attribute of a L{NamedConstant} refers to the value passed
        for the C{name} parameter to C{_realize}.
        """
        name = NamedConstant()
        name._realize(self.container, "bar", None)
        self.assertEqual("bar", name.name)


    def test_representation(self):
        """
        The string representation of an instance of L{NamedConstant} includes
        the container the instances belongs to as well as the instance's name.
        """
        name = NamedConstant()
        name._realize(self.container, "bar", None)
        self.assertEqual("<foo=bar>", repr(name))


    def test_equality(self):
        """
        A L{NamedConstant} instance compares equal to itself.
        """
        name = NamedConstant()
        name._realize(self.container, "bar", None)
        self.assertTrue(name == name)
        self.assertFalse(name != name)


    def test_nonequality(self):
        """
        Two different L{NamedConstant} instances do not compare equal to each
        other.
        """
        first = NamedConstant()
        first._realize(self.container, "bar", None)
        second = NamedConstant()
        second._realize(self.container, "bar", None)
        self.assertFalse(first == second)
        self.assertTrue(first != second)


    def test_hash(self):
        """
        Because two different L{NamedConstant} instances do not compare as equal
        to each other, they also have different hashes to avoid collisions when
        added to a C{dict} or C{set}.
        """
        first = NamedConstant()
        first._realize(self.container, "bar", None)
        second = NamedConstant()
        second._realize(self.container, "bar", None)
        self.assertNotEqual(hash(first), hash(second))



class _ConstantsTestsMixin(object):
    """
    Mixin defining test helpers common to multiple types of constants
    collections.
    """
    def _notInstantiableTest(self, name, cls):
        """
        Assert that an attempt to instantiate the constants class raises
        C{TypeError}.

        @param name: A C{str} giving the name of the constants collection.
        @param cls: The constants class to test.
        """
        exc = self.assertRaises(TypeError, cls)
        self.assertEqual(name + " may not be instantiated.", str(exc))



class NamesTests(TestCase, _ConstantsTestsMixin):
    """
    Tests for L{twisted.python.constants.Names}, a base class for containers of
    related constaints.
    """
    def setUp(self):
        """
        Create a fresh new L{Names} subclass for each unit test to use.  Since
        L{Names} is stateful, re-using the same subclass across test methods
        makes exercising all of the implementation code paths difficult.
        """
        class METHOD(Names):
            """
            A container for some named constants to use in unit tests for
            L{Names}.
            """
            GET = NamedConstant()
            PUT = NamedConstant()
            POST = NamedConstant()
            DELETE = NamedConstant()

        self.METHOD = METHOD


    def test_notInstantiable(self):
        """
        A subclass of L{Names} raises C{TypeError} if an attempt is made to
        instantiate it.
        """
        self._notInstantiableTest("METHOD", self.METHOD)


    def test_symbolicAttributes(self):
        """
        Each name associated with a L{NamedConstant} instance in the definition
        of a L{Names} subclass is available as an attribute on the resulting
        class.
        """
        self.assertTrue(hasattr(self.METHOD, "GET"))
        self.assertTrue(hasattr(self.METHOD, "PUT"))
        self.assertTrue(hasattr(self.METHOD, "POST"))
        self.assertTrue(hasattr(self.METHOD, "DELETE"))


    def test_withoutOtherAttributes(self):
        """
        As usual, names not defined in the class scope of a L{Names}
        subclass are not available as attributes on the resulting class.
        """
        self.assertFalse(hasattr(self.METHOD, "foo"))


    def test_representation(self):
        """
        The string representation of a constant on a L{Names} subclass includes
        the name of the L{Names} subclass and the name of the constant itself.
        """
        self.assertEqual("<METHOD=GET>", repr(self.METHOD.GET))


    def test_lookupByName(self):
        """
        Constants can be looked up by name using L{Names.lookupByName}.
        """
        method = self.METHOD.lookupByName("GET")
        self.assertIdentical(self.METHOD.GET, method)


    def test_notLookupMissingByName(self):
        """
        Names not defined with a L{NamedConstant} instance cannot be looked up
        using L{Names.lookupByName}.
        """
        self.assertRaises(ValueError, self.METHOD.lookupByName, "lookupByName")
        self.assertRaises(ValueError, self.METHOD.lookupByName, "__init__")
        self.assertRaises(ValueError, self.METHOD.lookupByName, "foo")


    def test_name(self):
        """
        The C{name} attribute of one of the named constants gives that
        constant's name.
        """
        self.assertEqual("GET", self.METHOD.GET.name)


    def test_attributeIdentity(self):
        """
        Repeated access of an attribute associated with a L{NamedConstant} value
        in a L{Names} subclass results in the same object.
        """
        self.assertIdentical(self.METHOD.GET, self.METHOD.GET)


    def test_iterconstants(self):
        """
        L{Names.iterconstants} returns an iterator over all of the constants
        defined in the class, in the order they were defined.
        """
        constants = list(self.METHOD.iterconstants())
        self.assertEqual(
            [self.METHOD.GET, self.METHOD.PUT,
             self.METHOD.POST, self.METHOD.DELETE],
            constants)


    def test_attributeIterconstantsIdentity(self):
        """
        The constants returned from L{Names.iterconstants} are identical to the
        constants accessible using attributes.
        """
        constants = list(self.METHOD.iterconstants())
        self.assertIdentical(self.METHOD.GET, constants[0])
        self.assertIdentical(self.METHOD.PUT, constants[1])
        self.assertIdentical(self.METHOD.POST, constants[2])
        self.assertIdentical(self.METHOD.DELETE, constants[3])


    def test_iterconstantsIdentity(self):
        """
        The constants returned from L{Names.iterconstants} are identical on each
        call to that method.
        """
        constants = list(self.METHOD.iterconstants())
        again = list(self.METHOD.iterconstants())
        self.assertIdentical(again[0], constants[0])
        self.assertIdentical(again[1], constants[1])
        self.assertIdentical(again[2], constants[2])
        self.assertIdentical(again[3], constants[3])


    def test_initializedOnce(self):
        """
        L{Names._enumerants} is initialized once and its value re-used on
        subsequent access.
        """
        first = self.METHOD._enumerants
        self.METHOD.GET # Side-effects!
        second = self.METHOD._enumerants
        self.assertIdentical(first, second)



class ValuesTests(TestCase, _ConstantsTestsMixin):
    """
    Tests for L{twisted.python.constants.Names}, a base class for containers of
    related constaints with arbitrary values.
    """
    def setUp(self):
        """
        Create a fresh new L{Values} subclass for each unit test to use.  Since
        L{Values} is stateful, re-using the same subclass across test methods
        makes exercising all of the implementation code paths difficult.
        """
        class STATUS(Values):
            OK = ValueConstant("200")
            NOT_FOUND = ValueConstant("404")

        self.STATUS = STATUS


    def test_notInstantiable(self):
        """
        A subclass of L{Values} raises C{TypeError} if an attempt is made to
        instantiate it.
        """
        self._notInstantiableTest("STATUS", self.STATUS)


    def test_symbolicAttributes(self):
        """
        Each name associated with a L{ValueConstant} instance in the definition
        of a L{Values} subclass is available as an attribute on the resulting
        class.
        """
        self.assertTrue(hasattr(self.STATUS, "OK"))
        self.assertTrue(hasattr(self.STATUS, "NOT_FOUND"))


    def test_withoutOtherAttributes(self):
        """
        As usual, names not defined in the class scope of a L{Values}
        subclass are not available as attributes on the resulting class.
        """
        self.assertFalse(hasattr(self.STATUS, "foo"))


    def test_representation(self):
        """
        The string representation of a constant on a L{Values} subclass includes
        the name of the L{Values} subclass and the name of the constant itself.
        """
        self.assertEqual("<STATUS=OK>", repr(self.STATUS.OK))


    def test_lookupByName(self):
        """
        Constants can be looked up by name using L{Values.lookupByName}.
        """
        method = self.STATUS.lookupByName("OK")
        self.assertIdentical(self.STATUS.OK, method)


    def test_notLookupMissingByName(self):
        """
        Names not defined with a L{ValueConstant} instance cannot be looked up
        using L{Values.lookupByName}.
        """
        self.assertRaises(ValueError, self.STATUS.lookupByName, "lookupByName")
        self.assertRaises(ValueError, self.STATUS.lookupByName, "__init__")
        self.assertRaises(ValueError, self.STATUS.lookupByName, "foo")


    def test_lookupByValue(self):
        """
        Constants can be looked up by their associated value, defined by the
        argument passed to L{ValueConstant}, using L{Values.lookupByValue}.
        """
        status = self.STATUS.lookupByValue("200")
        self.assertIdentical(self.STATUS.OK, status)


    def test_lookupDuplicateByValue(self):
        """
        If more than one constant is associated with a particular value,
        L{Values.lookupByValue} returns whichever of them is defined first.
        """
        class TRANSPORT_MESSAGE(Values):
            """
            Message types supported by an SSH transport.
            """
            KEX_DH_GEX_REQUEST_OLD = ValueConstant(30)
            KEXDH_INIT = ValueConstant(30)

        self.assertIdentical(
            TRANSPORT_MESSAGE.lookupByValue(30),
            TRANSPORT_MESSAGE.KEX_DH_GEX_REQUEST_OLD)


    def test_notLookupMissingByValue(self):
        """
        L{Values.lookupByValue} raises L{ValueError} when called with a value
        with which no constant is associated.
        """
        self.assertRaises(ValueError, self.STATUS.lookupByValue, "OK")
        self.assertRaises(ValueError, self.STATUS.lookupByValue, 200)
        self.assertRaises(ValueError, self.STATUS.lookupByValue, "200.1")


    def test_name(self):
        """
        The C{name} attribute of one of the constants gives that constant's
        name.
        """
        self.assertEqual("OK", self.STATUS.OK.name)


    def test_attributeIdentity(self):
        """
        Repeated access of an attribute associated with a L{ValueConstant} value
        in a L{Values} subclass results in the same object.
        """
        self.assertIdentical(self.STATUS.OK, self.STATUS.OK)


    def test_iterconstants(self):
        """
        L{Values.iterconstants} returns an iterator over all of the constants
        defined in the class, in the order they were defined.
        """
        constants = list(self.STATUS.iterconstants())
        self.assertEqual(
            [self.STATUS.OK, self.STATUS.NOT_FOUND],
            constants)


    def test_attributeIterconstantsIdentity(self):
        """
        The constants returned from L{Values.iterconstants} are identical to the
        constants accessible using attributes.
        """
        constants = list(self.STATUS.iterconstants())
        self.assertIdentical(self.STATUS.OK, constants[0])
        self.assertIdentical(self.STATUS.NOT_FOUND, constants[1])


    def test_iterconstantsIdentity(self):
        """
        The constants returned from L{Values.iterconstants} are identical on
        each call to that method.
        """
        constants = list(self.STATUS.iterconstants())
        again = list(self.STATUS.iterconstants())
        self.assertIdentical(again[0], constants[0])
        self.assertIdentical(again[1], constants[1])


    def test_initializedOnce(self):
        """
        L{Values._enumerants} is initialized once and its value re-used on
        subsequent access.
        """
        first = self.STATUS._enumerants
        self.STATUS.OK # Side-effects!
        second = self.STATUS._enumerants
        self.assertIdentical(first, second)
