# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for parts of our release automation system.
"""


import os

from distutils.core import Distribution

from twisted.trial.unittest import TestCase

from twisted.python import dist
from twisted.python.dist import get_setup_args, ConditionalExtension
from twisted.python.filepath import FilePath


class SetupTest(TestCase):
    """
    Tests for L{get_setup_args}.
    """
    def test_conditionalExtensions(self):
        """
        Passing C{conditionalExtensions} as a list of L{ConditionalExtension}
        objects to get_setup_args inserts a custom build_ext into the result
        which knows how to check whether they should be built.
        """
        good_ext = ConditionalExtension("whatever", ["whatever.c"],
                                        condition=lambda b: True)
        bad_ext = ConditionalExtension("whatever", ["whatever.c"],
                                        condition=lambda b: False)
        args = get_setup_args(conditionalExtensions=[good_ext, bad_ext])
        # ext_modules should be set even though it's not used.  See comment
        # in get_setup_args
        self.assertEqual(args["ext_modules"], [good_ext, bad_ext])
        cmdclass = args["cmdclass"]
        build_ext = cmdclass["build_ext"]
        builder = build_ext(Distribution())
        builder.prepare_extensions()
        self.assertEqual(builder.extensions, [good_ext])


    def test_win32Definition(self):
        """
        When building on Windows NT, the WIN32 macro will be defined as 1.
        """
        ext = ConditionalExtension("whatever", ["whatever.c"],
                                   define_macros=[("whatever", 2)])
        args = get_setup_args(conditionalExtensions=[ext])
        builder = args["cmdclass"]["build_ext"](Distribution())
        self.patch(os, "name", "nt")
        builder.prepare_extensions()
        self.assertEqual(ext.define_macros, [("whatever", 2), ("WIN32", 1)])



class GetVersionTest(TestCase):
    """
    Tests for L{dist.getVersion}.
    """

    def setUp(self):
        self.dirname = self.mktemp()
        os.mkdir(self.dirname)

    def test_getVersionCore(self):
        """
        Test that getting the version of core reads from the
        [base]/_version.py file.
        """
        f = open(os.path.join(self.dirname, "_version.py"), "w")
        f.write("""
from twisted.python import versions
version = versions.Version("twisted", 0, 1, 2)
""")
        f.close()
        self.assertEqual(dist.getVersion("core", base=self.dirname), "0.1.2")

    def test_getVersionOther(self):
        """
        Test that getting the version of a non-core project reads from
        the [base]/[projname]/_version.py file.
        """
        os.mkdir(os.path.join(self.dirname, "blat"))
        f = open(os.path.join(self.dirname, "blat", "_version.py"), "w")
        f.write("""
