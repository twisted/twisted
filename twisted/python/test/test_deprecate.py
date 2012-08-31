# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for Twisted's deprecation framework, L{twisted.python.deprecate}.
"""

import sys, types, warnings
from os.path import normcase

from twisted.python import deprecate
from twisted.python.deprecate import _getDeprecationWarningString
from twisted.python.deprecate import DEPRECATION_WARNING_FORMAT
from twisted.python.versions import Version
from twisted.python.filepath import FilePath

from twisted.python.test import deprecatedattributes
from twisted.python.test.modules_helpers import TwistedModulesTestCase

from twisted.trial.unittest import TestCase


class _MockDeprecatedAttribute(object):
    """
    Mock of L{twisted.python.deprecate._DeprecatedAttribute}.

    @ivar value: The value of the attribute.
    """
    def __init__(self, value):
        self.value = value


    def get(self):
        """
        Get a known value.
        """
        return self.value



class ModuleProxyTests(TestCase):
    """
    Tests for L{twisted.python.deprecate._ModuleProxy}, which proxies
    access to module-level attributes, intercepting access to deprecated
    attributes and passing through access to normal attributes.
    """
    def _makeProxy(self, **attrs):
        """
        Create a temporary module proxy object.

        @param **kw: Attributes to initialise on the temporary module object

        @rtype: L{twistd.python.deprecate._ModuleProxy}
        """
        mod = types.ModuleType('foo')
        for key, value in attrs.iteritems():
            setattr(mod, key, value)
        return deprecate._ModuleProxy(mod)


    def test_getattrPassthrough(self):
        """
        Getting a normal attribute on a L{twisted.python.deprecate._ModuleProxy}
        retrieves the underlying attribute's value, and raises C{AttributeError}
        if a non-existant attribute is accessed.
        """
        proxy = self._makeProxy(SOME_ATTRIBUTE='hello')
        self.assertIdentical(proxy.SOME_ATTRIBUTE, 'hello')
        self.assertRaises(AttributeError, getattr, proxy, 'DOES_NOT_EXIST')


    def test_getattrIntercept(self):
        """
        Getting an attribute marked as being deprecated on
        L{twisted.python.deprecate._ModuleProxy} results in calling the
        deprecated wrapper's C{get} method.
        """
        proxy = self._makeProxy()
        _deprecatedAttributes = object.__getattribute__(
            proxy, '_deprecatedAttributes')
        _deprecatedAttributes['foo'] = _MockDeprecatedAttribute(42)
        self.assertEqual(proxy.foo, 42)


    def test_privateAttributes(self):
        """
        Private attributes of L{twisted.python.deprecate._ModuleProxy} are
        inaccessible when regular attribute access is used.
        """
        proxy = self._makeProxy()
        self.assertRaises(AttributeError, getattr, proxy, '_module')
        self.assertRaises(
            AttributeError, getattr, proxy, '_deprecatedAttributes')


    def test_setattr(self):
        """
        Setting attributes on L{twisted.python.deprecate._ModuleProxy} proxies
        them through to the wrapped module.
        """
        proxy = self._makeProxy()
        proxy._module = 1
        self.assertNotEquals(object.__getattribute__(proxy, '_module'), 1)
        self.assertEqual(proxy._module, 1)


    def test_repr(self):
        """
        L{twisted.python.deprecated._ModuleProxy.__repr__} produces a string
        containing the proxy type and a representation of the wrapped module
        object.
        """
        proxy = self._makeProxy()
        realModule = object.__getattribute__(proxy, '_module')
        self.assertEqual(
            repr(proxy), '<%s module=%r>' % (type(proxy).__name__, realModule))



class DeprecatedAttributeTests(TestCase):
    """
    Tests for L{twisted.python.deprecate._DeprecatedAttribute} and
    L{twisted.python.deprecate.deprecatedModuleAttribute}, which issue
    warnings for deprecated module-level attributes.
    """
    def setUp(self):
        self.version = deprecatedattributes.version
        self.message = deprecatedattributes.message
        self._testModuleName = __name__ + '.foo'


    def _getWarningString(self, attr):
        """
        Create the warning string used by deprecated attributes.
        """
        return _getDeprecationWarningString(
            deprecatedattributes.__name__ + '.' + attr,
            deprecatedattributes.version,
            DEPRECATION_WARNING_FORMAT + ': ' + deprecatedattributes.message)


    def test_deprecatedAttributeHelper(self):
        """
        L{twisted.python.deprecate._DeprecatedAttribute} correctly sets its
        __name__ to match that of the deprecated attribute and emits a warning
        when the original attribute value is accessed.
        """
        name = 'ANOTHER_DEPRECATED_ATTRIBUTE'
        setattr(deprecatedattributes, name, 42)
        attr = deprecate._DeprecatedAttribute(
            deprecatedattributes, name, self.version, self.message)

        self.assertEqual(attr.__name__, name)

        # Since we're accessing the value getter directly, as opposed to via
        # the module proxy, we need to match the warning's stack level.
        def addStackLevel():
            attr.get()

        # Access the deprecated attribute.
        addStackLevel()
        warningsShown = self.flushWarnings([
            self.test_deprecatedAttributeHelper])
        self.assertIdentical(warningsShown[0]['category'], DeprecationWarning)
        self.assertEqual(
            warningsShown[0]['message'],
            self._getWarningString(name))
        self.assertEqual(len(warningsShown), 1)


    def test_deprecatedAttribute(self):
        """
        L{twisted.python.deprecate.deprecatedModuleAttribute} wraps a
        module-level attribute in an object that emits a deprecation warning
        when it is accessed the first time only, while leaving other unrelated
        attributes alone.
        """
        # Accessing non-deprecated attributes does not issue a warning.
        deprecatedattributes.ANOTHER_ATTRIBUTE
        warningsShown = self.flushWarnings([self.test_deprecatedAttribute])
        self.assertEqual(len(warningsShown), 0)

        name = 'DEPRECATED_ATTRIBUTE'

        # Access the deprecated attribute. This uses getattr to avoid repeating
        # the attribute name.
        getattr(deprecatedattributes, name)

        warningsShown = self.flushWarnings([self.test_deprecatedAttribute])
        self.assertEqual(len(warningsShown), 1)
        self.assertIdentical(warningsShown[0]['category'], DeprecationWarning)
        self.assertEqual(
            warningsShown[0]['message'],
            self._getWarningString(name))


    def test_wrappedModule(self):
        """
        Deprecating an attribute in a module replaces and wraps that module
        instance, in C{sys.modules}, with a
        L{twisted.python.deprecate._ModuleProxy} instance but only if it hasn't
        already been wrapped.
        """
        sys.modules[self._testModuleName] = mod = types.ModuleType('foo')
        self.addCleanup(sys.modules.pop, self._testModuleName)

        setattr(mod, 'first', 1)
        setattr(mod, 'second', 2)

        deprecate.deprecatedModuleAttribute(
            Version('Twisted', 8, 0, 0),
            'message',
            self._testModuleName,
            'first')

        proxy = sys.modules[self._testModuleName]
        self.assertNotEqual(proxy, mod)

        deprecate.deprecatedModuleAttribute(
            Version('Twisted', 8, 0, 0),
            'message',
            self._testModuleName,
            'second')

        self.assertIdentical(proxy, sys.modules[self._testModuleName])



class ImportedModuleAttributeTests(TwistedModulesTestCase):
    """
    Tests for L{deprecatedModuleAttribute} which involve loading a module via
    'import'.
    """

    _packageInit = """\
