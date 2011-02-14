# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Test cases for twisted.reflect module.
"""

import weakref, os
from ihooks import ModuleImporter

try:
    from collections import deque
except ImportError:
    deque = None

from twisted.trial import unittest
from twisted.python import reflect, util
from twisted.python.versions import Version



class SettableTest(unittest.TestCase):
    def setUp(self):
        self.setter = reflect.Settable()

    def tearDown(self):
        del self.setter

    def testSet(self):
        self.setter(a=1, b=2)
        self.failUnlessEqual(self.setter.a, 1)
        self.failUnlessEqual(self.setter.b, 2)



class AccessorTester(reflect.Accessor):

    def set_x(self, x):
        self.y = x
        self.reallySet('x', x)


    def get_z(self):
        self.q = 1
        return 1


    def del_z(self):
        self.reallyDel("q")



class PropertyAccessorTester(reflect.PropertyAccessor):
    """
    Test class to check L{reflect.PropertyAccessor} functionalities.
    """
    r = 0

    def set_r(self, r):
        self.s = r


    def set_x(self, x):
        self.y = x
        self.reallySet('x', x)


    def get_z(self):
        self.q = 1
        return 1


    def del_z(self):
        self.reallyDel("q")



class AccessorTest(unittest.TestCase):
    def setUp(self):
        self.tester = AccessorTester()

    def testSet(self):
        self.tester.x = 1
        self.failUnlessEqual(self.tester.x, 1)
        self.failUnlessEqual(self.tester.y, 1)

    def testGet(self):
        self.failUnlessEqual(self.tester.z, 1)
        self.failUnlessEqual(self.tester.q, 1)

    def testDel(self):
        self.tester.z
        self.failUnlessEqual(self.tester.q, 1)
        del self.tester.z
        self.failUnlessEqual(hasattr(self.tester, "q"), 0)
        self.tester.x = 1
        del self.tester.x
        self.failUnlessEqual(hasattr(self.tester, "x"), 0)



class PropertyAccessorTest(AccessorTest):
    """
    Tests for L{reflect.PropertyAccessor}, using L{PropertyAccessorTester}.
    """

    def setUp(self):
        self.tester = PropertyAccessorTester()


    def test_setWithDefaultValue(self):
        """
        If an attribute is present in the class, it can be retrieved by
        default.
        """
        self.assertEquals(self.tester.r, 0)
        self.tester.r = 1
        self.assertEquals(self.tester.r, 0)
        self.assertEquals(self.tester.s, 1)


    def test_getValueInDict(self):
        """
        The attribute value can be overriden by directly modifying the value in
        C{__dict__}.
        """
        self.tester.__dict__["r"] = 10
        self.assertEquals(self.tester.r, 10)


    def test_notYetInDict(self):
        """
        If a getter is defined on an attribute but without any default value,
        it raises C{AttributeError} when trying to access it.
        """
        self.assertRaises(AttributeError, getattr, self.tester, "x")



class LookupsTestCase(unittest.TestCase):
    """
    Tests for L{namedClass}, L{namedModule}, and L{namedAny}.
    """

    def test_namedClassLookup(self):
        """
        L{namedClass} should return the class object for the name it is passed.
        """
        self.assertIdentical(
            reflect.namedClass("twisted.python.reflect.Summer"),
            reflect.Summer)


    def test_namedModuleLookup(self):
        """
        L{namedModule} should return the module object for the name it is
        passed.
        """
        self.assertIdentical(
            reflect.namedModule("twisted.python.reflect"), reflect)


    def test_namedAnyPackageLookup(self):
        """
        L{namedAny} should return the package object for the name it is passed.
        """
        import twisted.python
        self.assertIdentical(
            reflect.namedAny("twisted.python"), twisted.python)

    def test_namedAnyModuleLookup(self):
        """
        L{namedAny} should return the module object for the name it is passed.
        """
        self.assertIdentical(
            reflect.namedAny("twisted.python.reflect"), reflect)


    def test_namedAnyClassLookup(self):
        """
        L{namedAny} should return the class object for the name it is passed.
        """
        self.assertIdentical(
            reflect.namedAny("twisted.python.reflect.Summer"), reflect.Summer)


    def test_namedAnyAttributeLookup(self):
        """
        L{namedAny} should return the object an attribute of a non-module,
        non-package object is bound to for the name it is passed.
        """
        # Note - not assertEqual because unbound method lookup creates a new
        # object every time.  This is a foolishness of Python's object
        # implementation, not a bug in Twisted.
        self.assertEqual(
            reflect.namedAny("twisted.python.reflect.Summer.reallySet"),
            reflect.Summer.reallySet)


    def test_namedAnySecondAttributeLookup(self):
        """
        L{namedAny} should return the object an attribute of an object which
        itself was an attribute of a non-module, non-package object is bound to
        for the name it is passed.
        """
        self.assertIdentical(
            reflect.namedAny(
                "twisted.python.reflect.Summer.reallySet.__doc__"),
            reflect.Summer.reallySet.__doc__)


    def test_importExceptions(self):
        """
        Exceptions raised by modules which L{namedAny} causes to be imported
        should pass through L{namedAny} to the caller.
        """
        self.assertRaises(
            ZeroDivisionError,
            reflect.namedAny, "twisted.test.reflect_helper_ZDE")
        # Make sure that this behavior is *consistent* for 2.3, where there is
        # no post-failed-import cleanup
        self.assertRaises(
            ZeroDivisionError,
            reflect.namedAny, "twisted.test.reflect_helper_ZDE")
        self.assertRaises(
            ValueError,
            reflect.namedAny, "twisted.test.reflect_helper_VE")
        # Modules which themselves raise ImportError when imported should result in an ImportError
        self.assertRaises(
            ImportError,
            reflect.namedAny, "twisted.test.reflect_helper_IE")


    def test_attributeExceptions(self):
        """
        If segments on the end of a fully-qualified Python name represents
        attributes which aren't actually present on the object represented by
        the earlier segments, L{namedAny} should raise an L{AttributeError}.
        """
        self.assertRaises(
            AttributeError,
            reflect.namedAny, "twisted.nosuchmoduleintheworld")
        # ImportError behaves somewhat differently between "import
        # extant.nonextant" and "import extant.nonextant.nonextant", so test
        # the latter as well.
        self.assertRaises(
            AttributeError,
            reflect.namedAny, "twisted.nosuch.modulein.theworld")
        self.assertRaises(
            AttributeError,
            reflect.namedAny, "twisted.python.reflect.Summer.nosuchattributeintheworld")


    def test_invalidNames(self):
        """
        Passing a name which isn't a fully-qualified Python name to L{namedAny}
        should result in one of the following exceptions:
        - L{InvalidName}: the name is not a dot-separated list of Python objects
        - L{ObjectNotFound}: the object doesn't exist
        - L{ModuleNotFound}: the object doesn't exist and there is only one
          component in the name
        """
        err = self.assertRaises(reflect.ModuleNotFound, reflect.namedAny,
                                'nosuchmoduleintheworld')
        self.assertEqual(str(err), "No module named 'nosuchmoduleintheworld'")

        # This is a dot-separated list, but it isn't valid!
        err = self.assertRaises(reflect.ObjectNotFound, reflect.namedAny,
                                "@#$@(#.!@(#!@#")
        self.assertEqual(str(err), "'@#$@(#.!@(#!@#' does not name an object")

        err = self.assertRaises(reflect.ObjectNotFound, reflect.namedAny,
                                "tcelfer.nohtyp.detsiwt")
        self.assertEqual(
            str(err),
            "'tcelfer.nohtyp.detsiwt' does not name an object")

        err = self.assertRaises(reflect.InvalidName, reflect.namedAny, '')
        self.assertEqual(str(err), 'Empty module name')

        for invalidName in ['.twisted', 'twisted.', 'twisted..python']:
            err = self.assertRaises(
                reflect.InvalidName, reflect.namedAny, invalidName)
            self.assertEqual(
                str(err),
                "name must be a string giving a '.'-separated list of Python "
                "identifiers, not %r" % (invalidName,))



class ImportHooksLookupTests(LookupsTestCase):
    """
    Tests for lookup methods in the presence of L{ihooks}-style import hooks.
    Runs all of the tests from L{LookupsTestCase} after installing a custom
    import hook.
    """
    def setUp(self):
        """
        Perturb the normal import behavior subtly by installing an import
        hook.  No custom behavior is provided, but this adds some extra
        frames to the call stack, which L{namedAny} must be able to account
        for.
        """
        self.importer = ModuleImporter()
        self.importer.install()


    def tearDown(self):
        """
        Uninstall the custom import hook.
        """
        self.importer.uninstall()



class ObjectGrep(unittest.TestCase):
    def test_dictionary(self):
        """
        Test references search through a dictionnary, as a key or as a value.
        """
        o = object()
        d1 = {None: o}
        d2 = {o: None}

        self.assertIn("[None]", reflect.objgrep(d1, o, reflect.isSame))
        self.assertIn("{None}", reflect.objgrep(d2, o, reflect.isSame))

    def test_list(self):
        """
        Test references search through a list.
        """
        o = object()
        L = [None, o]

        self.assertIn("[1]", reflect.objgrep(L, o, reflect.isSame))

    def test_tuple(self):
        """
        Test references search through a tuple.
        """
        o = object()
        T = (o, None)

        self.assertIn("[0]", reflect.objgrep(T, o, reflect.isSame))

    def test_instance(self):
        """
        Test references search through an object attribute.
        """
        class Dummy:
            pass
        o = object()
        d = Dummy()
        d.o = o

        self.assertIn(".o", reflect.objgrep(d, o, reflect.isSame))

    def test_weakref(self):
        """
        Test references search through a weakref object.
        """
        class Dummy:
            pass
        o = Dummy()
        w1 = weakref.ref(o)

        self.assertIn("()", reflect.objgrep(w1, o, reflect.isSame))

    def test_boundMethod(self):
        """
        Test references search through method special attributes.
        """
        class Dummy:
            def dummy(self):
                pass
        o = Dummy()
        m = o.dummy

        self.assertIn(".im_self", reflect.objgrep(m, m.im_self, reflect.isSame))
        self.assertIn(".im_class", reflect.objgrep(m, m.im_class, reflect.isSame))
        self.assertIn(".im_func", reflect.objgrep(m, m.im_func, reflect.isSame))

    def test_everything(self):
        """
        Test references search using complex set of objects.
        """
        class Dummy:
            def method(self):
                pass

        o = Dummy()
        D1 = {(): "baz", None: "Quux", o: "Foosh"}
        L = [None, (), D1, 3]
        T = (L, {}, Dummy())
        D2 = {0: "foo", 1: "bar", 2: T}
        i = Dummy()
        i.attr = D2
        m = i.method
        w = weakref.ref(m)

        self.assertIn("().im_self.attr[2][0][2]{'Foosh'}", reflect.objgrep(w, o, reflect.isSame))

    def test_depthLimit(self):
        """
        Test the depth of references search.
        """
        a = []
        b = [a]
        c = [a, b]
        d = [a, c]

        self.assertEquals(['[0]'], reflect.objgrep(d, a, reflect.isSame, maxDepth=1))
        self.assertEquals(['[0]', '[1][0]'], reflect.objgrep(d, a, reflect.isSame, maxDepth=2))
        self.assertEquals(['[0]', '[1][0]', '[1][1][0]'], reflect.objgrep(d, a, reflect.isSame, maxDepth=3))

    def test_deque(self):
        """
        Test references search through a deque object. Only for Python > 2.3.
        """
        o = object()
        D = deque()
        D.append(None)
        D.append(o)

        self.assertIn("[1]", reflect.objgrep(D, o, reflect.isSame))

    if deque is None:
        test_deque.skip = "Deque not available"


class GetClass(unittest.TestCase):
    def testOld(self):
        class OldClass:
            pass
        old = OldClass()
        self.assertIn(reflect.getClass(OldClass).__name__, ('class', 'classobj'))
        self.assertEquals(reflect.getClass(old).__name__, 'OldClass')

    def testNew(self):
        class NewClass(object):
            pass
        new = NewClass()
        self.assertEquals(reflect.getClass(NewClass).__name__, 'type')
        self.assertEquals(reflect.getClass(new).__name__, 'NewClass')



class Breakable(object):

    breakRepr = False
    breakStr = False

    def __str__(self):
        if self.breakStr:
            raise RuntimeError("str!")
        else:
            return '<Breakable>'

    def __repr__(self):
        if self.breakRepr:
            raise RuntimeError("repr!")
        else:
            return 'Breakable()'



class BrokenType(Breakable, type):
    breakName = False

    def get___name__(self):
        if self.breakName:
            raise RuntimeError("no name")
        return 'BrokenType'
    __name__ = property(get___name__)



class BTBase(Breakable):
    __metaclass__ = BrokenType
    breakRepr = True
    breakStr = True



class NoClassAttr(Breakable):
    __class__ = property(lambda x: x.not_class)



class SafeRepr(unittest.TestCase):
    """
    Tests for L{reflect.safe_repr} function.
    """

    def test_workingRepr(self):
        """
        L{reflect.safe_repr} produces the same output as C{repr} on a working
        object.
        """
        x = [1, 2, 3]
        self.assertEquals(reflect.safe_repr(x), repr(x))


    def test_brokenRepr(self):
        """
        L{reflect.safe_repr} returns a string with class name, address, and
        traceback when the repr call failed.
        """
        b = Breakable()
        b.breakRepr = True
        bRepr = reflect.safe_repr(b)
        self.assertIn("Breakable instance at 0x", bRepr)
        # Check that the file is in the repr, but without the extension as it
        # can be .py/.pyc
        self.assertIn(os.path.splitext(__file__)[0], bRepr)
        self.assertIn("RuntimeError: repr!", bRepr)


    def test_brokenStr(self):
        """
        L{reflect.safe_repr} isn't affected by a broken C{__str__} method.
        """
        b = Breakable()
        b.breakStr = True
        self.assertEquals(reflect.safe_repr(b), repr(b))


    def test_brokenClassRepr(self):
        class X(BTBase):
            breakRepr = True
        reflect.safe_repr(X)
        reflect.safe_repr(X())


    def test_unsignedID(self):
        """
        L{unsignedID} is used to print ID of the object in case of error, not
        standard ID value which can be negative.
        """
        class X(BTBase):
            breakRepr = True

        ids = {X: 100}
        def fakeID(obj):
            try:
                return ids[obj]
            except (TypeError, KeyError):
                return id(obj)
        self.addCleanup(util.setIDFunction, util.setIDFunction(fakeID))

        xRepr = reflect.safe_repr(X)
        self.assertIn("0x64", xRepr)


    def test_brokenClassStr(self):
        class X(BTBase):
            breakStr = True
        reflect.safe_repr(X)
        reflect.safe_repr(X())


    def test_brokenClassAttribute(self):
        """
        If an object raises an exception when accessing its C{__class__}
        attribute, L{reflect.safe_repr} uses C{type} to retrieve the class
        object.
        """
        b = NoClassAttr()
        b.breakRepr = True
        bRepr = reflect.safe_repr(b)
        self.assertIn("NoClassAttr instance at 0x", bRepr)
        self.assertIn(os.path.splitext(__file__)[0], bRepr)
        self.assertIn("RuntimeError: repr!", bRepr)


    def test_brokenClassNameAttribute(self):
        """
        If a class raises an exception when accessing its C{__name__} attribute
        B{and} when calling its C{__str__} implementation, L{reflect.safe_repr}
        returns 'BROKEN CLASS' instead of the class name.
        """
        class X(BTBase):
            breakName = True
        xRepr = reflect.safe_repr(X())
        self.assertIn("<BROKEN CLASS AT 0x", xRepr)
        self.assertIn(os.path.splitext(__file__)[0], xRepr)
        self.assertIn("RuntimeError: repr!", xRepr)



class SafeStr(unittest.TestCase):
    """
    Tests for L{reflect.safe_str} function.
    """

    def test_workingStr(self):
        x = [1, 2, 3]
        self.assertEquals(reflect.safe_str(x), str(x))


    def test_brokenStr(self):
        b = Breakable()
        b.breakStr = True
        reflect.safe_str(b)


    def test_brokenRepr(self):
        b = Breakable()
        b.breakRepr = True
        reflect.safe_str(b)


    def test_brokenClassStr(self):
        class X(BTBase):
            breakStr = True
        reflect.safe_str(X)
        reflect.safe_str(X())


    def test_brokenClassRepr(self):
        class X(BTBase):
            breakRepr = True
        reflect.safe_str(X)
        reflect.safe_str(X())


    def test_brokenClassAttribute(self):
        """
        If an object raises an exception when accessing its C{__class__}
        attribute, L{reflect.safe_str} uses C{type} to retrieve the class
        object.
        """
        b = NoClassAttr()
        b.breakStr = True
        bStr = reflect.safe_str(b)
        self.assertIn("NoClassAttr instance at 0x", bStr)
        self.assertIn(os.path.splitext(__file__)[0], bStr)
        self.assertIn("RuntimeError: str!", bStr)


    def test_brokenClassNameAttribute(self):
        """
        If a class raises an exception when accessing its C{__name__} attribute
        B{and} when calling its C{__str__} implementation, L{reflect.safe_str}
        returns 'BROKEN CLASS' instead of the class name.
        """
        class X(BTBase):
            breakName = True
        xStr = reflect.safe_str(X())
        self.assertIn("<BROKEN CLASS AT 0x", xStr)
        self.assertIn(os.path.splitext(__file__)[0], xStr)
        self.assertIn("RuntimeError: str!", xStr)



class FilenameToModule(unittest.TestCase):
    """
    Test L{reflect.filenameToModuleName} detection.
    """
    def test_directory(self):
        """
        Tests it finds good name for directories/packages.
        """
        module = reflect.filenameToModuleName(os.path.join('twisted', 'test'))
        self.assertEquals(module, 'test')
        module = reflect.filenameToModuleName(os.path.join('twisted', 'test')
                                              + os.path.sep)
        self.assertEquals(module, 'test')

    def test_file(self):
        """
        Test it finds good name for files.
        """
        module = reflect.filenameToModuleName(
            os.path.join('twisted', 'test', 'test_reflect.py'))
        self.assertEquals(module, 'test_reflect')



class FullyQualifiedNameTests(unittest.TestCase):
    """
    Test for L{reflect.fullyQualifiedName}.
    """

    def _checkFullyQualifiedName(self, obj, expected):
        """
        Helper to check that fully qualified name of C{obj} results to
        C{expected}.
        """
        self.assertEquals(
            reflect.fullyQualifiedName(obj), expected)


    def test_package(self):
        """
        L{reflect.fullyQualifiedName} returns the full name of a package and
        a subpackage.
        """
        import twisted
        self._checkFullyQualifiedName(twisted, 'twisted')
        import twisted.python
        self._checkFullyQualifiedName(twisted.python, 'twisted.python')


    def test_module(self):
        """
        L{reflect.fullyQualifiedName} returns the name of a module inside a a
        package.
        """
        self._checkFullyQualifiedName(reflect, 'twisted.python.reflect')
        import twisted.trial.unittest
        self._checkFullyQualifiedName(twisted.trial.unittest,
                                      'twisted.trial.unittest')


    def test_class(self):
        """
        L{reflect.fullyQualifiedName} returns the name of a class and its
        module.
        """
        self._checkFullyQualifiedName(reflect.Settable,
                                      'twisted.python.reflect.Settable')


    def test_function(self):
        """
        L{reflect.fullyQualifiedName} returns the name of a function inside its
        module.
        """
        self._checkFullyQualifiedName(reflect.fullyQualifiedName,
            "twisted.python.reflect.fullyQualifiedName")


    def test_method(self):
        """
        L{reflect.fullyQualifiedName} returns the name of a method inside its
        class and its module.
        """
        self._checkFullyQualifiedName(reflect.PropertyAccessor.reallyDel,
            "twisted.python.reflect.PropertyAccessor.reallyDel")
        self._checkFullyQualifiedName(reflect.PropertyAccessor().reallyDel,
            "twisted.python.reflect.PropertyAccessor.reallyDel")


class DeprecationTestCase(unittest.TestCase):
    """
    Test deprecations in twisted.python.reflect
    """

    def test_macro(self):
        """
        Test deprecation of L{reflect.macro}.
        """
        result = self.callDeprecated(Version("Twisted", 8, 2, 0),
            reflect.macro, "test", __file__, "test = 1")
        self.assertEquals(result, 1)
