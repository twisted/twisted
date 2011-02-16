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
        which knows how to check whether they should be 
        """
        good_ext = ConditionalExtension("whatever", ["whatever.c"],
                                        condition=lambda b: True)
        bad_ext = ConditionalExtension("whatever", ["whatever.c"],
                                        condition=lambda b: False)
        args = get_setup_args(conditionalExtensions=[good_ext, bad_ext])
        # ext_modules should be set even though it's not used.  See comment
        # in get_setup_args
        self.assertEquals(args["ext_modules"], [good_ext, bad_ext])
        cmdclass = args["cmdclass"]
        build_ext = cmdclass["build_ext"]
        builder = build_ext(Distribution())
        builder.prepare_extensions()
        self.assertEquals(builder.extensions, [good_ext])


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
        self.assertEquals(ext.define_macros, [("whatever", 2), ("WIN32", 1)])



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
        self.assertEquals(dist.getVersion("core", base=self.dirname), "0.1.2")

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
        self.assertEquals(dist.getVersion("blat", base=self.dirname), "9.8.10")


class GetScriptsTest(TestCase):

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
        self.assertEquals(len(scripts), 1)
        self.assertEquals(os.path.basename(scripts[0]), 'exy')


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
        self.assertEquals(len(scripts), 1)
        self.assertEquals(os.path.basename(scripts[0]), 'exy')


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
        self.assertEquals(scripts, [])


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
        self.assertEquals(scripts, [included.path])


    def test_noScriptsInSubproject(self):
        """
        When calling getScripts for a project which doesn't actually
        have any scripts in the context of that project's individual
        project structure, an empty list should be returned.
        """
        basedir = self.mktemp()
        os.mkdir(basedir)
        scripts = dist.getScripts('noscripts', basedir=basedir)
        self.assertEquals(scripts, [])