from twisted.python.deprecate import deprecatedModuleAttribute
from twisted.python.versions import Version

deprecatedModuleAttribute(
    Version('Package', 1, 2, 3), 'message', __name__, 'module')
"""


    def pathEntryTree(self, tree):
        """
        Create some files in a hierarchy, based on a dictionary describing those
        files.  The resulting hierarchy will be placed onto sys.path for the
        duration of the test.

        @param tree: A dictionary representing a directory structure.  Keys are
            strings, representing filenames, dictionary values represent
            directories, string values represent file contents.

        @return: another dictionary similar to the input, with file content
            strings replaced with L{FilePath} objects pointing at where those
            contents are now stored.
        """
        def makeSomeFiles(pathobj, dirdict):
            pathdict = {}
            for (key, value) in dirdict.items():
                child = pathobj.child(key)
                if isinstance(value, str):
                    pathdict[key] = child
                    child.setContent(value)
                elif isinstance(value, dict):
                    child.createDirectory()
                    pathdict[key] = makeSomeFiles(child, value)
                else:
                    raise ValueError("only strings and dicts allowed as values")
            return pathdict
        base = FilePath(self.mktemp())
        base.makedirs()

        result = makeSomeFiles(base, tree)
        self.replaceSysPath([base.path] + sys.path)
        self.replaceSysModules(sys.modules.copy())
        return result


    def simpleModuleEntry(self):
        """
        Add a sample module and package to the path, returning a L{FilePath}
        pointing at the module which will be loadable as C{package.module}.
        """
        paths = self.pathEntryTree(
            {"package": {"__init__.py": self._packageInit,
                         "module.py": ""}})
        return paths['package']['module.py']


    def checkOneWarning(self, modulePath):
        """
        Verification logic for L{test_deprecatedModule}.
        """
        # import package.module
        from package import module
        self.assertEqual(module.__file__, modulePath.path)
        emitted = self.flushWarnings([self.checkOneWarning])
        self.assertEqual(len(emitted), 1)
        self.assertEqual(emitted[0]['message'],
                          'package.module was deprecated in Package 1.2.3: '
                          'message')
        self.assertEqual(emitted[0]['category'], DeprecationWarning)


    def test_deprecatedModule(self):
        """
        If L{deprecatedModuleAttribute} is used to deprecate a module attribute
        of a package, only one deprecation warning is emitted when the
        deprecated module is imported.
        """
        self.checkOneWarning(self.simpleModuleEntry())


    def test_deprecatedModuleMultipleTimes(self):
        """
        If L{deprecatedModuleAttribute} is used to deprecate a module attribute
        of a package, only one deprecation warning is emitted when the
        deprecated module is subsequently imported.
        """
        mp = self.simpleModuleEntry()
        # The first time, the code needs to be loaded.
        self.checkOneWarning(mp)
        # The second time, things are slightly different; the object's already
        # in the namespace.
        self.checkOneWarning(mp)
        # The third and fourth times, things things should all be exactly the
        # same, but this is a sanity check to make sure the implementation isn't
        # special casing the second time.  Also, putting these cases into a loop
        # means that the stack will be identical, to make sure that the
        # implementation doesn't rely too much on stack-crawling.
        for x in range(2):
            self.checkOneWarning(mp)



class WarnAboutFunctionTests(TestCase):
    """
    Tests for L{twisted.python.deprecate.warnAboutFunction} which allows the
    callers of a function to issue a C{DeprecationWarning} about that function.
    """
    def setUp(self):
        """
        Create a file that will have known line numbers when emitting warnings.
        """
        self.package = FilePath(self.mktemp()).child('twisted_private_helper')
        self.package.makedirs()
        self.package.child('__init__.py').setContent('')
        self.package.child('module.py').setContent('''
"A module string"

from twisted.python import deprecate

def testFunction():
    "A doc string"
    a = 1 + 2
    return a

def callTestFunction():
    b = testFunction()
    if b == 3:
        deprecate.warnAboutFunction(testFunction, "A Warning String")
''')
        sys.path.insert(0, self.package.parent().path)
        self.addCleanup(sys.path.remove, self.package.parent().path)

        modules = sys.modules.copy()
        self.addCleanup(
            lambda: (sys.modules.clear(), sys.modules.update(modules)))


    def test_warning(self):
        """
        L{deprecate.warnAboutFunction} emits a warning the file and line number
        of which point to the beginning of the implementation of the function
        passed to it.
        """
        def aFunc():
            pass
        deprecate.warnAboutFunction(aFunc, 'A Warning Message')
        warningsShown = self.flushWarnings()
        filename = __file__
        if filename.lower().endswith('.pyc'):
            filename = filename[:-1]
        self.assertSamePath(
            FilePath(warningsShown[0]["filename"]), FilePath(filename))
        self.assertEqual(warningsShown[0]["message"], "A Warning Message")


    def test_warningLineNumber(self):
        """
        L{deprecate.warnAboutFunction} emits a C{DeprecationWarning} with the
        number of a line within the implementation of the function passed to it.
        """
        from twisted_private_helper import module
        module.callTestFunction()
        warningsShown = self.flushWarnings()
        self.assertSamePath(
            FilePath(warningsShown[0]["filename"]),
            self.package.sibling('twisted_private_helper').child('module.py'))
        # Line number 9 is the last line in the testFunction in the helper
        # module.
        self.assertEqual(warningsShown[0]["lineno"], 9)
        self.assertEqual(warningsShown[0]["message"], "A Warning String")
        self.assertEqual(len(warningsShown), 1)


    def assertSamePath(self, first, second):
        """
        Assert that the two paths are the same, considering case normalization
        appropriate for the current platform.

        @type first: L{FilePath}
        @type second: L{FilePath}

        @raise C{self.failureType}: If the paths are not the same.
        """
        self.assertTrue(
            normcase(first.path) == normcase(second.path),
            "%r != %r" % (first, second))


    def test_renamedFile(self):
        """
        Even if the implementation of a deprecated function is moved around on
        the filesystem, the line number in the warning emitted by
        L{deprecate.warnAboutFunction} points to a line in the implementation of
        the deprecated function.
        """
        from twisted_private_helper import module
        # Clean up the state resulting from that import; we're not going to use
        # this module, so it should go away.
        del sys.modules['twisted_private_helper']
        del sys.modules[module.__name__]

        # Rename the source directory
        self.package.moveTo(self.package.sibling('twisted_renamed_helper'))

        # Import the newly renamed version
        from twisted_renamed_helper import module
        self.addCleanup(sys.modules.pop, 'twisted_renamed_helper')
        self.addCleanup(sys.modules.pop, module.__name__)

        module.callTestFunction()
        warningsShown = self.flushWarnings()
        warnedPath = FilePath(warningsShown[0]["filename"])
        expectedPath = self.package.sibling(
            'twisted_renamed_helper').child('module.py')
        self.assertSamePath(warnedPath, expectedPath)
        self.assertEqual(warningsShown[0]["lineno"], 9)
        self.assertEqual(warningsShown[0]["message"], "A Warning String")
        self.assertEqual(len(warningsShown), 1)


    def test_filteredWarning(self):
        """
        L{deprecate.warnAboutFunction} emits a warning that will be filtered if
        L{warnings.filterwarning} is called with the module name of the
        deprecated function.
        """
        # Clean up anything *else* that might spuriously filter out the warning,
        # such as the "always" simplefilter set up by unittest._collectWarnings.
        # We'll also rely on trial to restore the original filters afterwards.
        del warnings.filters[:]

        warnings.filterwarnings(
            action="ignore", module="twisted_private_helper")

        from twisted_private_helper import module
        module.callTestFunction()

        warningsShown = self.flushWarnings()
        self.assertEqual(len(warningsShown), 0)


    def test_filteredOnceWarning(self):
        """
        L{deprecate.warnAboutFunction} emits a warning that will be filtered
        once if L{warnings.filterwarning} is called with the module name of the
        deprecated function and an action of once.
        """
        # Clean up anything *else* that might spuriously filter out the warning,
        # such as the "always" simplefilter set up by unittest._collectWarnings.
        # We'll also rely on trial to restore the original filters afterwards.
        del warnings.filters[:]

        warnings.filterwarnings(
            action="module", module="twisted_private_helper")

        from twisted_private_helper import module
        module.callTestFunction()
        module.callTestFunction()

        warningsShown = self.flushWarnings()
        self.assertEqual(len(warningsShown), 1)
        message = warningsShown[0]['message']
        category = warningsShown[0]['category']
        filename = warningsShown[0]['filename']
        lineno = warningsShown[0]['lineno']
        msg = warnings.formatwarning(message, category, filename, lineno)
        self.assertTrue(
            msg.endswith("module.py:9: DeprecationWarning: A Warning String\n"
                         "  return a\n"),
            "Unexpected warning string: %r" % (msg,))