from twisted.python import versions
version = versions.Version("twisted.blat", 9, 8, 10)
""")
        f.close()
        self.assertEqual(dist.getVersion("blat", base=self.dirname), "9.8.10")


class GetScriptsTest(TestCase):
    """
    Tests for L{dist.getScripts} which returns the scripts which should be
    included in the distribution of a project.
    """

    def test_scriptsInSVN(self):
        """
        getScripts should return the scripts associated with a project
        in the context of Twisted SVN.
        """
        basedir = self.mktemp()
        os.mkdir(basedir)
        os.mkdir(os.path.join(basedir, 'bin'))
        os.mkdir(os.path.join(basedir, 'bin', 'proj'))
        f = open(os.path.join(basedir, 'bin', 'proj', 'exy'), 'w')
        f.write('yay')
        f.close()
        scripts = dist.getScripts('proj', basedir=basedir)
        self.assertEqual(len(scripts), 1)
        self.assertEqual(os.path.basename(scripts[0]), 'exy')


    def test_excludedPreamble(self):
        """
        L{dist.getScripts} includes neither C{"_preamble.py"} nor
        C{"_preamble.pyc"}.
        """
        basedir = FilePath(self.mktemp())
        bin = basedir.child('bin')
        bin.makedirs()
        bin.child('_preamble.py').setContent('some preamble code\n')
        bin.child('_preamble.pyc').setContent('some preamble byte code\n')
        bin.child('program').setContent('good program code\n')
        scripts = dist.getScripts("", basedir=basedir.path)
        self.assertEqual(scripts, [bin.child('program').path])


    def test_scriptsInRelease(self):
        """
        getScripts should return the scripts associated with a project
        in the context of a released subproject tarball.
        """
        basedir = self.mktemp()
        os.mkdir(basedir)
        os.mkdir(os.path.join(basedir, 'bin'))
        f = open(os.path.join(basedir, 'bin', 'exy'), 'w')
        f.write('yay')
        f.close()
        scripts = dist.getScripts('proj', basedir=basedir)
        self.assertEqual(len(scripts), 1)
        self.assertEqual(os.path.basename(scripts[0]), 'exy')


    def test_noScriptsInSVN(self):
        """
        When calling getScripts for a project which doesn't actually
        have any scripts, in the context of an SVN checkout, an
        empty list should be returned.
        """
        basedir = self.mktemp()
        os.mkdir(basedir)
        os.mkdir(os.path.join(basedir, 'bin'))
        os.mkdir(os.path.join(basedir, 'bin', 'otherproj'))
        scripts = dist.getScripts('noscripts', basedir=basedir)
        self.assertEqual(scripts, [])


    def test_getScriptsTopLevel(self):
        """
        Passing the empty string to getScripts returns scripts that are (only)
        in the top level bin directory.
        """
        basedir = FilePath(self.mktemp())
        basedir.createDirectory()
        bindir = basedir.child("bin")
        bindir.createDirectory()
        included = bindir.child("included")
        included.setContent("yay included")
        subdir = bindir.child("subdir")
        subdir.createDirectory()
        subdir.child("not-included").setContent("not included")

        scripts = dist.getScripts("", basedir=basedir.path)
        self.assertEqual(scripts, [included.path])


    def test_noScriptsInSubproject(self):
        """
        When calling getScripts for a project which doesn't actually
        have any scripts in the context of that project's individual
        project structure, an empty list should be returned.
        """
        basedir = self.mktemp()
        os.mkdir(basedir)
        scripts = dist.getScripts('noscripts', basedir=basedir)
        self.assertEqual(scripts, [])



class FakeModule(object):
    """
    A fake module, suitable for dependency injection in testing.
    """
    def __init__(self, attrs):
        """
        Initializes a fake module.

        @param attrs: The attrs that will be accessible on the module.
        @type attrs: C{dict} of C{str} (Python names) to objects
        """
        self._attrs = attrs

    def __getattr__(self, name):
        """
        Gets an attribute of this fake module from its attrs.

        @raise AttributeError: When the requested attribute is missing.
        """
        try:
            return self._attrs[name]
        except KeyError:
            raise AttributeError()



fakeCPythonPlatform = FakeModule({"python_implementation": lambda: "CPython"})
fakeOtherPlatform = FakeModule({"python_implementation": lambda: "lvhpy"})
emptyPlatform = FakeModule({})



class WithPlatformTests(TestCase):
    """
    Tests for L{_checkCPython} when used with a (fake) recent C{platform}
    module.
    """
    def test_cpython(self):
        """
        L{_checkCPython} returns C{True} when C{platform.python_implementation}
        says we're running on CPython.
        """
        self.assertTrue(dist._checkCPython(platform=fakeCPythonPlatform))


    def test_other(self):
        """
        L{_checkCPython} returns C{False} when C{platform.python_implementation}
        says we're not running on CPython.
        """
        self.assertFalse(dist._checkCPython(platform=fakeOtherPlatform))



fakeCPythonSys = FakeModule({"subversion": ("CPython", None, None)})
fakeOtherSys = FakeModule({"subversion": ("lvhpy", None, None)})


def _checkCPythonWithEmptyPlatform(sys):
    """
    A partially applied L{_checkCPython} that uses an empty C{platform}
    module (otherwise the code this test case is supposed to test won't
    even be called).
    """
    return dist._checkCPython(platform=emptyPlatform, sys=sys)



class WithSubversionTest(TestCase):
    """
    Tests for L{_checkCPython} when used with a (fake) recent (2.5+)
    C{sys.subversion}. This is effectively only relevant for 2.5, since 2.6 and
    beyond have L{platform.python_implementation}, which is tried first.
    """
    def test_cpython(self):
        """
        L{_checkCPython} returns C{True} when C{platform.python_implementation}
        is unavailable and C{sys.subversion} says we're running on CPython.
        """
        isCPython = _checkCPythonWithEmptyPlatform(fakeCPythonSys)
        self.assertTrue(isCPython)


    def test_other(self):
        """
        L{_checkCPython} returns C{False} when C{platform.python_implementation}
        is unavailable and C{sys.subversion} says we're not running on CPython.
        """
        isCPython = _checkCPythonWithEmptyPlatform(fakeOtherSys)
        self.assertFalse(isCPython)



oldCPythonSys = FakeModule({"modules": {}})
oldPypySys = FakeModule({"modules": {"__pypy__": None}})


class OldPythonsFallbackTest(TestCase):
    """
    Tests for L{_checkCPython} when used on a Python 2.4-like platform, when
    neither C{platform.python_implementation} nor C{sys.subversion} is
    available.
    """
    def test_cpython(self):
        """
        L{_checkCPython} returns C{True} when both
        C{platform.python_implementation} and C{sys.subversion} are unavailable
        and there is no C{__pypy__} module in C{sys.modules}.
        """
        isCPython = _checkCPythonWithEmptyPlatform(oldCPythonSys)
        self.assertTrue(isCPython)


    def test_pypy(self):
        """
        L{_checkCPython} returns C{False} when both
        C{platform.python_implementation} and C{sys.subversion} are unavailable
        and there is a C{__pypy__} module in C{sys.modules}.
        """
        isCPython = _checkCPythonWithEmptyPlatform(oldPypySys)
        self.assertFalse(isCPython)
