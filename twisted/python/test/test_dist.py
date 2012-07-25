# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for parts of our release automation system.
"""


import os
import sys

from distutils.core import Distribution

from twisted.trial.unittest import TestCase

from twisted.python import dist
from twisted.python.dist import (get_setup_args, ConditionalExtension,
    build_scripts_twisted)
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



class GetExtensionsTest(TestCase):
    """
    Tests for L{dist.getExtensions}.
    """

    setupTemplate = (
        "from twisted.python.dist import ConditionalExtension\n"
        "extensions = [\n"
        "    ConditionalExtension(\n"
        "        '%s', ['twisted/some/thing.c'],\n"
        "        condition=lambda builder: True)\n"
        "    ]\n")

    def setUp(self):
        self.basedir = FilePath(self.mktemp()).child("twisted")
        self.basedir.makedirs()
        self.addCleanup(os.chdir, os.getcwd())
        os.chdir(self.basedir.parent().path)


    def writeSetup(self, name, *path):
        """
        Write out a C{setup.py} file to a location determined by
        L{self.basedir} and L{path}. L{self.setupTemplate} is used to
        generate its contents.
        """
        outdir = self.basedir.descendant(path)
        outdir.makedirs()
        setup = outdir.child("setup.py")
        setup.setContent(self.setupTemplate % (name,))


    def writeEmptySetup(self, *path):
        """
        Write out an empty C{setup.py} file to a location determined by
        L{self.basedir} and L{path}.
        """
        outdir = self.basedir.descendant(path)
        outdir.makedirs()
        outdir.child("setup.py").setContent("")


    def assertExtensions(self, expected):
        """
        Assert that the given names match the (sorted) names of discovered
        extensions.
        """
        extensions = dist.getExtensions()
        names = [extension.name for extension in extensions]
        self.assertEqual(sorted(names), expected)


    def test_getExtensions(self):
        """
        Files named I{setup.py} in I{twisted/topfiles} and I{twisted/*/topfiles}
        are executed with L{execfile} in order to discover the extensions they
        declare.
        """
        self.writeSetup("twisted.transmutate", "topfiles")
        self.writeSetup("twisted.tele.port", "tele", "topfiles")
        self.assertExtensions(["twisted.tele.port", "twisted.transmutate"])


    def test_getExtensionsTooDeep(self):
        """
        Files named I{setup.py} in I{topfiles} directories are not considered if
        they are too deep in the directory hierarchy.
        """
        self.writeSetup("twisted.trans.mog.rify", "trans", "mog", "topfiles")
        self.assertExtensions([])


    def test_getExtensionsNotTopfiles(self):
        """
        The folder in which I{setup.py} is discovered must be called I{topfiles}
        otherwise it is ignored.
        """
        self.writeSetup("twisted.metamorphosis", "notfiles")
        self.assertExtensions([])


    def test_getExtensionsNotSupportedOnJava(self):
        """
        Extensions are not supported on Java-based platforms.
        """
        self.addCleanup(setattr, sys, "platform", sys.platform)
        sys.platform = "java"
        self.writeSetup("twisted.sorcery", "topfiles")
        self.assertExtensions([])


    def test_getExtensionsExtensionsLocalIsOptional(self):
        """
        It is acceptable for extensions to not define the C{extensions} local
        variable.
        """
        self.writeEmptySetup("twisted.necromancy", "topfiles")
        self.assertExtensions([])



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



class DummyCommand:
    """
    A fake Command.
    """
    def __init__(self, **kwargs):
        for kw, val in kwargs.items():
            setattr(self, kw, val)

    def ensure_finalized(self):
        pass



class BuildScriptsTest(TestCase):
    """
    Tests for L{dist.build_scripts_twisted}.
    """

    def setUp(self):
        self.source = FilePath(self.mktemp())
        self.target = FilePath(self.mktemp())
        self.source.makedirs()
        self.addCleanup(os.chdir, os.getcwd())
        os.chdir(self.source.path)


    def buildScripts(self):
        """
        Write 3 types of scripts and run the L{build_scripts_twisted}
        command.
        """
        self.writeScript(self.source, "script1",
                          ("#! /usr/bin/env python2.7\n"
                           "# bogus script w/ Python sh-bang\n"
                           "pass\n"))

        self.writeScript(self.source, "script2.py",
                        ("#!/usr/bin/python\n"
                         "# bogus script w/ Python sh-bang\n"
                         "pass\n"))

        self.writeScript(self.source, "shell.sh",
                        ("#!/bin/sh\n"
                         "# bogus shell script w/ sh-bang\n"
                         "exit 0\n"))

        expected = ['script1', 'script2.py', 'shell.sh']
        cmd = self.getBuildScriptsCmd(self.target,
                                     [self.source.child(fn).path
                                      for fn in expected])
        cmd.finalize_options()
        cmd.run()

        return self.target.listdir()


    def getBuildScriptsCmd(self, target, scripts):
        """
        Create a distutils L{Distribution} with a L{DummyCommand} and wrap it
        in L{build_scripts_twisted}.

        @type target: L{FilePath}
        """
        dist = Distribution()
        dist.scripts = scripts
        dist.command_obj["build"] = DummyCommand(
            build_scripts = target.path,
            force = 1,
            executable = sys.executable
        )
        return build_scripts_twisted(dist)


    def writeScript(self, dir, name, text):
        """
        Write the script to disk.
        """
        with open(dir.child(name).path, "w") as f:
            f.write(text)


    def test_notWindows(self):
        """
        L{build_scripts_twisted} does not rename scripts on non-Windows
        platforms.
        """
        self.patch(os, "name", "twisted")
        built = self.buildScripts()
        for name in ['script1', 'script2.py', 'shell.sh']:
            self.assertTrue(name in built)


    def test_windows(self):
        """
        L{build_scripts_twisted} renames scripts so they end with '.py' on
        the Windows platform.
        """
        self.patch(os, "name", "nt")
        built = self.buildScripts()
        for name in ['script1.py', 'script2.py', 'shell.sh.py']:
            self.assertTrue(name in built)



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
